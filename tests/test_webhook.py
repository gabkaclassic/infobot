from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import payment.endpoints as endpoints

TRUSTED_IP = "185.71.76.1"
UNTRUSTED_IP = "203.0.113.7"


def notification(event, payment_id="pay-1"):
    return {
        "type": "notification",
        "event": event,
        "object": {
            "id": payment_id,
            "status": event.split(".")[-1],
            "paid": event == "payment.succeeded",
            "amount": {"value": "1.00", "currency": "RUB"},
        },
    }


class ClientAddressMiddleware:
    """TestClient жёстко прописывает адрес клиента в ASGI scope, поэтому его
    подменяет заголовок — так же, как это делает ProxyHeadersMiddleware uvicorn
    за реверс-прокси."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            ip = headers.get(b"x-test-client-ip")
            scope["client"] = (ip.decode(), 50000) if ip else None

        await self.app(scope, receive, send)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(endpoints.router)
    app.add_middleware(ClientAddressMiddleware)

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def messages():
    """Подменяет все отправки в Telegram."""
    names = [
        "success_payment_message",
        "success_payment_for_responsible_message",
        "success_payment_for_target_message",
        "failure_payment_message",
    ]
    mocks = {name: AsyncMock() for name in names}

    with ExitStack() as stack:
        for name, mock in mocks.items():
            stack.enter_context(patch.object(endpoints, name, mock))
        yield mocks


def post(client, body, ip=TRUSTED_IP):
    headers = {"x-test-client-ip": ip} if ip else {}
    return client.post("/infobot/payment", json=body, headers=headers)


class TestIpCheck:
    def test_untrusted_ip_is_rejected(self, client, fake_redis, messages):
        response = post(client, notification("payment.succeeded"), ip=UNTRUSTED_IP)

        assert response.status_code == 400

    def test_rejected_ip_is_logged(self, client, fake_redis, messages, project_logs):
        """Регрессия: лог не содержал сам адрес, поэтому за реверс-прокси
        отклонение всех вебхуков было нечем диагностировать."""
        post(client, notification("payment.succeeded"), ip=UNTRUSTED_IP)

        assert UNTRUSTED_IP in project_logs.text

    def test_trusted_ip_is_accepted(self, client, fake_redis, messages):
        response = post(client, notification("payment.succeeded"))

        assert response.status_code == 200

    def test_missing_client_address_is_rejected(self, client, fake_redis, messages):
        response = post(client, notification("payment.succeeded"), ip=None)

        assert response.status_code == 400


class TestMalformedPayload:
    def test_unparsable_body_returns_400(self, client, fake_redis, messages):
        response = post(client, {"event": "нет такого", "object": {}})

        assert response.status_code == 400


class TestSuccessfulPayment:
    async def test_marks_user_paid(self, client, fake_redis, messages):
        await fake_redis.create_payment("42", "pay-1", "https://pay")

        response = post(client, notification("payment.succeeded"))

        assert response.status_code == 200
        assert await fake_redis.users.get_payment_info("42") == {"paid": True}

    async def test_notifies_single_client(self, client, fake_redis, messages):
        await fake_redis.create_payment("42", "pay-1", "https://pay")

        post(client, notification("payment.succeeded"))

        messages["success_payment_message"].assert_awaited_once_with("42")
        messages["success_payment_for_target_message"].assert_not_awaited()

    async def test_gift_notifies_both_sides(self, client, fake_redis, messages):
        await fake_redis.create_payment("42", "pay-1", "https://pay", target_user="99")

        post(client, notification("payment.succeeded"))

        messages["success_payment_for_responsible_message"].assert_awaited_once_with("42")
        messages["success_payment_for_target_message"].assert_awaited_once_with("99")
        messages["success_payment_message"].assert_not_awaited()

    async def test_payment_record_is_removed(self, client, fake_redis, messages):
        await fake_redis.create_payment("42", "pay-1", "https://pay")

        post(client, notification("payment.succeeded"))

        assert await fake_redis.payments.get_key("pay-1") == {}


class TestNotificationFailure:
    async def test_telegram_failure_does_not_break_webhook(
        self, client, fake_redis, messages
    ):
        """Регрессия: пользователь заблокировал бота — оплата уже подтверждена
        в базе, но вебхук отвечал 400, и ЮKassa сутки слала ретраи."""
        await fake_redis.create_payment("42", "pay-1", "https://pay")
        messages["success_payment_message"].side_effect = RuntimeError("bot is blocked")

        response = post(client, notification("payment.succeeded"))

        assert response.status_code == 200
        assert await fake_redis.users.get_payment_info("42") == {"paid": True}


class TestIdempotency:
    async def test_repeated_notification_is_acknowledged(
        self, client, fake_redis, messages
    ):
        """Регрессия: после подтверждения запись платежа удаляется, повтор
        уведомления давал target_id=None и падал с DataError в 400."""
        await fake_redis.create_payment("42", "pay-1", "https://pay")

        first = post(client, notification("payment.succeeded"))
        second = post(client, notification("payment.succeeded"))

        assert first.status_code == 200
        assert second.status_code == 200

    async def test_repeated_notification_sends_no_extra_message(
        self, client, fake_redis, messages
    ):
        await fake_redis.create_payment("42", "pay-1", "https://pay")

        post(client, notification("payment.succeeded"))
        post(client, notification("payment.succeeded"))

        assert messages["success_payment_message"].await_count == 1

    async def test_repeated_notification_keeps_access(
        self, client, fake_redis, messages
    ):
        await fake_redis.create_payment("42", "pay-1", "https://pay")

        post(client, notification("payment.succeeded"))
        post(client, notification("payment.canceled"))

        assert await fake_redis.users.get_payment_info("42") == {"paid": True}

    def test_unknown_payment_is_acknowledged(self, client, fake_redis, messages):
        response = post(client, notification("payment.succeeded", payment_id="нет"))

        assert response.status_code == 200


class TestCanceledPayment:
    async def test_marks_user_unpaid(self, client, fake_redis, messages):
        await fake_redis.create_payment("42", "pay-1", "https://pay")

        response = post(client, notification("payment.canceled"))

        assert response.status_code == 200
        assert await fake_redis.users.get_payment_info("42") == {"paid": False}

    async def test_notifies_responsible(self, client, fake_redis, messages):
        await fake_redis.create_payment("42", "pay-1", "https://pay", target_user="99")

        post(client, notification("payment.canceled"))

        assert messages["failure_payment_message"].await_count == 1
        assert messages["failure_payment_message"].await_args.args[0] == "42"

    async def test_does_not_revoke_already_paid_access(
        self, client, fake_redis, messages
    ):
        await fake_redis.create_payment("42", "pay-1", "https://pay")
        await fake_redis.users.confirm_payment("42")

        response = post(client, notification("payment.canceled"))

        assert response.status_code == 200
        assert await fake_redis.users.get_payment_info("42") == {"paid": True}


class TestDatabaseUnavailable:
    def test_returns_500_so_yookassa_retries(self, client, broken_redis, messages):
        response = post(client, notification("payment.succeeded"))

        assert response.status_code == 500
