import logging
import os
from pathlib import Path

import pytest

import logger_config


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    target = tmp_path / "logs"
    monkeypatch.setattr(logger_config, "LOG_DIR", target)
    return target


@pytest.fixture(autouse=True)
def cleanup_logger():
    yield
    logger = logging.getLogger("тестовый-логгер")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


class TestSetupLogger:
    def test_creates_missing_directory(self, log_dir):
        """Регрессия: каталог logs исключён .gitignore, git не хранит пустые
        каталоги, поэтому в свежем клоне импорт падал с FileNotFoundError."""
        assert not log_dir.exists()

        logger_config.setup_logger("тестовый-логгер", "test.log")

        assert log_dir.is_dir()

    def test_writes_into_log_file(self, log_dir):
        logger = logger_config.setup_logger("тестовый-логгер", "test.log")
        logger.info("строка лога")

        for handler in logger.handlers:
            handler.flush()

        assert "строка лога" in (log_dir / "test.log").read_text(encoding="utf-8")

    def test_existing_directory_is_reused(self, log_dir):
        log_dir.mkdir(parents=True)

        logger_config.setup_logger("тестовый-логгер", "test.log")

        assert log_dir.is_dir()

    def test_does_not_propagate_to_root(self, log_dir):
        """Иначе строки задваиваются: свой обработчик плюс обработчик root."""
        logger = logger_config.setup_logger("тестовый-логгер", "test.log")

        assert logger.propagate is False


class TestModuleLevelPaths:
    def test_log_dir_is_absolute(self):
        assert Path(logger_config.LOG_DIR).is_absolute()

    def test_log_dir_defaults_next_to_project(self, monkeypatch):
        """Путь не должен зависеть от текущего каталога запуска."""
        assert Path(logger_config.BASE_DIR).is_absolute()
        assert (Path(logger_config.BASE_DIR) / "main.py").exists()

    def test_default_log_file_exists(self):
        assert os.path.exists(Path(logger_config.LOG_DIR) / "log.log")
