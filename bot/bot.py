import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import FSInputFile
from aiogram.types import InlineKeyboardMarkup
from dotenv import load_dotenv
from bot.messages.message_tree import messages_tree
from bot.messages.parsing.parser import nodes_ids

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=os.environ.get('BOT_TOKEN'))
dp = Dispatcher()


def get_keyboard_from_choices(choices):
    button_list = []
    for choice, node in choices.items():
        button_list.append([
            types.InlineKeyboardButton(
                text=node.short_text,
                callback_data=nodes_ids.get(choice)
            )
        ])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=button_list)
    return reply_markup


@dp.callback_query(lambda c: True)
async def handle_callback_query(call: types.CallbackQuery):
    try:
        await call.answer()
        node_id = nodes_ids.get(call.data)
        node = messages_tree.get_node(node_id)

        if node:
            reply_markup = get_keyboard_from_choices(node.choices)
            await call.message.answer(node.short_text)
            if node.image:
                image = FSInputFile(node.image)
                if node.text:
                    await call.message.answer_photo(image)
                    await call.message.answer(node.text, reply_markup=reply_markup, parse_mode='MarkdownV2')
                else:
                    await call.message.answer_photo(image, reply_markup=reply_markup)
            elif node.text:
                await call.message.answer(node.text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    except Exception as e:
        logging.error(f"Error handling callback query: {e}")
        await call.answer(text="An error occurred, please try again later.")

@dp.message(Command('start'))
async def entrypoint(message: types.Message):
    node = messages_tree
    if node:
        reply_markup = get_keyboard_from_choices(node.choices)
        if node.image:
            image = FSInputFile(node.image)
            if node.text:
                await message.answer_photo(image)
                await message.answer(node.text, reply_markup=reply_markup, parse_mode='MarkdownV2')
            else:
                await message.answer_photo(image, reply_markup=reply_markup)
        elif node.text:
            await message.answer(node.text, reply_markup=reply_markup, parse_mode='MarkdownV2')


async def start_bot():
    await dp.start_polling(bot)
