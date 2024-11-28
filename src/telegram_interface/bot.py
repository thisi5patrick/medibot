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
    PicklePersistence,
    filters,
)

from src.telegram_interface.commands.find_appointments import (
    find_appointments,
    get_clinic_from_buttons,
    get_clinic_from_input,
    get_doctor_from_buttons,
    get_doctor_from_input,
    get_from_date_from_buttons,
    get_from_date_from_input,
    get_from_time_from_buttons,
    get_from_time_from_input,
    get_location_from_buttons,
    get_location_from_input,
    get_specialization_from_buttons,
    get_specialization_from_input,
    get_to_date_from_buttons,
    get_to_date_from_input,
    get_to_time_from_buttons,
    get_to_time_from_input,
    read_clinic,
    read_create_monitoring,
    read_doctor,
    read_location,
    read_specialization,
    verify_summary,
)
from src.telegram_interface.commands.login import login, password, username
from src.telegram_interface.commands.monitorings import active_monitorings_command, cancel_monitoring
from src.telegram_interface.states import (
    CANCEL_MONITORING,
    GET_CLINIC,
    GET_DOCTOR,
    GET_FROM_DATE,
    GET_FROM_TIME,
    GET_LOCATION,
    GET_SPECIALIZATION,
    GET_TO_DATE,
    GET_TO_TIME,
    PROVIDE_PASSWORD,
    PROVIDE_USERNAME,
    READ_CLINIC,
    READ_CREATE_MONITORING,
    READ_DOCTOR,
    READ_LOCATION,
    READ_SPECIALIZATION,
    VERIFY_SUMMARY,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


async def post_init(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("/login", "Login to Medicover"),
            BotCommand("/monitor", "Create a new appointment monitor"),
            BotCommand("/active_monitorings", "Show all your appointment monitorings"),
            BotCommand("/help", "Show help message"),
        ]
    )


class TelegramBot:
    def __init__(self) -> None:
        persistence = PicklePersistence(filepath=os.environ["TELEGRAM_PERSISTENCE_PICKLE_FILE_PATH"])

        self.bot = (
            ApplicationBuilder()
            .token(os.environ["TELEGRAM_BOT_TOKEN"])
            .post_init(post_init)
            .persistence(persistence)
            .build()
        )
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
                GET_LOCATION: [
                    CallbackQueryHandler(get_location_from_buttons),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_location_from_input),
                ],
                READ_LOCATION: [
                    CallbackQueryHandler(read_location),
                ],
                GET_SPECIALIZATION: [
                    CallbackQueryHandler(get_specialization_from_buttons),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_specialization_from_input),
                ],
                READ_SPECIALIZATION: [
                    CallbackQueryHandler(read_specialization),
                ],
                GET_CLINIC: [
                    CallbackQueryHandler(get_clinic_from_buttons),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_clinic_from_input),
                ],
                READ_CLINIC: [
                    CallbackQueryHandler(read_clinic),
                ],
                GET_DOCTOR: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_doctor_from_input),
                    CallbackQueryHandler(get_doctor_from_buttons),
                ],
                READ_DOCTOR: [
                    CallbackQueryHandler(read_doctor),
                ],
                GET_FROM_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_from_date_from_input),
                    CallbackQueryHandler(get_from_date_from_buttons),
                ],
                GET_FROM_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_from_time_from_input),
                    CallbackQueryHandler(get_from_time_from_buttons),
                ],
                GET_TO_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_to_date_from_input),
                    CallbackQueryHandler(get_to_date_from_buttons),
                ],
                GET_TO_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_to_time_from_input),
                    CallbackQueryHandler(get_to_time_from_buttons),
                ],
                VERIFY_SUMMARY: [
                    CallbackQueryHandler(verify_summary),
                ],
                READ_CREATE_MONITORING: [
                    CallbackQueryHandler(read_create_monitoring),
                ],
            },
            fallbacks=[],
        )

        my_monitors_handler = ConversationHandler(
            entry_points=[CommandHandler("active_monitorings", active_monitorings_command)],
            states={
                CANCEL_MONITORING: [
                    CallbackQueryHandler(cancel_monitoring),
                ]
            },
            fallbacks=[],
        )

        self.bot.add_handler(login_handler)
        self.bot.add_handler(monitor_handler)
        self.bot.add_handler(my_monitors_handler)

        self.bot.run_polling()
