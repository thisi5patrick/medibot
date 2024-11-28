from typing import cast

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from src.telegram_interface.user_data import UserDataDataclass


async def clear_search_history_entrypoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    user_data = cast(UserDataDataclass, context.user_data)
    user_data["history"] = {"locations": [], "specializations": [], "clinics": {}, "doctors": {}, "temp_data": {}}

    await update.message.reply_text("Wyczyszczono historię wyszukiwania.")

    return ConversationHandler.END
