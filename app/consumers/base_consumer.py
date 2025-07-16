from abc import abstractmethod, ABC
import asyncio
import aio_pika

from app.config import RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_HOST
from app.configs.logger import logger

class BaseConsumer(ABC):
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    MESSAGE_RETRY_DELAY = 300

    def __init__(self, queue: str, message_retry_delay: int = MESSAGE_RETRY_DELAY):
        self.queue = queue
        self.message_retry_delay = message_retry_delay

    async def init(self):
        while True:
            try:
                logger.info("🚀 Connecting to RabbitMQ…")
                connection = await aio_pika.connect_robust(
                    f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}/")
                async with connection:
                    channel = await connection.channel()
                    await channel.set_qos(prefetch_count=1)

                    queue = await channel.declare_queue(self.queue, durable=True)
                    logger.info("🎯 Waiting for messages…")

                    await queue.consume(self.__handle_message, no_ack=False)

                    await asyncio.Future()
            except Exception as e:
                logger.error(f"🔄 Connection lost or error: {e}")
                logger.info(f"⏳ Reconnecting in {BaseConsumer.RETRY_DELAY} seconds…")
                await asyncio.sleep(BaseConsumer.RETRY_DELAY)

    async def __handle_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        async with message.process(requeue=False):
            for attempt in range(1, BaseConsumer.MAX_RETRIES + 1):
                try:
                    await self.handle_message(message)
                    break
                except Exception as e:
                    logger.error(f"❌ [{attempt}] Error processing message: {e}")
                    if attempt < BaseConsumer.MAX_RETRIES:
                        await asyncio.sleep(self.message_retry_delay)
                    else:
                        await message.nack(requeue=True)
                        logger.error("🚫 Max retries reached, message requeued")

    @abstractmethod
    async def handle_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        pass