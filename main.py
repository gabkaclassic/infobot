import asyncio
import logging
import os

from dotenv import load_dotenv

from bot.bot import start_bot
from payment.app import start_app

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

enable_payments = os.environ.get("PAYMENT_ENABLE", "True").lower() == "true"


async def main():

    tasks = [asyncio.create_task(start_bot())]

    if enable_payments:
        tasks.append(asyncio.create_task(start_app()))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    from bot.messages.parsing.parser import parse_message_tree

    tree_path = os.environ.get("TREE_PATH")
    messages_tree, nodes_ids = parse_message_tree(tree_path)

    asyncio.run(main())
