from typing import cast

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes, ConversationHandler

from src.locale_handler import _
from src.telegram_interface.states import (
    CHANGE_LANGUAGE,
    CLEAR_SEARCH_HISTORY,
    READ_CHANGE_LANGUAGE,
    SELECTING_SETTING,
)
from src.telegram_interface.user_data import UserDataDataclass


async def settings_entrypoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    keyboard = [
        [InlineKeyboardButton(_("Change language", user_data["language"]), callback_data=str(CHANGE_LANGUAGE))],
        [
            InlineKeyboardButton(
                _("Clear search history", user_data["language"]), callback_data=str(CLEAR_SEARCH_HISTORY)
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update_message.reply_text(
        _("Select the setting you want to change:", user_data["language"]), reply_markup=reply_markup
    )

    return SELECTING_SETTING


async def show_change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    query = cast(CallbackQuery, update.callback_query)
    query_message = cast(Message, query.message)

    keyboard = [
        [InlineKeyboardButton(_("English", user_data["language"]), callback_data="en")],
        [InlineKeyboardButton(_("Polish", user_data["language"]), callback_data="pl")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query_message.reply_text(
        _("Select the language you want to use:", user_data["language"]), reply_markup=reply_markup
    )

    return READ_CHANGE_LANGUAGE


async def read_change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    await query.answer()
    language_selection = cast(str, query.data)
    if language_selection == "pl":
        user_data["language"] = "pl"
        language = _("Polish", user_data["language"])
    else:
        user_data["language"] = "en"
        language = _("English", user_data["language"])

    await query.edit_message_text(f"\u2705 {_("Language changed to:", user_data["language"])} {language}")

    return ConversationHandler.END


async def clear_search_history_entrypoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    query_message = cast(Message, query.message)

    user_data = cast(UserDataDataclass, context.user_data)
    user_data["history"] = {"locations": [], "specializations": [], "clinics": {}, "doctors": {}, "temp_data": {}}

    await query_message.edit_text(_("Search history cleared.", user_data["language"]))

    return ConversationHandler.END
