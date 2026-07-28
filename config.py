"""Чтение переменных окружения с валидацией.

Все значения в окружении — строки, поэтому приводить их надо разбором, а не
приведением типа: bool("False") == True.

При отсутствии обязательной переменной или неразбираемом значении бросается
RuntimeError с именем переменной, чтобы ошибка конфигурации была видна сразу,
а не превращалась в TypeError: 'NoneType' где-то на импорте.
"""

import os

TRUE_VALUES = {"1", "true", "yes", "on"}


class ConfigError(RuntimeError):
    pass


def _raw(name, required):
    value = os.environ.get(name)

    if value is None or value == "":
        if required:
            raise ConfigError(f"Не задана обязательная переменная окружения {name}")
        return None

    return value


def env_str(name, default=None, required=False):
    value = _raw(name, required)

    return default if value is None else value


def env_int(name, default=None, required=False):
    value = _raw(name, required)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        raise ConfigError(
            f"Переменная окружения {name} должна быть целым числом, получено: {value!r}"
        )


def env_float(name, default=None, required=False):
    value = _raw(name, required)

    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        raise ConfigError(
            f"Переменная окружения {name} должна быть числом, получено: {value!r}"
        )


def env_bool(name, default=False):
    value = _raw(name, required=False)

    if value is None:
        return default

    return value.strip().lower() in TRUE_VALUES


def env_list(name, default=()):
    value = _raw(name, required=False)

    if value is None:
        return list(default)

    return [item.strip() for item in value.split(",") if item.strip()]


def env_int_list(name, default=()):
    items = env_list(name, default=default)
    result = []

    for item in items:
        try:
            result.append(int(item))
        except ValueError:
            raise ConfigError(
                f"Переменная окружения {name} должна содержать целые числа "
                f"через запятую, получено: {item!r}"
            )

    return result
