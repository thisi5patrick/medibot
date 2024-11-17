from telegram import InlineKeyboardButton, InlineKeyboardMarkup


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
