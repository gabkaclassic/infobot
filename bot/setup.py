import os
import shutil
from bot.messages.parsing.parser import parse_message_tree
from uuid import uuid4 as uuid
from dotenv import load_dotenv
from config import env_str
from logger_config import logger

load_dotenv()

TREE_PATH = env_str("TREE_PATH", required=True)
TREE_DIR = os.path.dirname(TREE_PATH) or "."


async def handle_text_file(bot, message, file_path):

    os.makedirs(TREE_DIR, exist_ok=True)
    tmp_destination = os.path.join(TREE_DIR, f"{uuid()}.txt")

    try:
        await bot.download_file(file_path, tmp_destination)

        await bot.send_message(
            chat_id=message.chat.id, text="Начинаю загрузку файла с деревом диалога"
        )
        result = parse_message_tree(tmp_destination)

        shutil.move(tmp_destination, TREE_PATH)

        await bot.send_message(
            chat_id=message.chat.id, text="Файл с деревом диалога загружен"
        )
        return result
    except Exception as e:
        logger.error(f"Tree file handling failed: {e}", exc_info=True)
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Ошибка при парсинге файла с деревом диалога: {str(e)}",
        )
    finally:
        if os.path.exists(tmp_destination):
            os.remove(tmp_destination)
