import asyncio
from typing import Any, cast

from telegram import CallbackQuery, Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes, ConversationHandler

from src.client import MedicoverClient
from src.telegram_interface.states import CANCEL_MONITORING


async def active_monitorings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat = cast(Chat, update.effective_chat)
    user_chat_id = chat.id

    update_message = cast(Message, update.message)
    user_data = cast(dict[str, Any], context.user_data)

    client: MedicoverClient | None = user_data.get("medicover_client")
    if not client:
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    all_tasks = asyncio.all_tasks()
    user_tasks = [task for task in all_tasks if task.get_name().startswith(str(user_chat_id))]

    if not user_tasks:
        await update_message.reply_text("Brak aktywnych monitoringów")
        return ConversationHandler.END

    for task in user_tasks:
        keyboard = [
            [InlineKeyboardButton("Usuń monitoring", callback_data=task.get_name())],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        task_data = user_data[task.get_name()]

        # TODO: add proper text with appoinment data
        await update_message.reply_text(task_data, reply_markup=reply_markup)

    user_data["user_tasks"] = user_tasks

    return CANCEL_MONITORING


async def cancel_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    query_message = cast(Message, query.message)

    await query.answer()
    data = cast(str, query.data)

    user_data = cast(dict[str, Any], context.user_data)
    user_tasks = user_data.get("user_tasks", [])

    for task in user_tasks:
        if task.get_name() == data:
            task.cancel()
            await query_message.edit_text("Monitoring usunięty")

    user_tasks = [task for task in user_tasks if not task.cancelled()]
    user_data["user_tasks"] = user_tasks

    if not user_tasks:
        await query_message.reply_text("Brak aktywnych monitoringów")
        return ConversationHandler.END

    return CANCEL_MONITORING
