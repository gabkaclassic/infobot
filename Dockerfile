# 3.12, а не свежее: под него у всех закреплённых в requirements.txt версий есть
# готовые колёса. На 3.13 aiohttp 3.9.5 и yookassa собираются из исходников и
# образу понадобился бы компилятор.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Отдельным слоем до копирования кода, чтобы правка исходников не тянула
# переустановку зависимостей.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# UID должен совпадать с владельцем смонтированных trees/, images/ и logs/,
# иначе бот не сможет записать загруженное дерево и лог.
ARG UID=1000
ARG GID=1000
RUN groupadd --gid "$GID" app \
    && useradd --uid "$UID" --gid "$GID" --create-home app

COPY --chown=app:app . .

USER app

CMD ["python", "main.py"]
