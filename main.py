import asyncio
import logging
from bot.bot import start_bot
from payment.app import start_app
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)


async def main():
    await asyncio.gather(
        asyncio.create_task(start_bot()),
        asyncio.create_task(start_app())
    )


if __name__ == "__main__":
    asyncio.run(main())
