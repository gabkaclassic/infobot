import json

import pytest

from db.redis.client import UserState, add_priveleged_users, user_states


class TestGetKeyContract:
    """Пустой dict — ключа нет, None — база недоступна."""

    async def test_roundtrip(self, fake_redis):
        assert await fake_redis.users.set_key("1", {"paid": True}) is True
        assert await fake_redis.users.get_key("1") == {"paid": True}

    async def test_missing_key_returns_empty_dict(self, fake_redis):
        assert await fake_redis.users.get_key("нет такого") == {}

    async def test_unavailable_database_returns_none(self, broken_redis):
        assert await broken_redis.users.get_key("1") is None

    async def test_set_key_returns_false_when_unavailable(self, broken_redis):
        assert await broken_redis.users.set_key("1", {"paid": True}) is False

    async def test_delete_removes_key(self, fake_redis):
        await fake_redis.users.set_key("1", {"paid": True})
        await fake_redis.users.delete("1")
        assert await fake_redis.users.get_key("1") == {}


class TestUserDatabase:
    async def test_add_user_stores_unpaid_record(self, fake_redis):
        assert await fake_redis.users.add_user("1", "https://pay") is True
        assert await fake_redis.users.get_payment_info("1") == {
            "confirmation_url": "https://pay",
            "paid": False,
        }

    async def test_add_user_rejects_empty_id(self, fake_redis):
        assert await fake_redis.users.add_user("", "https://pay") is False

    async def test_confirm_payment_drops_confirmation_url(self, fake_redis):
        await fake_redis.users.add_user("1", "https://pay")
        assert await fake_redis.users.confirm_payment("1") is True
        assert await fake_redis.users.get_payment_info("1") == {"paid": True}

    async def test_cancel_payment_drops_confirmation_url(self, fake_redis):
        await fake_redis.users.add_user("1", "https://pay")
        assert await fake_redis.users.cancel_payment("1") is True
        assert await fake_redis.users.get_payment_info("1") == {"paid": False}

    async def test_confirm_payment_returns_false_when_unavailable(self, broken_redis):
        assert await broken_redis.users.confirm_payment("1") is False

    async def test_cancel_payment_returns_false_when_unavailable(self, broken_redis):
        assert await broken_redis.users.cancel_payment("1") is False


class TestPaymentDatabase:
    async def test_returns_stored_dict(self, fake_redis):
        await fake_redis.payments.set_key("pay-1", {"responsible": "1", "target_user": "2"})
        assert await fake_redis.payments.get_key("pay-1") == {
            "responsible": "1",
            "target_user": "2",
        }

    async def test_legacy_string_format_is_expanded(self, fake_redis):
        """Старые записи хранили просто client_id — совместимость сохраняется."""
        await fake_redis.payments.set_key("pay-1", "42")
        assert await fake_redis.payments.get_key("pay-1") == {
            "responsible": "42",
            "target_user": "42",
        }

    async def test_missing_key_returns_empty_dict(self, fake_redis):
        assert await fake_redis.payments.get_key("нет такого") == {}

    async def test_unavailable_database_returns_none(self, broken_redis):
        assert await broken_redis.payments.get_key("pay-1") is None

    async def test_close_payment_returns_entity_and_deletes(self, fake_redis):
        await fake_redis.payments.set_key("pay-1", {"responsible": "1", "target_user": "2"})
        entity = await fake_redis.payments.close_payment("pay-1")

        assert entity == {"responsible": "1", "target_user": "2"}
        assert await fake_redis.payments.get_key("pay-1") == {}


class TestPaymentManagerCreate:
    async def test_writes_payment_and_user_records(self, fake_redis):
        result = await fake_redis.create_payment("1", "pay-1", "https://pay")

        assert result == "https://pay"
        assert await fake_redis.payments.get_key("pay-1") == {
            "responsible": "1",
            "target_user": "1",
        }
        assert await fake_redis.users.get_payment_info("1") == {
            "confirmation_url": "https://pay",
            "paid": False,
        }

    async def test_target_user_defaults_to_client(self, fake_redis):
        await fake_redis.create_payment("1", "pay-1", "https://pay")
        entity = await fake_redis.payments.get_key("pay-1")

        assert entity["target_user"] == entity["responsible"] == "1"

    async def test_gift_records_separate_target(self, fake_redis):
        await fake_redis.create_payment("1", "pay-1", "https://pay", target_user="2")

        assert await fake_redis.payments.get_key("pay-1") == {
            "responsible": "1",
            "target_user": "2",
        }
        assert await fake_redis.users.get_payment_info("2") == {
            "confirmation_url": "https://pay",
            "paid": False,
        }
        assert await fake_redis.users.get_payment_info("1") == {}


class TestPaymentManagerConfirm:
    async def test_marks_user_paid_and_removes_payment(self, fake_redis):
        await fake_redis.create_payment("1", "pay-1", "https://pay")

        assert await fake_redis.confirm_payment("1", "pay-1") is True
        assert await fake_redis.users.get_payment_info("1") == {"paid": True}
        assert await fake_redis.payments.get_key("pay-1") == {}

    async def test_gift_marks_target_paid(self, fake_redis):
        await fake_redis.create_payment("1", "pay-1", "https://pay", target_user="2")

        assert await fake_redis.confirm_payment("2", "pay-1") is True
        assert await fake_redis.users.get_payment_info("2") == {"paid": True}


class TestPaymentManagerCancel:
    async def test_cancels_unpaid_user(self, fake_redis):
        await fake_redis.create_payment("1", "pay-1", "https://pay")

        assert await fake_redis.cancel_payment("1", "pay-1") is True
        assert await fake_redis.users.get_payment_info("1") == {"paid": False}
        assert await fake_redis.payments.get_key("pay-1") == {}

    async def test_does_not_revoke_access_of_paid_user(self, fake_redis):
        await fake_redis.create_payment("1", "pay-1", "https://pay")
        await fake_redis.confirm_payment("1", "pay-1")

        assert await fake_redis.cancel_payment("1", "pay-2") is False
        assert await fake_redis.users.get_payment_info("1") == {"paid": True}

    async def test_empty_client_id_returns_false(self, fake_redis):
        assert await fake_redis.cancel_payment(None, "pay-1") is False

    async def test_unavailable_database_returns_false(self, broken_redis):
        assert await broken_redis.cancel_payment("1", "pay-1") is False


class TestUserStateDatabase:
    async def test_set_and_check_state(self, fake_redis):
        assert await user_states.set_state("1", UserState.GIVE_BOT) is True
        assert await user_states.check_state("1", UserState.GIVE_BOT) is True
        assert await user_states.check_state("1", UserState.NONE) is False

    async def test_unknown_client_has_no_state(self, fake_redis):
        assert await user_states.check_state("нет такого", UserState.GIVE_BOT) is False

    async def test_state_can_be_reset(self, fake_redis):
        await user_states.set_state("1", UserState.GIVE_BOT)
        await user_states.set_state("1", UserState.NONE)

        assert await user_states.check_state("1", UserState.GIVE_BOT) is False


class TestPrivilegedUsers:
    async def test_single_id_is_accepted(self, fake_redis):
        await add_priveleged_users(111)

        assert await fake_redis.users.get_payment_info("111") == {"paid": True}

    async def test_iterable_of_ids(self, fake_redis):
        await add_priveleged_users({111, 222})

        assert await fake_redis.users.get_payment_info("111") == {"paid": True}
        assert await fake_redis.users.get_payment_info("222") == {"paid": True}

    async def test_empty_list_writes_nothing(self, fake_redis):
        await add_priveleged_users([])

        assert await fake_redis.users.redis.dbsize() == 0
