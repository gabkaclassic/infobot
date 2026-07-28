import json
from unittest.mock import MagicMock, patch

import pytest

import payment.client as payment_client


def yookassa_response(payment_id="pay-1", confirmation_url="https://pay.test/1"):
    body = {"id": payment_id}

    if confirmation_url is not None:
        body["confirmation"] = {"confirmation_url": confirmation_url}

    response = MagicMock()
    response.json.return_value = json.dumps(body)
    return response


@pytest.fixture
def yookassa():
    with patch.object(payment_client, "Payment") as mock:
        yield mock


class TestCreatePayment:
    async def test_returns_confirmation_url(self, fake_redis, yookassa):
        yookassa.create.return_value = yookassa_response()

        result = await payment_client.create_payment("1")

        assert result == "https://pay.test/1"

    async def test_stores_payment_and_user_records(self, fake_redis, yookassa):
        yookassa.create.return_value = yookassa_response()

        await payment_client.create_payment("1")

        assert await fake_redis.payments.get_key("pay-1") == {
            "responsible": "1",
            "target_user": "1",
        }
        assert await fake_redis.users.get_payment_info("1") == {
            "confirmation_url": "https://pay.test/1",
            "paid": False,
        }

    async def test_gift_stores_target_user(self, fake_redis, yookassa):
        yookassa.create.return_value = yookassa_response()

        await payment_client.create_payment(1, target_user=2)

        assert await fake_redis.payments.get_key("pay-1") == {
            "responsible": 1,
            "target_user": 2,
        }

    async def test_yookassa_failure_returns_none(self, fake_redis, yookassa):
        """Регрессия: исключение уходило наверх через check_payment и aiogram
        его проглатывал, из-за чего пользователь не получал вообще ничего."""
        yookassa.create.side_effect = RuntimeError("YooKassa is unavailable")

        assert await payment_client.create_payment("1") is None

    async def test_yookassa_failure_writes_nothing(self, fake_redis, yookassa):
        yookassa.create.side_effect = RuntimeError("YooKassa is unavailable")

        await payment_client.create_payment("1")

        assert await fake_redis.users.get_payment_info("1") == {}

    async def test_response_without_confirmation_url_returns_none(
        self, fake_redis, yookassa
    ):
        yookassa.create.return_value = yookassa_response(confirmation_url=None)

        assert await payment_client.create_payment("1") is None

    async def test_database_failure_returns_none(self, broken_redis, yookassa):
        yookassa.create.return_value = yookassa_response()

        assert await payment_client.create_payment("1") is None

    async def test_receipt_is_built_with_configured_cost(self, fake_redis, yookassa):
        yookassa.create.return_value = yookassa_response()

        await payment_client.create_payment("1")

        request = yookassa.create.call_args.args[0]
        assert float(request.amount.value) == payment_client.cost


class TestBuildPaymentRequest:
    def test_sets_configured_contacts(self):
        request = payment_client.build_payment_request()

        assert request.receipt.customer.email == "shop@example.test"
        assert request.receipt.customer.phone == "79000000000"

    def test_empty_contacts_do_not_raise(self, monkeypatch):
        """sample.env поставляется с пустыми PAYMENT_EMAIL и PAYMENT_PHONE,
        а сеттеры ЮKassa падают на пустом значении."""
        monkeypatch.setattr(payment_client, "receipt_email", None)
        monkeypatch.setattr(payment_client, "receipt_phone", None)

        request = payment_client.build_payment_request()

        assert request.receipt.customer is None

    async def test_create_payment_survives_empty_contacts(
        self, fake_redis, yookassa, monkeypatch
    ):
        monkeypatch.setattr(payment_client, "receipt_email", None)
        monkeypatch.setattr(payment_client, "receipt_phone", None)
        yookassa.create.return_value = yookassa_response()

        assert await payment_client.create_payment("1") == "https://pay.test/1"


class TestConfigurePayment:
    def test_passes_credentials_to_sdk(self):
        with patch.object(payment_client, "Configuration") as configuration:
            payment_client.configure_payment()

        configuration.configure.assert_called_once_with("test-account", "test-secret")
