import asyncio
import logging

from dotenv import load_dotenv

load_dotenv()

from config import env_bool, env_str
from bot.bot import start_bot
from payment.app import start_app

# Уровень должен настраиваться здесь: basicConfig не переопределяет root-логгер,
# у которого уже есть обработчики, поэтому вызов из импортируемого модуля
# молча выиграл бы у этого.
log_level = env_str("LOG_LEVEL", "INFO").upper()

if log_level not in logging._nameToLevel:
    log_level = "INFO"

logging.basicConfig(level=log_level)

enable_payments = env_bool("PAYMENT_ENABLE", True)


async def main():

    tasks = [asyncio.create_task(start_bot())]

    if enable_payments:
        tasks.append(asyncio.create_task(start_app()))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
