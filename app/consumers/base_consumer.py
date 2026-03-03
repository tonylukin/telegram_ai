from abc import abstractmethod, ABC
import asyncio
import aio_pika
import time
import aiohttp

from app.config import RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_HOST
from app.configs.logger import logger
from app.services.notification_sender import NotificationSender


class BaseConsumer(ABC):
    MAX_RETRIES = 1 # was 5 -> move to DLQ immediately
    RETRY_DELAY = 5
    MESSAGE_RETRY_DELAY = 180
    LONG_SESSION_TIMEOUT = aiohttp.ClientTimeout(
        total=1800,
        connect=20,
        sock_read=1800
    )

    def __init__(self, queue: str, notification_sender: NotificationSender, message_retry_delay: int = MESSAGE_RETRY_DELAY):
        self._queue = queue
        self._message_retry_delay = message_retry_delay
        self._notification_sender = notification_sender
        self._dlx = None
        self._aiohttpClient = aiohttp.ClientSession()

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
                    self._dlx = dlx
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
                    await message.ack()
                    result = await self.handle_message(message)

                    if result:
                        success = True
                        notification_message = self.get_notification_message()
                        if notification_message:
                            await self._notification_sender.send_notification_message(notification_message)
                        break
                    else:
                        raise Exception("handle_message returned False")

                except Exception as e:
                    logger.exception(f"❌ [{attempt}] Error processing message: {e}")
                    if attempt < BaseConsumer.MAX_RETRIES:
                        await asyncio.sleep(self._message_retry_delay)
                    else:
                        logger.error("🚫 Max retries reached, will requeue message")
        finally:
            if not success:
                try:
                    logger.error("☠️ Message moved to Dead Letter Queue")
                    await self._send_to_dlq(message, error="Max retries reached")
                except Exception:
                    logger.exception("⚠️ Failed to reject message")

    async def _send_to_dlq(self, message: aio_pika.abc.AbstractIncomingMessage, error: str) -> None:
        if not self._dlx:
            logger.error("DLX not initialized, cannot send to DLQ")
            return
        headers = dict(message.headers or {})
        headers.update({
            "x-error": error,
            "x-original-queue": self._queue,
            "x-failed-at": int(time.time()),
            "x-original-delivery-tag": getattr(message, "delivery_tag", None),
        })

        await self._dlx.publish(
            aio_pika.Message(
                body=message.body,
                content_type=message.content_type,
                content_encoding=message.content_encoding,
                headers=headers,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                correlation_id=message.correlation_id,
                message_id=message.message_id,
                timestamp=message.timestamp,
            ),
            routing_key=self._queue,
        )

    @abstractmethod
    async def handle_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> bool:
        pass

    @abstractmethod
    def get_notification_message(self) -> str | None:
        return None
