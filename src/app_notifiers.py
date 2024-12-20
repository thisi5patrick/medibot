from abc import ABC, abstractmethod

import asyncclick as click
from notifiers import get_notifier


class Notifier(ABC):
    @abstractmethod
    def send_message(self, message: str) -> None:
        pass


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str):
        super().__init__()
        self.notifier = get_notifier("telegram")
        self.token = token
        self.chat_id = chat_id

    def send_message(self, message: str) -> None:
        response = self.notifier.notify(message=message, token=self.token, chat_id=self.chat_id)
        if response.ok:
            click.secho("Telegram notification sent", fg="green")
        else:
            click.secho("Telegram notification failed", fg="red")
