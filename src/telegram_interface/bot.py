import logging
import os
from typing import Any

from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.telegram_interface.find_appointments_command import (
    find_appointments,
    get_location,
    get_specialization,
    handle_clinic_text,
    handle_date_from_selection,
    handle_doctor_text,
    handle_selected_clinic,
    handle_selected_doctor,
    handle_time_from_selection,
    read_location,
    read_specialization,
)
from src.telegram_interface.login_command import login, password, username
from src.telegram_interface.states import (
    GET_LOCATION,
    GET_SPECIALIZATION,
    PROVIDE_PASSWORD,
    PROVIDE_USERNAME,
    READ_CLINIC,
    READ_DATE_FROM,
    READ_DOCTOR,
    READ_LOCATION,
    READ_SPECIALIZATION,
    READ_TIME_FROM,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


async def post_init(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("/login", "Login to Medicover"),
            BotCommand("/monitor", "Create a new appointment monitor"),
            BotCommand("/help", "Show help message"),
        ]
    )


class TelegramBot:
    def __init__(self) -> None:
        self.bot = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).post_init(post_init).build()
        login_handler = ConversationHandler(
            entry_points=[CommandHandler("login", login)],
            states={
                PROVIDE_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username)],
                PROVIDE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password)],
            },
            fallbacks=[],
        )

        monitor_handler = ConversationHandler(
            entry_points=[CommandHandler("monitor", find_appointments)],
            states={
                GET_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_location)],
                READ_LOCATION: [CallbackQueryHandler(read_location)],
                GET_SPECIALIZATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_specialization)],
                READ_SPECIALIZATION: [CallbackQueryHandler(read_specialization)],
                READ_CLINIC: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_clinic_text),
                    CallbackQueryHandler(handle_selected_clinic),
                ],
                READ_DOCTOR: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doctor_text),
                    CallbackQueryHandler(handle_selected_doctor),
                ],
                READ_DATE_FROM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_from_selection),
                    CallbackQueryHandler(handle_date_from_selection),
                ],
                READ_TIME_FROM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_from_selection),
                    CallbackQueryHandler(handle_time_from_selection),
                ],
            },
            fallbacks=[],
        )

        self.bot.add_handler(login_handler)
        self.bot.add_handler(monitor_handler)

        self.bot.run_polling()
