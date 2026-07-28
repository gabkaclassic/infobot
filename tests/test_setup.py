import os
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot.setup as bot_setup

VALID_TREE = "| Корень | | \nteacher | Текст | воспитатель | \n"
BROKEN_TREE = "| Корень | | \nteacher | текст без остальных полей\n"


@pytest.fixture
def tree_paths(tmp_path, monkeypatch):
    tree_dir = tmp_path / "trees"
    tree_path = tree_dir / "tree.txt"
    monkeypatch.setattr(bot_setup, "TREE_DIR", str(tree_dir))
    monkeypatch.setattr(bot_setup, "TREE_PATH", str(tree_path))
    return tree_dir, tree_path


@pytest.fixture
def bot_stub():
    stub = MagicMock()
    stub.send_message = AsyncMock()
    return stub


def downloads(content):
    async def download(file_path, destination):
        with open(destination, "w", encoding="utf-8") as file:
            file.write(content)

    return AsyncMock(side_effect=download)


def leftovers(tree_dir):
    return [name for name in os.listdir(tree_dir) if name != "tree.txt"]


class TestHandleTextFile:
    async def test_valid_file_is_applied(self, tree_paths, bot_stub):
        tree_dir, tree_path = tree_paths
        bot_stub.download_file = downloads(VALID_TREE)

        tree, nodes_ids = await bot_setup.handle_text_file(
            bot_stub, MagicMock(), "remote/path"
        )

        assert tree.text == "Корень"
        assert set(nodes_ids) >= {"teacher"}
        assert tree_path.read_text(encoding="utf-8") == VALID_TREE

    async def test_valid_file_leaves_no_temporary_files(self, tree_paths, bot_stub):
        tree_dir, _ = tree_paths
        bot_stub.download_file = downloads(VALID_TREE)

        await bot_setup.handle_text_file(bot_stub, MagicMock(), "remote/path")

        assert leftovers(tree_dir) == []

    async def test_broken_file_reports_error(self, tree_paths, bot_stub):
        bot_stub.download_file = downloads(BROKEN_TREE)

        result = await bot_setup.handle_text_file(
            bot_stub, MagicMock(), "remote/path"
        )

        assert result is None
        assert "Ошибка при парсинге" in bot_stub.send_message.await_args.kwargs["text"]

    async def test_broken_file_leaves_no_temporary_files(self, tree_paths, bot_stub):
        """Регрессия: при ошибке разбора временный файл оставался в каталоге
        деревьев и накапливался с каждой неудачной загрузкой."""
        tree_dir, _ = tree_paths
        bot_stub.download_file = downloads(BROKEN_TREE)

        await bot_setup.handle_text_file(bot_stub, MagicMock(), "remote/path")

        assert leftovers(tree_dir) == []

    async def test_broken_file_keeps_previous_tree(self, tree_paths, bot_stub):
        tree_dir, tree_path = tree_paths
        tree_dir.mkdir(parents=True)
        tree_path.write_text(VALID_TREE, encoding="utf-8")
        bot_stub.download_file = downloads(BROKEN_TREE)

        await bot_setup.handle_text_file(bot_stub, MagicMock(), "remote/path")

        assert tree_path.read_text(encoding="utf-8") == VALID_TREE

    async def test_download_failure_reports_error(self, tree_paths, bot_stub):
        bot_stub.download_file = AsyncMock(side_effect=RuntimeError("сеть недоступна"))

        result = await bot_setup.handle_text_file(
            bot_stub, MagicMock(), "remote/path"
        )

        assert result is None
        assert "Ошибка при парсинге" in bot_stub.send_message.await_args.kwargs["text"]

    async def test_missing_directory_is_created(self, tree_paths, bot_stub):
        tree_dir, _ = tree_paths
        assert not tree_dir.exists()
        bot_stub.download_file = downloads(VALID_TREE)

        await bot_setup.handle_text_file(bot_stub, MagicMock(), "remote/path")

        assert tree_dir.is_dir()
