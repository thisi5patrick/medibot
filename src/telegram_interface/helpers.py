import logging
import os
from calendar import monthrange
from datetime import date, datetime
from typing import Literal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.locale_handler import _
from src.medicover_client.client import FilterDataType
from src.telegram_interface.user_data import UserDataDataclass

logger = logging.getLogger(__name__)

YES_ANSWER = "yes"
NO_ANSWER = "no"
DATE_INCREMENT = 1
MINUTE_INCREMENT = 15
HOUR_INCREMENT = 1
MAX_MINUTES = 60
MAX_HOURS = 24
MAX_MONTHS = 12


def prepare_date_keyboard(day: int, month: int, year: int, language: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("↑", callback_data="day_up"),
            InlineKeyboardButton("↑", callback_data="month_up"),
            InlineKeyboardButton("↑", callback_data="year_up"),
        ],
        [
            InlineKeyboardButton(f"{day:02d}", callback_data="ignore"),
            InlineKeyboardButton(f"{month:02d}", callback_data="ignore"),
            InlineKeyboardButton(f"{year}", callback_data="ignore"),
        ],
        [
            InlineKeyboardButton("↓", callback_data="day_down"),
            InlineKeyboardButton("↓", callback_data="month_down"),
            InlineKeyboardButton("↓", callback_data="year_down"),
        ],
        [
            InlineKeyboardButton(_("Done", language), callback_data="date_done"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def prepare_date_selection(
    user_data: UserDataDataclass, booking_date_type: Literal["from_date", "to_date"]
) -> InlineKeyboardMarkup:
    if booking_date_type == "from_date":
        day = date.today().day
        month = date.today().month
        year = date.today().year
    else:
        from_date_values = user_data["bookings"][user_data["current_booking_number"]]["from_date"]
        day = from_date_values["day"]
        month = from_date_values["month"]
        year = from_date_values["year"]

    current_booking_number = user_data["current_booking_number"]

    user_data["bookings"][current_booking_number][booking_date_type] = {"day": day, "month": month, "year": year}

    reply_markup = prepare_date_keyboard(day, month, year, language=user_data["language"])

    return reply_markup


def prepare_time_keyboard(hour: int, minute: int, language: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("↑", callback_data="hour_up"),
            InlineKeyboardButton("↑", callback_data="minute_up"),
        ],
        [
            InlineKeyboardButton(f"{hour:02d}", callback_data="ignore"),
            InlineKeyboardButton(f"{minute:02d}", callback_data="ignore"),
        ],
        [
            InlineKeyboardButton("↓", callback_data="hour_down"),
            InlineKeyboardButton("↓", callback_data="minute_down"),
        ],
        [
            InlineKeyboardButton(_("Done", language), callback_data="time_done"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def prepare_specialization_keyboard(user_data: UserDataDataclass) -> InlineKeyboardMarkup:
    specializations = user_data["history"]["specializations"]
    if specializations:
        specializations_buttons = [
            [
                InlineKeyboardButton(
                    specialization["specialization_name"], callback_data=str(specialization["specialization_id"])
                )
            ]
            for specialization in specializations
        ]
    else:
        specializations_buttons = []
    keyboard = [
        *specializations_buttons,
    ]
    return InlineKeyboardMarkup(keyboard)


def prepare_clinic_keyboard(user_data: UserDataDataclass, specialization_id: str) -> InlineKeyboardMarkup:
    clinics = user_data["history"]["clinics"].get(specialization_id)
    if clinics:
        clinic_buttons = [
            [InlineKeyboardButton(clinic["clinic_name"], callback_data=str(clinic["clinic_id"]))] for clinic in clinics
        ]
    else:
        clinic_buttons = []
    keyboard = [
        [InlineKeyboardButton(_("Any-her", user_data["language"]), callback_data="any")],
        *clinic_buttons,
    ]
    return InlineKeyboardMarkup(keyboard)


def prepare_doctor_keyboard(user_data: UserDataDataclass, specialization_id: str) -> InlineKeyboardMarkup:
    doctors = user_data["history"]["doctors"].get(specialization_id)
    if doctors:
        doctor_buttons = [
            [InlineKeyboardButton(doctor["doctor_name"], callback_data=str(doctor["doctor_id"]))] for doctor in doctors
        ]
    else:
        doctor_buttons = []
    keyboard = [
        [InlineKeyboardButton(_("Any-him", user_data["language"]), callback_data="any")],
        *doctor_buttons,
    ]
    return InlineKeyboardMarkup(keyboard)


def adjust_day(
    user_data: UserDataDataclass, increment: int, booking_date_parameter: Literal["from_date", "to_date"]
) -> None:
    current_booking_number = user_data["current_booking_number"]

    day = user_data["bookings"][current_booking_number][booking_date_parameter]["day"]
    month = user_data["bookings"][current_booking_number][booking_date_parameter]["month"]
    year = user_data["bookings"][current_booking_number][booking_date_parameter]["year"]
    max_day = monthrange(year, month)[1]
    day = max(1, min(day + increment, max_day))
    user_data["bookings"][current_booking_number][booking_date_parameter]["day"] = day


def adjust_month(
    user_data: UserDataDataclass, increment: int, booking_date_parameter: Literal["from_date", "to_date"]
) -> None:
    current_booking_number = user_data["current_booking_number"]

    month = user_data["bookings"][current_booking_number][booking_date_parameter]["month"]
    month += increment
    if month > MAX_MONTHS:
        month = 1
    elif month < 1:
        month = 12
    user_data["bookings"][current_booking_number][booking_date_parameter]["month"] = month
    adjust_day(user_data, 0, booking_date_parameter)


def adjust_year(
    user_data: UserDataDataclass, increment: int, booking_date_parameter: Literal["from_date", "to_date"]
) -> None:
    current_booking_number = user_data["current_booking_number"]

    year = user_data["bookings"][current_booking_number][booking_date_parameter]["year"]
    year += increment
    if year >= datetime.now().year or increment > 0:
        user_data["bookings"][current_booking_number][booking_date_parameter]["year"] = year
        adjust_day(user_data, 0, booking_date_parameter)


def handle_date_selection(
    user_action: str, user_data: UserDataDataclass, booking_date_parameter: Literal["from_date", "to_date"]
) -> str | None:
    current_booking_number = user_data["current_booking_number"]

    if user_action == "day_up":
        adjust_day(user_data, DATE_INCREMENT, booking_date_parameter)
    elif user_action == "day_down":
        adjust_day(user_data, -DATE_INCREMENT, booking_date_parameter)
    elif user_action == "month_up":
        adjust_month(user_data, DATE_INCREMENT, booking_date_parameter)
    elif user_action == "month_down":
        adjust_month(user_data, -DATE_INCREMENT, booking_date_parameter)
    elif user_action == "year_up":
        adjust_year(user_data, DATE_INCREMENT, booking_date_parameter)
    elif user_action == "year_down":
        adjust_year(user_data, -DATE_INCREMENT, booking_date_parameter)
    elif user_action == "date_done":
        selected_day = user_data["bookings"][current_booking_number][booking_date_parameter]["day"]
        selected_month = user_data["bookings"][current_booking_number][booking_date_parameter]["month"]
        selected_year = user_data["bookings"][current_booking_number][booking_date_parameter]["year"]
        selected_date = f"{selected_day:02d}-{selected_month:02d}-{selected_year}"

        return selected_date
    return None


def update_date_selection_buttons(
    user_data: UserDataDataclass, booking_date_parameter: Literal["from_date", "to_date"]
) -> InlineKeyboardMarkup:
    current_booking_number = user_data["current_booking_number"]
    day = user_data["bookings"][current_booking_number][booking_date_parameter]["day"]
    month = user_data["bookings"][current_booking_number][booking_date_parameter]["month"]
    year = user_data["bookings"][current_booking_number][booking_date_parameter]["year"]

    return prepare_date_keyboard(day, month, year, language=user_data["language"])


def adjust_minute(
    user_data: UserDataDataclass, increment: int, booking_time_parameter: Literal["from_time", "to_time"]
) -> None:
    current_booking_number = user_data["current_booking_number"]

    minute = user_data["bookings"][current_booking_number][booking_time_parameter]["minute"]
    minute += increment
    if minute >= MAX_MINUTES:
        minute = 0
    elif minute < 0:
        minute = 45
    user_data["bookings"][current_booking_number][booking_time_parameter]["minute"] = minute


def adjust_hour(
    user_data: UserDataDataclass, increment: int, booking_time_parameter: Literal["from_time", "to_time"]
) -> None:
    current_booking_number = user_data["current_booking_number"]

    hour = user_data["bookings"][current_booking_number][booking_time_parameter]["hour"]
    hour += increment
    if hour >= MAX_HOURS:
        hour = 0
    elif hour < 0:
        hour = 23
    user_data["bookings"][current_booking_number][booking_time_parameter]["hour"] = hour


def handle_time_selection(
    user_action: str, user_data: UserDataDataclass, booking_time_parameter: Literal["from_time", "to_time"]
) -> str | None:
    current_booking_number = user_data["current_booking_number"]

    if user_action == "minute_up":
        adjust_minute(user_data, MINUTE_INCREMENT, booking_time_parameter)
    elif user_action == "minute_down":
        adjust_minute(user_data, -MINUTE_INCREMENT, booking_time_parameter)
    elif user_action == "hour_up":
        adjust_hour(user_data, HOUR_INCREMENT, booking_time_parameter)
    elif user_action == "hour_down":
        adjust_hour(user_data, -HOUR_INCREMENT, booking_time_parameter)
    elif user_action == "time_done":
        selected_hour = user_data["bookings"][current_booking_number][booking_time_parameter]["hour"]
        selected_minute = user_data["bookings"][current_booking_number][booking_time_parameter]["minute"]
        selected_time = f"{selected_hour:02d}:{selected_minute:02d}"

        return selected_time
    return None


def update_time_selection_buttons(
    user_data: UserDataDataclass, booking_time_parameter: Literal["from_time", "to_time"]
) -> InlineKeyboardMarkup:
    current_booking_number = user_data["current_booking_number"]

    hour = user_data["bookings"][current_booking_number][booking_time_parameter]["hour"]
    minute = user_data["bookings"][current_booking_number][booking_time_parameter]["minute"]

    return prepare_time_keyboard(hour, minute, language=user_data["language"])


def get_summary_text(user_data: UserDataDataclass, booking_number: int | None = None) -> str:
    if booking_number is None:
        booking_number = user_data["current_booking_number"]

    location = user_data["bookings"][booking_number]["location"]
    specialization = user_data["bookings"][booking_number]["specialization"]
    clinic = user_data["bookings"][booking_number]["clinic"]
    doctor = user_data["bookings"][booking_number]["doctor"]
    from_date = user_data["bookings"][booking_number]["from_date"]
    from_date_str = f"{from_date['day']:02d}-{from_date['month']:02d}-{from_date['year']:02d}"
    from_time = user_data["bookings"][booking_number]["from_time"]
    from_time_str = f"{from_time['hour']:02d}:{from_time['minute']:02d}"
    to_date = user_data["bookings"][booking_number]["to_date"]
    to_date_str = f"{to_date['day']:02d}-{to_date['month']:02d}-{to_date['year']:02d}"
    to_time = user_data["bookings"][booking_number]["to_time"]
    to_time_str = f"{to_time['hour']:02d}:{to_time['minute']:02d}"

    summary_text = f"{_("City:",user_data["language"])} {location['location_name']}\n"
    summary_text += f"{_("Specialization:",user_data["language"])} {specialization['specialization_name']}\n"
    summary_text += f"{_("Clinic:",user_data["language"])} {clinic['clinic_name']}\n"
    summary_text += f"{_("Doctor:",user_data["language"])} {doctor['doctor_name']}\n"
    summary_text += f"{_("Date from:",user_data["language"])} {from_date_str}\n"
    summary_text += f"{_("Time from:",user_data["language"])} {from_time_str}\n"
    summary_text += f"{_("Date before:",user_data["language"])} {to_date_str}\n"
    summary_text += f"{_("Time before:",user_data["language"])} {to_time_str}\n"

    return summary_text


async def prepare_summary(user_data: UserDataDataclass, update_message: Message) -> None:
    summary_text = get_summary_text(user_data)

    keyboard = [
        [InlineKeyboardButton("Tak", callback_data=YES_ANSWER)],
        [InlineKeyboardButton("Nie", callback_data=NO_ANSWER)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update_message.reply_text(
        f"\u2754 {summary_text}\nPodsumowanie jest prawidłowe?",
        reply_markup=reply_markup,
    )


def match_input_to_filter(user_text: str, filters_data: list[FilterDataType]) -> list[FilterDataType]:
    selected_filters = []
    for available_filter in filters_data:
        if user_text.lower() in available_filter["value"].lower():
            selected_filters.append(available_filter)
    return selected_filters


async def send_to_dev_message(context: ContextTypes.DEFAULT_TYPE, message: str) -> None:
    admin_chat_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
    if admin_chat_id is None:
        logger.warning("TELEGRAM_ADMIN_CHAT_ID is not set. Skipping sending to dev chat.")
        return
    await context.bot.send_message(
        chat_id=admin_chat_id,
        text=message,
        parse_mode=ParseMode.HTML,
    )
