import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import FSInputFile
from aiogram.types import InlineKeyboardMarkup
from dotenv import load_dotenv
from bot.messages.message_tree import messages_tree
from bot.messages.parsing.parser import nodes_ids
from db.redis.client import payments
from payment.client import create_payment

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
        message = call.message
        client_id = str(message.chat.id)
        payment_info = payments.users.get_payment_info(client_id)
        paid = payment_info.get('paid', False)
        confirmation_url = payment_info.get('confirmation_url', False)

        if not paid and not confirmation_url:
            confirmation_url = await create_payment(client_id)
            if not confirmation_url:
                await failure_create_payment_message(message)
                return

        if not paid:
            await confirm_create_payment(message, confirmation_url)
            return

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


@dp.message(Command('id'))
async def send_client_id(message: types.Message):
    await bot.send_message(message.chat.id, f'Your ID: {message.from_user.id}')


@dp.message(Command('start'))
async def entrypoint(message: types.Message):
    client_id = str(message.chat.id)
    payment_info = payments.users.get_payment_info(client_id)
    paid = payment_info.get('paid', False)
    confirmation_url = payment_info.get('confirmation_url', False)

    if not paid and not confirmation_url:
        confirmation_url = await create_payment(client_id)
        if not confirmation_url:
            await failure_create_payment_message(message)
            return

    if not paid:
        await confirm_create_payment(message, confirmation_url)
        return

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


async def confirm_create_payment(message: types.Message, confirmation_url: str):
    await bot.send_message(
        message.chat.id,
        f'Пожалуйста, оплатите работу бота: \n {confirmation_url}',
    )


async def success_payment_message(client_id: str):
    await bot.send_message(
        client_id,
        'Ваша оплата прошла успешно, впредь вы можете пользоваться нашим ботом'
    )


async def failure_payment_message(client_id: str, status: str):
    await bot.send_message(
        client_id,
        f'Возникла проблема с оплатой: \n{status}\n Пожалуйста, посмотрите статус оплаты в приложении или на сайте'
    )


async def failure_create_payment_message(message: types.Message):
    await message.answer(
        f'Возникла проблема с созданием оплаты. Приносим свои извинения, пожалуйста, попробуйте позже'
    )


async def start_bot():
    await dp.start_polling(bot)
