FROM python:3.12 as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.2

RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-interaction

COPY . .

ENV PYTHONPATH=/app

FROM base as telegram-bot

ENTRYPOINT ["poetry", "run"]

CMD ["python", "src/telegram_interface/bot.py"]

FROM base as cli-app

RUN poetry run pip install -e .

ENTRYPOINT ["poetry", "run", "medibot"]
