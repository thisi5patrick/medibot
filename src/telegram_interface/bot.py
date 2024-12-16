import logging
import os
from pathlib import Path
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

from src.telegram_interface.commands.active_monitorings import active_monitorings_entrypoint, cancel_monitoring
from src.telegram_interface.commands.future_appointments import future_appointments_entrypoint
from src.telegram_interface.commands.login import login, password, username
from src.telegram_interface.commands.new_monitoring import (
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
    new_monitoring_entrypoint,
    read_clinic,
    read_create_monitoring,
    read_doctor,
    read_location,
    read_specialization,
    verify_summary,
)
from src.telegram_interface.commands.settings import (
    clear_search_history_entrypoint,
    read_change_language,
    settings_entrypoint,
    show_change_language,
)
from src.telegram_interface.commands.start import start_entrypoint
from src.telegram_interface.states import (
    CANCEL_MONITORING,
    CHANGE_LANGUAGE,
    CLEAR_SEARCH_HISTORY,
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
    READ_CHANGE_LANGUAGE,
    READ_CLINIC,
    READ_CREATE_MONITORING,
    READ_DOCTOR,
    READ_LOCATION,
    READ_SPECIALIZATION,
    SELECTING_SETTING,
    SHOW_CHANGE_LANGUAGE,
    VERIFY_SUMMARY,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


async def post_init(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("/start", "Start the bot"),
            BotCommand("/login", "Login to Medicover"),
            BotCommand("/new_monitoring", "Create a new appointment monitoring"),
            BotCommand("/active_monitorings", "Show all your appointment monitorings"),
            BotCommand("/future_appointments", "Show your future appointments"),
            BotCommand("/settings", "Change the bot settings"),
            BotCommand("/help", "Show help message"),
        ]
    )


async def end_current_command(*args: Any, **kwargs: Any) -> int:
    return ConversationHandler.END


class TelegramBot:
    def __init__(self) -> None:
        source_folder = Path(__file__).resolve().parent.parent.parent
        pickle_file_path = Path(os.environ["TELEGRAM_PERSISTENCE_PICKLE_FILE_PATH"])
        file_path = source_folder / pickle_file_path

        persistence = PicklePersistence(filepath=file_path)

        self.bot = (
            ApplicationBuilder()
            .token(os.environ["TELEGRAM_BOT_TOKEN"])
            .post_init(post_init)
            .persistence(persistence)
            .build()
        )

        start_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start_entrypoint)],
            states={},
            fallbacks=[],
        )

        login_handler = ConversationHandler(
            entry_points=[CommandHandler("login", login)],
            states={
                PROVIDE_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username)],
                PROVIDE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password)],
            },
            fallbacks=[
                CommandHandler("start", end_current_command),
                CommandHandler("new_monitoring", end_current_command),
                CommandHandler("active_monitorings", end_current_command),
                CommandHandler("settings", end_current_command),
                CommandHandler("help", end_current_command),
            ],
            allow_reentry=True,
        )

        new_monitoring_handler = ConversationHandler(
            entry_points=[CommandHandler("new_monitoring", new_monitoring_entrypoint)],
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
            fallbacks=[
                CommandHandler("start", end_current_command),
                CommandHandler("login", end_current_command),
                CommandHandler("active_monitorings", end_current_command),
                CommandHandler("settings", end_current_command),
                CommandHandler("help", end_current_command),
            ],
            allow_reentry=True,
        )

        active_monitorings = ConversationHandler(
            entry_points=[CommandHandler("active_monitorings", active_monitorings_entrypoint)],
            states={
                CANCEL_MONITORING: [
                    CallbackQueryHandler(cancel_monitoring),
                ]
            },
            fallbacks=[
                CommandHandler("start", end_current_command),
                CommandHandler("login", end_current_command),
                CommandHandler("new_monitoring", end_current_command),
                CommandHandler("settings", end_current_command),
                CommandHandler("help", end_current_command),
            ],
            allow_reentry=True,
        )

        clear_search_history_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(clear_search_history_entrypoint, pattern=f"^{CLEAR_SEARCH_HISTORY}$")],
            states={},
            fallbacks=[
                CommandHandler("start", end_current_command),
                CommandHandler("login", end_current_command),
                CommandHandler("new_monitoring", end_current_command),
                CommandHandler("active_monitorings", end_current_command),
                CommandHandler("settings", end_current_command),
                CommandHandler("help", end_current_command),
            ],
            allow_reentry=True,
        )

        change_language_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(show_change_language, pattern=f"^{CHANGE_LANGUAGE}$")],
            states={
                SHOW_CHANGE_LANGUAGE: [
                    CallbackQueryHandler(show_change_language),
                ],
                READ_CHANGE_LANGUAGE: [
                    CallbackQueryHandler(read_change_language),
                ],
            },
            fallbacks=[
                CommandHandler("start", end_current_command),
                CommandHandler("login", end_current_command),
                CommandHandler("new_monitoring", end_current_command),
                CommandHandler("active_monitorings", end_current_command),
                CommandHandler("settings", end_current_command),
                CommandHandler("help", end_current_command),
            ],
            allow_reentry=True,
        )

        settings_handler = ConversationHandler(
            entry_points=[CommandHandler("settings", settings_entrypoint)],
            states={
                SELECTING_SETTING: [
                    change_language_handler,
                    clear_search_history_handler,
                    # More settings
                ],
            },
            fallbacks=[
                CommandHandler("start", end_current_command),
                CommandHandler("login", end_current_command),
                CommandHandler("new_monitoring", end_current_command),
                CommandHandler("active_monitorings", end_current_command),
                CommandHandler("help", end_current_command),
            ],
            allow_reentry=True,
        )

        future_appointments_handler = ConversationHandler(
            entry_points=[CommandHandler("future_appointments", future_appointments_entrypoint)],
            states={},
            fallbacks=[
                CommandHandler("start", end_current_command),
                CommandHandler("login", end_current_command),
                CommandHandler("new_monitoring", end_current_command),
                CommandHandler("active_monitorings", end_current_command),
                CommandHandler("settings", end_current_command),
                CommandHandler("help", end_current_command),
            ],
            allow_reentry=True,
        )

        self.bot.add_handler(start_handler, 0)
        self.bot.add_handler(login_handler, 1)
        self.bot.add_handler(new_monitoring_handler, 2)
        self.bot.add_handler(active_monitorings, 3)
        self.bot.add_handler(settings_handler, 4)
        self.bot.add_handler(future_appointments_handler, 5)

        self.bot.run_polling()
