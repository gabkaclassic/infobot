# 3.12, а не свежее: под него у всех закреплённых в pyproject.toml версий есть
# готовые колёса. На 3.13 aiohttp 3.9.5 и yookassa собираются из исходников и
# образу понадобился бы компилятор.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Отдельным слоем до копирования кода, чтобы правка исходников не тянула
# переустановку зависимостей. Это работает потому, что в pyproject.toml
# packages = [] — сборка не требует исходников и ставит только зависимости.
COPY pyproject.toml .
# setuptools собирает проект прямо в рабочем каталоге, поэтому после установки
# в образе остаются build/ и *.egg-info — убираем их тем же слоем.
RUN pip install --no-cache-dir . \
    && rm -rf build *.egg-info

# UID должен совпадать с владельцем смонтированных trees/, images/ и logs/,
# иначе бот не сможет записать загруженное дерево и лог.
ARG UID=1000
ARG GID=1000
# WORKDIR создаётся от root, а COPY --chown меняет владельца только у
# скопированного содержимого. Без явного chown приложение не смогло бы создать
# каталог логов — при штатном запуске это скрыто bind-монтированием, но образ
# сам по себе оказался бы нерабочим.
RUN groupadd --gid "$GID" app \
    && useradd --uid "$UID" --gid "$GID" --create-home app \
    && mkdir -p /app/logs /app/trees \
    && chown -R "$UID:$GID" /app

COPY --chown=app:app . .

USER app

CMD ["python", "main.py"]
