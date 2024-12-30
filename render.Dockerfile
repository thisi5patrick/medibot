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

ENTRYPOINT ["poetry", "run"]

CMD ["sh", "-c", "python src/telegram_interface/bot.py & python src/serve_readme.py"]
