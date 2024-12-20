.PHONY: translate run-telegram docker-telegram build-docker-cli

translate:
	msgfmt src/locales/pl/LC_MESSAGES/messages.po -o src/locales/pl/LC_MESSAGES/messages.mo
	msgfmt src/locales/en/LC_MESSAGES/messages.po -o src/locales/en/LC_MESSAGES/messages.mo

run-telegram:
	poetry run python src/telegram_interface/bot.py

docker-telegram:
	docker build -t telegram-bot -f Dockerfile . && \
	docker run --rm --name telegram-bot telegram-bot

build-docker-cli:
	docker build -t cli-app -f Dockerfile . && \
	docker run --rm --name cli-app cli-app
