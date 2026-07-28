import pytest

from config import (
    ConfigError,
    env_bool,
    env_float,
    env_int,
    env_int_list,
    env_list,
    env_str,
)


@pytest.fixture
def env(monkeypatch):
    def setter(value):
        if value is None:
            monkeypatch.delenv("SOME_VAR", raising=False)
        else:
            monkeypatch.setenv("SOME_VAR", value)

    return setter


class TestEnvBool:
    @pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "on", " on "])
    def test_truthy_values(self, env, value):
        env(value)
        assert env_bool("SOME_VAR") is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "FALSE", "no", "off"])
    def test_falsy_values(self, env, value):
        env(value)
        assert env_bool("SOME_VAR") is False

    def test_string_false_is_not_true(self, env):
        """Регрессия: bool("False") == True, поэтому DEV всегда включался."""
        env("False")
        assert env_bool("SOME_VAR", default=True) is False

    def test_missing_returns_default(self, env):
        env(None)
        assert env_bool("SOME_VAR", default=True) is True
        assert env_bool("SOME_VAR") is False

    def test_empty_returns_default(self, env):
        env("")
        assert env_bool("SOME_VAR", default=True) is True


class TestEnvInt:
    def test_parses_value(self, env):
        env("6379")
        assert env_int("SOME_VAR") == 6379

    def test_missing_returns_default(self, env):
        env(None)
        assert env_int("SOME_VAR", 42) == 42

    def test_missing_required_raises_with_name(self, env):
        env(None)
        with pytest.raises(ConfigError, match="SOME_VAR"):
            env_int("SOME_VAR", required=True)

    def test_invalid_raises_with_name(self, env):
        env("не число")
        with pytest.raises(ConfigError, match="SOME_VAR"):
            env_int("SOME_VAR")


class TestEnvFloat:
    def test_parses_value(self, env):
        env("1.5")
        assert env_float("SOME_VAR") == 1.5

    def test_invalid_raises(self, env):
        env("abc")
        with pytest.raises(ConfigError, match="SOME_VAR"):
            env_float("SOME_VAR")

    def test_missing_required_raises(self, env):
        env(None)
        with pytest.raises(ConfigError, match="SOME_VAR"):
            env_float("SOME_VAR", required=True)


class TestEnvStr:
    def test_returns_value(self, env):
        env("значение")
        assert env_str("SOME_VAR") == "значение"

    def test_empty_treated_as_missing(self, env):
        env("")
        assert env_str("SOME_VAR", "по умолчанию") == "по умолчанию"

    def test_missing_required_raises(self, env):
        env(None)
        with pytest.raises(ConfigError, match="SOME_VAR"):
            env_str("SOME_VAR", required=True)


class TestEnvList:
    def test_splits_and_strips(self, env):
        env(" 111 , 222 ,333 ")
        assert env_list("SOME_VAR") == ["111", "222", "333"]

    def test_drops_empty_items(self, env):
        env("111,,222,")
        assert env_list("SOME_VAR") == ["111", "222"]

    def test_empty_returns_empty_list(self, env):
        env("")
        assert env_list("SOME_VAR") == []

    def test_missing_returns_default_copy(self, env):
        env(None)
        result = env_list("SOME_VAR", default=("a",))
        result.append("b")
        assert env_list("SOME_VAR", default=("a",)) == ["a"]


class TestEnvIntList:
    def test_parses_ints(self, env):
        env("111, 222")
        assert env_int_list("SOME_VAR") == [111, 222]

    def test_empty_returns_empty_list(self, env):
        env("")
        assert env_int_list("SOME_VAR") == []

    def test_invalid_item_raises_with_name(self, env):
        env("111,abc")
        with pytest.raises(ConfigError, match="SOME_VAR"):
            env_int_list("SOME_VAR")
