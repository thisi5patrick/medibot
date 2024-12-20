import os
from typing import Literal, cast

from dotenv import load_dotenv
from telegram import Message, Update
from telegram.ext import ContextTypes, ConversationHandler

from src.locale_handler import SUPPORTED_LANGUAGES, _
from src.telegram_interface.user_data import UserDataDataclass

load_dotenv()


async def start_entrypoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    default_language = os.getenv("TELEGRAM_DEFAULT_LANGUAGE")
    if default_language is None:
        default_language = "en"
    if default_language not in SUPPORTED_LANGUAGES:
        await update_message.reply_text("Default language is not supported.")
        return ConversationHandler.END

    user_data["medicover_client"] = None
    user_data["history"] = {"locations": [], "specializations": [], "clinics": {}, "doctors": {}, "temp_data": {}}
    user_data["bookings"] = {}
    user_data["current_booking_number"] = 0
    user_data["booking_hashes"] = {}
    user_data["language"] = cast(Literal["en", "pl"], default_language)
    user_data["username"] = ""
    user_data["password"] = ""

    await update_message.reply_text(_("Welcome to the unofficial Medicover Bot.", user_data["language"]))

    return ConversationHandler.END
