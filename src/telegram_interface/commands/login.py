import logging
from typing import cast

from telegram import Message, Update
from telegram.ext import ContextTypes, ConversationHandler

from src.locale_handler import _
from src.medicover_client.client import MedicoverClient
from src.telegram_interface.states import PROVIDE_PASSWORD, PROVIDE_USERNAME
from src.telegram_interface.user_data import UserDataDataclass

logger = logging.getLogger(__name__)


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    await update_message.reply_text(_("Log in to Medicover.\n\nPlease provide your username:", user_data["language"]))
    return PROVIDE_USERNAME


async def username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    user_data["username"] = cast(str, update_message.text)
    await update_message.reply_text(_("Please provide your password:", user_data["language"]))
    return PROVIDE_PASSWORD


async def password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    user_data["password"] = cast(str, update_message.text)
    username = user_data["username"]
    password = user_data["password"]

    medicover_client = MedicoverClient(username, password)
    try:
        await medicover_client.log_in()
        user_data["medicover_client"] = medicover_client
        await update_message.reply_text(_("Login attempt successful.", user_data["language"]))
        user_data["username"] = ""
        user_data["password"] = ""
        return ConversationHandler.END
    except Exception:
        await update_message.reply_text(_("Login failed. Please try again.", user_data["language"]))
        return await login(update, context)
