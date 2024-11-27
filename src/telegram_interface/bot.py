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
    get_location_from_buttons,
    get_location_from_input,
    get_specialization_from_buttons,
    get_specialization_from_input,
    handle_date_from_selection,
    handle_date_to_selection,
    handle_time_from_selection,
    handle_time_to_selection,
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
    GET_LOCATION,
    GET_SPECIALIZATION,
    PROVIDE_PASSWORD,
    PROVIDE_USERNAME,
    READ_CLINIC,
    READ_CREATE_MONITORING,
    READ_DATE_FROM,
    READ_DATE_TO,
    READ_DOCTOR,
    READ_LOCATION,
    READ_SPECIALIZATION,
    READ_TIME_FROM,
    READ_TIME_TO,
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
                READ_DATE_FROM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_from_selection),
                    CallbackQueryHandler(handle_date_from_selection),
                ],
                READ_TIME_FROM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_from_selection),
                    CallbackQueryHandler(handle_time_from_selection),
                ],
                READ_DATE_TO: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_to_selection),
                    CallbackQueryHandler(handle_date_to_selection),
                ],
                READ_TIME_TO: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_to_selection),
                    CallbackQueryHandler(handle_time_to_selection),
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
