from abc import abstractmethod, ABC
import asyncio
import aio_pika

from app.config import RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_HOST
from app.configs.logger import logger
from app.services.notification_sender import NotificationSender


class BaseConsumer(ABC):
    MAX_RETRIES = 5
    RETRY_DELAY = 5
    MESSAGE_RETRY_DELAY = 180

    def __init__(self, queue: str, notification_sender: NotificationSender, message_retry_delay: int = MESSAGE_RETRY_DELAY):
        self._queue = queue
        self._message_retry_delay = message_retry_delay
        self._notification_sender = notification_sender

    async def init(self):
        while True:
            try:
                logger.info("🚀 Connecting to RabbitMQ…")
                connection = await aio_pika.connect_robust(
                    f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}/"
                )
                async with connection:
                    channel = await connection.channel()
                    await channel.set_qos(prefetch_count=5)

                    # Declare DLX (dead letter exchange) and DLQ
                    dlx = await channel.declare_exchange(
                        f"{self._queue}.dlx", aio_pika.ExchangeType.DIRECT, durable=True
                    )
                    dlq = await channel.declare_queue(f"{self._queue}.dlq", durable=True)
                    await dlq.bind(dlx, routing_key=self._queue)

                    # Declare main queue with DLX params
                    args = {
                        "x-dead-letter-exchange": f"{self._queue}.dlx",
                        "x-dead-letter-routing-key": self._queue,
                    }
                    queue = await channel.declare_queue(self._queue, durable=True, arguments=args)

                    logger.info(f"🎯 [{self._queue}] Waiting for messages…")
                    await queue.consume(self.__handle_message, no_ack=False)

                    await asyncio.Future()
            except Exception as e:
                logger.error(f"🔄 Connection lost or error: {e}")
                logger.info(f"⏳ Reconnecting in {BaseConsumer.RETRY_DELAY} seconds…")
                await asyncio.sleep(BaseConsumer.RETRY_DELAY)

    async def __handle_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        success = False

        try:
            for attempt in range(1, BaseConsumer.MAX_RETRIES + 1):
                try:
                    logger.info(f"📥 Processing message: attempt {attempt}")
                    result = await self.handle_message(message)

                    if result:
                        await message.ack()
                        success = True
                        notification_message = self.get_notification_message()
                        if notification_message:
                            await self._notification_sender.send_notification_message(notification_message)
                        break
                    else:
                        raise Exception("handle_message returned False")

                except Exception as e:
                    logger.error(f"❌ [{attempt}] Error processing message: {e}")
                    if attempt < BaseConsumer.MAX_RETRIES:
                        await asyncio.sleep(self._message_retry_delay)
                    else:
                        logger.error("🚫 Max retries reached, will requeue message")
        finally:
            if not success:
                try:
                    logger.error("☠️ Message moved to Dead Letter Queue")
                    await message.reject(requeue=False)
                except Exception as nack_err:
                    logger.error(f"⚠️ Failed to reject message: {nack_err}")

    @abstractmethod
    async def handle_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> bool:
        pass

    @abstractmethod
    def get_notification_message(self) -> str | None:
        return None
