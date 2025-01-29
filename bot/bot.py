import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import FSInputFile
from aiogram.types import InlineKeyboardMarkup
from dotenv import load_dotenv
from db.redis.client import payments, add_priveleged_users, user_states, UserState
from payment.client import create_payment
from aiogram.types import ContentType
from bot.setup import handle_text_file
from bot.messages.parsing.parser import prepare_text
from aiogram.filters import Filter

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=os.environ.get("BOT_TOKEN"))
dp = Dispatcher()
ADMINS = [int(id) for id in os.environ.get("ADMINS").split(",")]
enable_setup = os.environ.get("SETUP_ENABLE", "False").lower() == "true"
enable_payments = os.environ.get("PAYMENT_ENABLE", "True").lower() == "true"
greeting_text = prepare_text(os.environ.get("GREETING", ""))


class GiveBotFilter(Filter):
    async def __call__(self, message: types.Message) -> bool:
        return await check_user_gives_bot(message)


def get_keyboard_from_choices(choices):
    button_list = []
    for choice, node in choices.items():
        button_list.append(
            [
                types.InlineKeyboardButton(
                    text=node.short_text, callback_data=nodes_ids.get(choice)
                )
            ]
        )
    reply_markup = InlineKeyboardMarkup(inline_keyboard=button_list)
    return reply_markup

async def check_payment_by_user_id(client_id: str) -> bool:
    payment_info = await payments.users.get_payment_info(client_id)
    paid = payment_info.get("paid", False)
    
    return paid 
    
async def check_payment(message: types.Message) -> bool:

    if not enable_payments:
        return True

    client_id = str(message.chat.id)
    payment_info = await payments.users.get_payment_info(client_id)
    paid = payment_info.get("paid", False)
    confirmation_url = payment_info.get("confirmation_url", False)

    if not paid and not confirmation_url:
        confirmation_url = await create_payment(client_id)
        if not confirmation_url:
            await failure_create_payment_message(message)
            return False

    if not paid:
        await confirm_create_payment(message, confirmation_url)
        return False

    return paid


async def check_user_gives_bot(message: types.Message) -> bool:

    if not enable_payments:
        return False

    return await user_states.check_state(message.chat.id, UserState.GIVE_BOT)


@dp.callback_query(lambda c: True)
async def handle_callback_query(call: types.CallbackQuery):
    try:
        message = call.message

        payment_check_result = await check_payment(message)

        if not payment_check_result:
            return

        await call.answer()

        node_id = nodes_ids.get(call.data)
        node = messages_tree.get_node(node_id)

        if node:
            reply_markup = get_keyboard_from_choices(node.choices)
            await call.message.answer(node.short_text, protect_content=True)
            if node.image:
                image = FSInputFile(node.image)
                if node.text:
                    await call.message.answer_photo(image, protect_content=True)
                    await call.message.answer(
                        node.text,
                        reply_markup=reply_markup,
                        parse_mode="MarkdownV2",
                        protect_content=True,
                    )
                else:
                    await call.message.answer_photo(image, reply_markup=reply_markup)
            elif node.text:
                await call.message.answer(
                    node.text,
                    reply_markup=reply_markup,
                    parse_mode="MarkdownV2",
                    protect_content=True,
                )
    except Exception as e:
        logging.error(f"Error handling callback query: {e}")
        await call.answer(
            text="An error occurred, please try again later.", protect_content=True
        )


@dp.message(lambda message: message.content_type == ContentType.DOCUMENT)
async def handle_document(message: types.Message):

    if not enable_setup:
        return

    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.reply(
            "Вы не имеете права отправлять файлы.", protect_content=True
        )
        return

    document = message.document
    file_id = document.file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path

    if (
        "\\" in document.file_name
        or "/" in document.file_name
        or ".." in document.file_name
    ):
        await message.reply("Невалидное имя файла", protect_content=True)
        return

    file_extension = os.path.splitext(document.file_name)[1].lower()

    global messages_tree, nodes_ids

    if file_extension == ".txt":
        result = await handle_text_file(bot, message, file_path)
        if result:
            messages_tree, nodes_ids = result
    else:
        await message.reply(
            "Пожалуйста, отправьте файл формата txt", protect_content=True
        )


@dp.message(Command("free"))
async def handle_admin_commands(message: types.Message):

    if not enable_setup:
        return

    user_id = message.from_user.id
    if user_id not in ADMINS:
        return

    try:
        text = message.text
        cmd = text.split(" ")
        if len(cmd) > 1:
            arguments = cmd[1:]

        ids = {int(arg) for arg in arguments}
        await add_priveleged_users(ids)
        await message.reply(f'Пользователи успешно добавлены: {", ".join(arguments)}')

    except Exception as e:
        await message.reply(f"Ошибка выполнения команды")


@dp.message(Command("id"))
async def send_client_id(message: types.Message):
    await bot.send_message(message.chat.id, f"Your ID: {message.from_user.id}")


@dp.message(Command("gift"))
async def give_bot(message: types.Message):
    access = await user_states.set_state(message.chat.id, UserState.GIVE_BOT)

    if access:
        await message.reply(
            f"Пожалуйста, пришлите ID пользователя, которому хотите подарить бота:"
        )
    else:
        await message.reply(f"Ошибка в работе бота. Пожалуйста, попробуйте позже")


@dp.message(GiveBotFilter())
async def handle_give_bot_response(message: types.Message):
    try:
        target_user = int(message.text.strip())
        
        if await check_payment_by_user_id(str(target_user)):
            await message.reply('У пользователя с данным ID уже куплен бот')
            return
        
        confirmation_url = await create_payment(
            message.chat.id, target_user=target_user
        )
        if not confirmation_url:
            await failure_create_payment_message(message)
        await confirm_create_payment(message, confirmation_url, greeting=False)
    except ValueError:
        await message.reply(
            "Неверный формат ID. Пожалуйста, в следующий раз отправьте корректный ID пользователя."
        )
    finally:
        await user_states.set_state(message.chat.id, UserState.NONE)
        

@dp.message(Command("start"))
async def entrypoint(message: types.Message):

    payment_check_result = await check_payment(message)

    if not payment_check_result:
        return

    node = messages_tree
    if node:
        reply_markup = get_keyboard_from_choices(node.choices)
        if node.image:
            image = FSInputFile(node.image)
            if node.text:
                await message.answer_photo(image, protect_content=True)
                await message.answer(
                    node.text,
                    reply_markup=reply_markup,
                    parse_mode="MarkdownV2",
                    protect_content=True,
                )
            else:
                await message.answer_photo(
                    image, reply_markup=reply_markup, protect_content=True
                )
        elif node.text:
            await message.answer(
                node.text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2",
                protect_content=True,
            )


async def confirm_create_payment(
    message: types.Message, confirmation_url: str, greeting: bool = True
):

    if greeting_text and greeting:
        await bot.send_message(message.chat.id, greeting_text, parse_mode="MarkdownV2")

    await bot.send_message(
        message.chat.id,
        f"Пожалуйста, оплатите работу бота: \n {confirmation_url}",
    )


async def success_payment_for_responsible_message(client_id: str):
    await bot.send_message(
        client_id,
        "Ваша оплата прошла успешно, спасибо, что дарите другим людям прекрасное!",
    )


async def success_payment_for_target_message(client_id: str):
    await bot.send_message(
        client_id,
        "Вам сделали подарок! Впредь вы можете пользоваться нашим ботом: /start",
    )


async def success_payment_message(client_id: str):
    await bot.send_message(
        client_id,
        "Ваша оплата прошла успешно, впредь вы можете пользоваться нашим ботом: /start",
    )


async def failure_payment_message(client_id: str, status: str):
    try:
        await bot.send_message(
            client_id,
            f"Возникла проблема с оплатой: \n{status}\n Пожалуйста, посмотрите статус оплаты в приложении или на сайте",
        )
    except:
        pass


async def failure_create_payment_message(message: types.Message):
    await message.answer(
        f"Возникла проблема с созданием оплаты. Приносим свои извинения, пожалуйста, попробуйте позже"
    )


async def start_bot():

    global messages_tree, nodes_ids

    from bot.messages.parsing.parser import parse_message_tree

    tree_path = os.environ.get("TREE_PATH")
    messages_tree, nodes_ids = parse_message_tree(tree_path)

    await dp.start_polling(bot)
