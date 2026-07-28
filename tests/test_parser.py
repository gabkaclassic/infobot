import pytest

from bot.messages.message_node import MessageNode
from bot.messages.parsing.parser import get_hash, parse_message_tree, prepare_text


@pytest.fixture
def tree_file(tmp_path):
    def writer(content):
        path = tmp_path / "tree.txt"
        path.write_text(content, encoding="utf-8")
        return str(path)

    return writer


SIMPLE_TREE = """\
| Корневой текст | |
teacher | Текст воспитателя | воспитатель |
parent | Текст родителя | родитель |
teacher.age | Про возраст | возраст |
"""


class TestPrepareText:
    @pytest.mark.parametrize(
        "symbol",
        [".", "!", "#", "+", "=", "-", "(", ")"],
    )
    def test_escapes_markdown_symbols(self, symbol):
        assert prepare_text(f"а{symbol}б") == f"а\\{symbol}б"

    def test_converts_literal_newline(self):
        assert prepare_text("первая\\nвторая") == "первая\nвторая"

    def test_strips_surrounding_spaces(self):
        assert prepare_text("  текст  ") == "текст"

    def test_escapes_underscore_in_url_only(self):
        result = prepare_text("см http://a.b/c_d")

        assert "http://a\\.b/c\\_d" in result

    def test_keeps_underscore_outside_url(self):
        assert prepare_text("имя_файла") == "имя_файла"

    def test_empty_text(self):
        assert prepare_text("") == ""


class TestGetHash:
    def test_is_deterministic(self):
        assert get_hash("teacher") == get_hash("teacher")

    def test_differs_for_different_input(self):
        assert get_hash("teacher") != get_hash("parent")


class TestParseMessageTree:
    def test_first_line_becomes_root(self, tree_file):
        tree, _ = parse_message_tree(tree_file(SIMPLE_TREE))

        assert tree.text == "Корневой текст"
        assert tree.image is None

    def test_children_are_attached_to_root(self, tree_file):
        tree, _ = parse_message_tree(tree_file(SIMPLE_TREE))

        assert set(tree.choices) == {"teacher", "parent"}
        assert tree.choices["teacher"].short_text == "воспитатель"

    def test_nested_node_is_reachable(self, tree_file):
        tree, _ = parse_message_tree(tree_file(SIMPLE_TREE))
        node = tree.get_node("teacher.age")

        assert node is not None
        assert node.short_text == "возраст"

    def test_ids_map_is_bidirectional(self, tree_file):
        _, nodes_ids = parse_message_tree(tree_file(SIMPLE_TREE))
        short_id = nodes_ids["teacher"]

        assert nodes_ids[short_id] == "teacher"
        assert short_id == get_hash("teacher")

    def test_root_is_not_in_ids_map(self, tree_file):
        _, nodes_ids = parse_message_tree(tree_file(SIMPLE_TREE))

        assert "" not in nodes_ids

    def test_blank_lines_are_skipped(self, tree_file):
        tree, _ = parse_message_tree(tree_file("| Корень | | \n\n\nteacher | Т | в | \n"))

        assert set(tree.choices) == {"teacher"}

    def test_ids_are_isolated_between_calls(self, tree_file):
        """Регрессия: словарь был модульным, поэтому идентификаторы старого
        дерева накапливались после каждой перезагрузки файла."""
        first_path = tree_file(SIMPLE_TREE)
        _, first_ids = parse_message_tree(first_path)

        second = "| Корень | | \nother | Текст | другое | \n"
        _, second_ids = parse_message_tree(tree_file(second))

        assert "teacher" in first_ids
        assert "teacher" not in second_ids
        assert set(second_ids) == {"other", get_hash("other")}

    def test_broken_line_does_not_pollute_previous_ids(self, tree_file):
        _, good_ids = parse_message_tree(tree_file(SIMPLE_TREE))

        with pytest.raises(IndexError):
            parse_message_tree(tree_file("| Корень | | \nbroken | текст\n"))

        assert "teacher" in good_ids


class TestMessageNode:
    def test_add_and_get_nested_node(self):
        root = MessageNode("корень", "корень")
        root.add_node("a", MessageNode("а", "а"))
        root.add_node("a.b", MessageNode("б", "б"))

        assert root.get_node("a.b").text == "б"

    def test_get_unknown_node_returns_none(self):
        root = MessageNode("корень", "корень")
        root.add_node("a", MessageNode("а", "а"))

        assert root.get_node("нет") is None

    def test_get_node_with_empty_id_returns_none(self):
        root = MessageNode("корень", "корень")

        assert root.get_node("") is None
        assert root.get_node(None) is None

    def test_new_node_has_no_choices(self):
        assert MessageNode("текст", "коротко").choices == {}
