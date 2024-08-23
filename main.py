import asyncio
import logging
from bot.bot import start_bot
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)


async def main():
    await asyncio.gather(
        asyncio.create_task(start_bot())
    )


if __name__ == "__main__":
    asyncio.run(main())
