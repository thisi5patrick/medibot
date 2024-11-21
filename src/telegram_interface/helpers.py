from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

YES_ANSWER = "yes"
NO_ANSWER = "no"


def prepare_date_keyboard(day: int, month: int, year: int) -> InlineKeyboardMarkup:
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
            InlineKeyboardButton("Done", callback_data="date_done"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def prepare_time_keyboard(hour: int, minute: int) -> InlineKeyboardMarkup:
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
            InlineKeyboardButton("Done", callback_data="time_done"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def extract_dates_from_user_data(user_data: dict[str, Any]) -> tuple[str, str, str, str]:
    selected_from_day = user_data["selected_from_day"]
    selected_from_month = user_data["selected_from_month"]
    selected_from_year = user_data["selected_from_year"]
    selected_from_date = f"{selected_from_day:02d}-{selected_from_month:02d}-{selected_from_year}"

    selected_from_hour = user_data["selected_from_hour"]
    selected_from_minute = user_data["selected_from_minute"]
    selected_from_time = f"{selected_from_hour:02d}:{selected_from_minute:02d}"

    selected_to_day = user_data["selected_to_day"]
    selected_to_month = user_data["selected_to_month"]
    selected_to_year = user_data["selected_to_year"]
    selected_to_date = f"{selected_to_day:02d}-{selected_to_month:02d}-{selected_to_year}"

    selected_to_hour = user_data["selected_to_hour"]
    selected_to_minute = user_data["selected_to_minute"]
    selected_to_time = f"{selected_to_hour:02d}:{selected_to_minute:02d}"

    return selected_from_date, selected_from_time, selected_to_date, selected_to_time
