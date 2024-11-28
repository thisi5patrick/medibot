import asyncio
from typing import cast

from telegram import CallbackQuery, Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes, ConversationHandler

from src.telegram_interface.helpers import get_summary_text
from src.telegram_interface.states import CANCEL_MONITORING
from src.telegram_interface.user_data import UserDataDataclass


async def active_monitorings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat = cast(Chat, update.effective_chat)
    user_chat_id = chat.id

    update_message = cast(Message, update.message)
    user_data = cast(UserDataDataclass, context.user_data)

    client = user_data.get("medicover_client")
    if not client:
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    all_tasks = asyncio.all_tasks()
    user_tasks = [task for task in all_tasks if task.get_name().startswith(f"{user_chat_id}_")]

    if not user_tasks:
        await update_message.reply_text("Brak aktywnych monitoringów")
        return ConversationHandler.END

    for task in user_tasks:
        task_hash = task.get_name().split("_")[-1]
        booking_number = user_data["booking_hashes"][task_hash]

        keyboard = [
            [InlineKeyboardButton("Usuń monitoring", callback_data=task.get_name())],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        booking_summary = get_summary_text(user_data, booking_number)

        await update_message.reply_text(booking_summary, reply_markup=reply_markup)

    return CANCEL_MONITORING


async def cancel_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat = cast(Chat, update.effective_chat)
    user_chat_id = chat.id

    query = cast(CallbackQuery, update.callback_query)
    query_message = cast(Message, query.message)

    await query.answer()
    data = cast(str, query.data)

    user_data = cast(UserDataDataclass, context.user_data)
    all_tasks = asyncio.all_tasks()
    user_tasks = [task for task in all_tasks if task.get_name().startswith(f"{user_chat_id}_")]

    for task in user_tasks:
        if task.get_name() == data:
            task.cancel()
            user_data["booking_hashes"].pop(data.split("_")[-1])
            await query_message.edit_text("Monitoring usunięty")

    if not user_tasks:
        await query_message.reply_text("Brak aktywnych monitoringów")
        return ConversationHandler.END

    return CANCEL_MONITORING
