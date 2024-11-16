import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from src.client import MedicoverClient
from src.telegram_interface.states import PROVIDE_PASSWORD, PROVIDE_USERNAME

logger = logging.getLogger(__name__)


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    await update.message.reply_text("Log in to Medicover.\n\nPlease provide your username:")
    return PROVIDE_USERNAME


async def username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None or update.message is None:
        return ConversationHandler.END

    context.user_data["username"] = update.message.text
    await update.message.reply_text("Please provide your password:")
    return PROVIDE_PASSWORD


async def password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None or update.message is None:
        return ConversationHandler.END

    context.user_data["password"] = update.message.text
    username = context.user_data["username"]
    password = context.user_data["password"]

    medicover_client = MedicoverClient(username, password)
    try:
        medicover_client.log_in()
        context.user_data["medicover_client"] = medicover_client
        await update.message.reply_text("Login attempt successful.")
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text("Login failed. Please try again.")
        return await login(update, context)
