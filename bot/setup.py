import os
import shutil
from bot.messages.parsing.parser import parse_message_tree
from uuid import uuid4 as uuid
from dotenv import load_dotenv

load_dotenv()

TREE_PATH = os.environ.get("TREE_PATH")
TREE_DIR = TREE_PATH[: TREE_PATH.rindex("/")]


async def handle_text_file(bot, message, file_path):

    tmp_destination = os.path.join(TREE_DIR, f"{uuid()}.txt")
    await bot.download_file(file_path, tmp_destination)

    try:

        await bot.send_message(
            chat_id=message.chat.id, text=f"Начинаю загрузку файла с деревом диалога"
        )
        result = parse_message_tree(tmp_destination)

        shutil.move(tmp_destination, TREE_PATH)

        await bot.send_message(
            chat_id=message.chat.id, text=f"Файл с деревом диалога загружен"
        )
        return result
    except Exception as e:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Ошибка при парсинге файла с деревом диалога: {str(e)}",
        )
