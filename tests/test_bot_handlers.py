from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot.bot as bot_module
from bot.messages.message_node import MessageNode
from db.redis.client import UserState, user_states


def make_message(chat_id=42, text="", user_id=None):
    message = MagicMock()
    message.chat.id = chat_id
    message.from_user.id = user_id if user_id is not None else chat_id
    message.text = text
    message.reply = AsyncMock()
    message.answer = AsyncMock()
    message.answer_photo = AsyncMock()
    return message


@pytest.fixture
def sent():
    """Подменяет исходящие сообщения бота."""
    with patch.object(bot_module, "bot") as bot_mock:
        bot_mock.send_message = AsyncMock()
        bot_mock.get_file = AsyncMock()
        bot_mock.download_file = AsyncMock()
        yield bot_mock


@pytest.fixture
def created_payment():
    with patch.object(bot_module, "create_payment", AsyncMock()) as mock:
        yield mock


class TestCheckPayment:
    async def test_paid_user_passes(self, fake_redis, sent):
        await fake_redis.users.add_user("42", "")
        await fake_redis.users.confirm_payment("42")

        assert await bot_module.check_payment(make_message()) is True

    async def test_pending_user_gets_existing_link(
        self, fake_redis, sent, created_payment
    ):
        await fake_redis.users.add_user("42", "https://pay")

        assert await bot_module.check_payment(make_message()) is False
        created_payment.assert_not_awaited()
        assert "https://pay" in sent.send_message.await_args.args[1]

    async def test_new_user_gets_payment_created(
        self, fake_redis, sent, created_payment
    ):
        created_payment.return_value = "https://pay/new"

        assert await bot_module.check_payment(make_message()) is False
        created_payment.assert_awaited_once_with("42")
        assert "https://pay/new" in sent.send_message.await_args.args[1]

    async def test_payment_creation_failure_reports_error(
        self, fake_redis, sent, created_payment
    ):
        created_payment.return_value = None
        message = make_message()

        assert await bot_module.check_payment(message) is False
        assert "Возникла проблема с созданием оплаты" in message.answer.await_args.args[0]

    async def test_unavailable_database_does_not_create_payment(
        self, broken_redis, sent, created_payment
    ):
        """Регрессия: get_key возвращал None, вызов .get() на нём падал
        с AttributeError и пользователь не получал ответа."""
        message = make_message()

        assert await bot_module.check_payment(message) is False
        created_payment.assert_not_awaited()
        assert "Возникла проблема с созданием оплаты" in message.answer.await_args.args[0]

    async def test_disabled_payments_always_pass(self, fake_redis, sent, monkeypatch):
        monkeypatch.setattr(bot_module, "enable_payments", False)

        assert await bot_module.check_payment(make_message()) is True


class TestCheckPaymentByUserId:
    async def test_paid_user(self, fake_redis):
        await fake_redis.users.add_user("99", "")
        await fake_redis.users.confirm_payment("99")

        assert await bot_module.check_payment_by_user_id("99") is True

    async def test_unknown_user(self, fake_redis):
        assert await bot_module.check_payment_by_user_id("99") is False

    async def test_unavailable_database_returns_none(self, broken_redis):
        assert await bot_module.check_payment_by_user_id("99") is None


class TestGiveBotResponse:
    async def test_creates_payment_for_target(
        self, fake_redis, sent, created_payment
    ):
        created_payment.return_value = "https://pay/gift"
        message = make_message(text=" 99 ")

        await bot_module.handle_give_bot_response(message)

        created_payment.assert_awaited_once_with(42, target_user=99)
        assert "https://pay/gift" in sent.send_message.await_args.args[1]

    async def test_no_greeting_for_gift(self, fake_redis, sent, created_payment):
        created_payment.return_value = "https://pay/gift"

        await bot_module.handle_give_bot_response(make_message(text="99"))

        assert sent.send_message.await_count == 1

    async def test_already_paid_target_is_reported(
        self, fake_redis, sent, created_payment
    ):
        await fake_redis.users.add_user("99", "")
        await fake_redis.users.confirm_payment("99")
        message = make_message(text="99")

        await bot_module.handle_give_bot_response(message)

        created_payment.assert_not_awaited()
        assert message.reply.await_args.args[0] == "У пользователя с данным ID уже куплен бот"

    async def test_payment_failure_does_not_send_broken_link(
        self, fake_redis, sent, created_payment
    ):
        """Регрессия: без return пользователь получал извинение, а следом
        «Пожалуйста, оплатите работу бота: None»."""
        created_payment.return_value = None
        message = make_message(text="99")

        await bot_module.handle_give_bot_response(message)

        assert "Возникла проблема с созданием оплаты" in message.answer.await_args.args[0]
        sent.send_message.assert_not_awaited()

    async def test_invalid_id_is_reported(self, fake_redis, sent, created_payment):
        message = make_message(text="не число")

        await bot_module.handle_give_bot_response(message)

        created_payment.assert_not_awaited()
        assert "Неверный формат ID" in message.reply.await_args.args[0]

    async def test_unavailable_database_is_reported(
        self, broken_redis, sent, created_payment
    ):
        message = make_message(text="99")

        await bot_module.handle_give_bot_response(message)

        created_payment.assert_not_awaited()
        assert "Возникла проблема с созданием оплаты" in message.answer.await_args.args[0]

    @pytest.mark.parametrize("text", ["99", "не число"])
    async def test_state_is_always_reset(
        self, fake_redis, sent, created_payment, text
    ):
        created_payment.return_value = "https://pay/gift"
        await user_states.set_state(42, UserState.GIVE_BOT)

        await bot_module.handle_give_bot_response(make_message(text=text))

        assert await user_states.check_state(42, UserState.GIVE_BOT) is False


class TestAdminCommands:
    async def test_non_admin_is_ignored(self, fake_redis, sent):
        message = make_message(text="/free 555", user_id=999)

        await bot_module.handle_admin_commands(message)

        message.reply.assert_not_awaited()
        assert await fake_redis.users.get_payment_info("555") == {}

    async def test_admin_adds_privileged_users(self, fake_redis, sent):
        message = make_message(text="/free 555 666", user_id=111)

        await bot_module.handle_admin_commands(message)

        assert await fake_redis.users.get_payment_info("555") == {"paid": True}
        assert await fake_redis.users.get_payment_info("666") == {"paid": True}

    async def test_command_without_arguments_shows_usage(self, fake_redis, sent):
        """Регрессия: arguments оставалась неопределённой и NameError
        превращался в бесполезное «Ошибка выполнения команды»."""
        message = make_message(text="/free", user_id=111)

        await bot_module.handle_admin_commands(message)

        assert message.reply.await_args.args[0] == "Использование: /free ID1 ID2 ..."

    async def test_invalid_id_reports_error(self, fake_redis, sent):
        message = make_message(text="/free абв", user_id=111)

        await bot_module.handle_admin_commands(message)

        assert message.reply.await_args.args[0] == "Ошибка выполнения команды"

    async def test_disabled_setup_ignores_command(
        self, fake_redis, sent, monkeypatch
    ):
        monkeypatch.setattr(bot_module, "enable_setup", False)
        message = make_message(text="/free 555", user_id=111)

        await bot_module.handle_admin_commands(message)

        message.reply.assert_not_awaited()


class TestDocumentUpload:
    @pytest.fixture
    def document_message(self):
        message = make_message(user_id=111)
        message.document.file_id = "file-1"
        message.document.file_name = "tree.txt"
        return message

    async def test_non_admin_is_rejected(self, sent, document_message):
        document_message.from_user.id = 999

        await bot_module.handle_document(document_message)

        assert document_message.reply.await_args.args[0] == "Вы не имеете права отправлять файлы."

    async def test_non_txt_is_rejected(self, sent, document_message):
        document_message.document.file_name = "tree.pdf"

        await bot_module.handle_document(document_message)

        assert "формата txt" in document_message.reply.await_args.args[0]

    @pytest.mark.parametrize("name", ["../tree.txt", "dir/tree.txt", "dir\\tree.txt"])
    async def test_path_traversal_is_rejected(self, sent, document_message, name):
        document_message.document.file_name = name

        await bot_module.handle_document(document_message)

        assert document_message.reply.await_args.args[0] == "Невалидное имя файла"

    async def test_valid_file_replaces_tree(self, sent, document_message):
        with patch.object(bot_module, "handle_text_file", AsyncMock()) as handler:
            handler.return_value = ("новое дерево", {"a": "b"})

            await bot_module.handle_document(document_message)

        assert bot_module.messages_tree == "новое дерево"
        assert bot_module.nodes_ids == {"a": "b"}

    async def test_failed_parsing_keeps_previous_tree(self, sent, document_message):
        bot_module.messages_tree = "старое дерево"
        bot_module.nodes_ids = {"old": "id"}

        with patch.object(bot_module, "handle_text_file", AsyncMock()) as handler:
            handler.return_value = None

            await bot_module.handle_document(document_message)

        assert bot_module.messages_tree == "старое дерево"
        assert bot_module.nodes_ids == {"old": "id"}

    async def test_disabled_setup_ignores_document(
        self, sent, document_message, monkeypatch
    ):
        monkeypatch.setattr(bot_module, "enable_setup", False)

        await bot_module.handle_document(document_message)

        document_message.reply.assert_not_awaited()


class TestKeyboard:
    def test_buttons_use_hashed_callback_data(self, monkeypatch):
        monkeypatch.setattr(bot_module, "nodes_ids", {"teacher": "hash-1"})
        choices = {"teacher": MessageNode("текст", "воспитатель")}

        markup = bot_module.get_keyboard_from_choices(choices)

        assert len(markup.inline_keyboard) == 1
        button = markup.inline_keyboard[0][0]
        assert button.text == "воспитатель"
        assert button.callback_data == "hash-1"

    def test_preserves_choices_order(self, monkeypatch):
        monkeypatch.setattr(bot_module, "nodes_ids", {"a": "h1", "b": "h2"})
        choices = {
            "a": MessageNode("т", "первая"),
            "b": MessageNode("т", "вторая"),
        }

        markup = bot_module.get_keyboard_from_choices(choices)

        assert [row[0].text for row in markup.inline_keyboard] == ["первая", "вторая"]

    def test_empty_choices_give_empty_keyboard(self):
        assert bot_module.get_keyboard_from_choices({}).inline_keyboard == []


class TestGiveBotCommand:
    async def test_sets_state_and_asks_for_id(self, fake_redis, sent):
        message = make_message()

        await bot_module.give_bot(message)

        assert await user_states.check_state(42, UserState.GIVE_BOT) is True
        assert message.reply.await_args.args[0] == bot_module.get_id_instruction

    async def test_reports_error_when_state_not_saved(self, broken_redis, sent):
        message = make_message()

        await bot_module.give_bot(message)

        assert "Ошибка в работе бота" in message.reply.await_args.args[0]


class TestUserGivesBotFilter:
    async def test_true_in_give_bot_state(self, fake_redis):
        await user_states.set_state(42, UserState.GIVE_BOT)

        assert await bot_module.check_user_gives_bot(make_message()) is True

    async def test_false_without_state(self, fake_redis):
        assert await bot_module.check_user_gives_bot(make_message()) is False

    async def test_false_when_payments_disabled(self, fake_redis, monkeypatch):
        monkeypatch.setattr(bot_module, "enable_payments", False)
        await user_states.set_state(42, UserState.GIVE_BOT)

        assert await bot_module.check_user_gives_bot(make_message()) is False
