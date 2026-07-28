"""Окружение для тестов.

Значения выставляются в теле модуля, а не в фикстуре: проектные модули читают
переменные окружения и создают объекты (Bot, клиенты Redis, файловый логгер)
прямо на импорте, а conftest выполняется раньше, чем pytest импортирует тесты.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

TEST_ENV = {
    "BOT_TOKEN": "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
    "ADMINS": "111,222",
    "SETUP_ENABLE": "True",
    "PAYMENT_ENABLE": "True",
    "GREETING": "Привет",
    "GET_ID_INSTRUCTION": "Пришлите ID",
    "IMAGES_PATH": str(BASE_DIR / "images"),
    "TREE_PATH": str(BASE_DIR / "trees" / "tree.txt"),
    "HOST": "127.0.0.1",
    "PORT": "8000",
    "DEV": "False",
    "FORWARDED_ALLOW_IPS": "127.0.0.1",
    "LOG_LEVEL": "INFO",
    "PAYMENT_COST": "1.0",
    "PAYMENT_DESCRIPTION": "Оплата бота",
    "PAYMENT_PRIVILEGED_USERS": "",
    "PAYMENT_ACCOUNT_ID": "test-account",
    "PAYMENT_SECRET_KEY": "test-secret",
    "PAYMENT_PHONE": "79000000000",
    "PAYMENT_EMAIL": "shop@example.test",
    "PAYMENT_WEBHOOK_URL": "https://example.test/return",
    "DB_HOST": "localhost",
    "DB_PORT": "6379",
    "DB_USER": "",
    "DB_PASSWORD": "",
}

# Тесты не должны зависеть от .env разработчика: перекрываем значения безусловно.
os.environ.update(TEST_ENV)
os.environ["LOG_DIR"] = str(BASE_DIR / "logs")

import pytest
from fakeredis import aioredis as fake_aioredis

import db.redis.client as redis_client


@pytest.fixture
def fake_redis():
    """Подменяет соединения всех трёх баз на общий in-memory сервер."""
    from fakeredis import FakeServer

    server = FakeServer()
    targets = {
        redis_client.payments.users: 1,
        redis_client.payments.payments: 2,
        redis_client.user_states: 3,
    }
    originals = {database: database.redis for database in targets}

    for database, db_number in targets.items():
        database.redis = fake_aioredis.FakeRedis(
            server=server, db=db_number, decode_responses=True
        )

    yield redis_client.payments

    for database, original in originals.items():
        database.redis = original


@pytest.fixture
def project_logs(caplog):
    """Логгер проекта не всплывает в root (propagate = False), поэтому штатный
    caplog его не видит и обработчик нужно подключить напрямую."""
    from logger_config import logger as project_logger

    project_logger.addHandler(caplog.handler)
    caplog.set_level("DEBUG")

    yield caplog

    project_logger.removeHandler(caplog.handler)


@pytest.fixture
def broken_redis(fake_redis):
    """Имитирует недоступную базу: падают и обычные команды, и pipeline —
    транзакционные записи идут мимо get/set и иначе продолжали бы работать."""
    from unittest.mock import AsyncMock, MagicMock

    def down(*args, **kwargs):
        raise ConnectionError("redis is down")

    databases = [
        redis_client.payments.users,
        redis_client.payments.payments,
        redis_client.user_states,
    ]

    for database in databases:
        database.redis.get = AsyncMock(side_effect=ConnectionError("redis is down"))
        database.redis.set = AsyncMock(side_effect=ConnectionError("redis is down"))
        database.redis.delete = AsyncMock(side_effect=ConnectionError("redis is down"))
        database.redis.ping = AsyncMock(side_effect=ConnectionError("redis is down"))
        database.redis.pipeline = MagicMock(side_effect=down)

    return fake_redis
