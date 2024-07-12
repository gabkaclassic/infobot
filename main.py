import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import FSInputFile
from aiogram.types import InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=os.environ.get('BOT_TOKEN'))
dp = Dispatcher()


def get_keyboard_from_choices(choices):
    button_list = []
    for choice, node in choices.items():
        button_list.append(
            types.InlineKeyboardButton(
                text=node.short_text,
                callback_data=choice
            )
        )
    reply_markup = InlineKeyboardMarkup(inline_keyboard=[button_list])
    return reply_markup


@dp.callback_query(lambda c: True)
async def handle_callback_query(call: types.CallbackQuery):
    await call.answer()

    node = messages_tree.get_node(call.data)

    if node:
        if node.image:
            image = FSInputFile(node.image)
            await call.message.answer_photo(image)

        await call.message.answer(node.text, reply_markup=get_keyboard_from_choices(node.choices),
                                  parse_mode="Markdown")


@dp.message(Command('start'))
async def entrypoint(message: types.Message):
    node = messages_tree
    if node:
        if node.image:
            with open(node.image, 'rb') as image:
                await message.answer_photo(photo=image)
        await message.answer(node.text, reply_markup=get_keyboard_from_choices(node.choices), parse_mode='MarkdownV2')


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    from messages.message_tree import messages_tree

    asyncio.run(main())
