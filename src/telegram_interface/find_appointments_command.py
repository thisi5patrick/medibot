import json
import logging
from calendar import monthrange
from datetime import date, datetime
from typing import Any, cast

import telegram
from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from telegram.ext import ContextTypes, ConversationHandler

from src.client import MedicoverClient
from src.telegram_interface.states import (
    GET_LOCATION,
    GET_SPECIALIZATION,
    READ_CLINIC,
    READ_DATE_FROM,
    READ_DOCTOR,
    READ_LOCATION,
    READ_SPECIALIZATION,
    READ_TIME_FROM,
)

logger = logging.getLogger(__name__)


async def find_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    user_data = cast(dict[Any, Any], context.user_data)

    client: MedicoverClient | None = user_data.get("medicover_client")
    if not client:
        await update.message.reply_text("Please log in first.")
        return ConversationHandler.END

    await update.message.reply_text("Podaj fragment szukanego miasta")

    return GET_LOCATION


async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END
    user_data = cast(dict[Any, Any], context.user_data)

    client: MedicoverClient = user_data["medicover_client"]
    location_input = update.message.text
    locations = client.get_region(location_input)

    if locations:
        user_data["locations"] = {str(loc["id"]): loc for loc in locations}

        keyboard = [[InlineKeyboardButton(loc["text"], callback_data=json.dumps(loc))] for loc in locations]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Wybierz miasto z listy:", reply_markup=reply_markup)

        return READ_LOCATION

    await update.message.reply_text("Nie znaleziono miasta. Wpisz ponownie.")
    return GET_LOCATION


async def read_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[Any, Any], context.user_data)

    query = cast(CallbackQuery, update.callback_query)

    await query.answer()

    data = json.loads(cast(str, query.data))
    location_id = data["id"]
    location_text = data["text"]

    user_data["location_id"] = location_id
    await query.edit_message_text(f"\u2705 Wybrano miasto: {location_text}")

    query_message = cast(Message, query.message)

    await query_message.reply_text("Wpisz fragment szukanej specjalizacji")

    return GET_SPECIALIZATION


async def get_specialization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[Any, Any], context.user_data)
    update_message = cast(Message, update.message)

    client: MedicoverClient = user_data["medicover_client"]
    specialization_input = update_message.text

    specializations = client.get_specialization(cast(str, specialization_input), user_data["location_id"])

    if specializations:
        user_data["specializations"] = {str(spec["id"]): spec for spec in specializations}

        keyboard = [[InlineKeyboardButton(spec["text"], callback_data=str(spec["id"]))] for spec in specializations]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update_message.reply_text("Wybierz specjalizację:", reply_markup=reply_markup)

        return READ_SPECIALIZATION

    await update_message.reply_text("Nie znaleziono specjalizacji. Wpisz ponownie.")
    return GET_SPECIALIZATION


async def read_specialization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(dict[Any, Any], context.user_data)

    await query.answer()

    specialization_id = query.data
    specializations = user_data.get("specializations", {})
    selected_spec = specializations.get(specialization_id)

    specialization_text = selected_spec["text"]

    user_data["specialization_id"] = specialization_id

    await query.edit_message_text(text=f"\u2705 Wybrano specjalizacje: {specialization_text}")

    keyboard = [[InlineKeyboardButton("Jakakolwiek", callback_data="any")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query_message = cast(Message, query.message)
    await query_message.reply_text("Wybierz klinikę albo podaj własną:", reply_markup=reply_markup)

    return READ_CLINIC


async def handle_clinic_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[Any, Any], context.user_data)
    update_message = cast(Message, update.message)

    client: MedicoverClient = user_data["medicover_client"]
    location_id = user_data["location_id"]
    specialization_id = user_data["specialization_id"]

    user_input = cast(str, update_message.text)

    clinics = client.get_clinic(user_input, location_id, specialization_id)

    if clinics:
        user_data["clinics"] = {str(clinic["id"]): clinic for clinic in clinics}

        keyboard = [[InlineKeyboardButton(clinic["text"], callback_data=str(clinic["id"]))] for clinic in clinics]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update_message.reply_text("Wybierz klinikę z listy:", reply_markup=reply_markup)
        return READ_CLINIC

    await update_message.reply_text("Nie znaleziono kliniki. Wpisz ponownie.")
    return READ_CLINIC


async def handle_selected_clinic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(dict[Any, Any], context.user_data)

    await query.answer()

    clinic_id = query.data
    clinics = user_data.get("clinics", {})
    selected_clinic = clinics.get(clinic_id)
    if not selected_clinic:
        selected_clinic = "jakakolwiek"
    else:
        selected_clinic = selected_clinic["text"]
        user_data["clinic_id"] = clinic_id

    await query.edit_message_text(f"\u2705 Wybrano: {selected_clinic}")

    keyboard = [[InlineKeyboardButton("Jakikolwiek", callback_data="any")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query_message = cast(Message, query.message)
    await query_message.reply_text("Wybierz lekarza albo podaj:", reply_markup=reply_markup)

    return READ_DOCTOR


async def handle_doctor_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    update_message = cast(Message, update.message)
    user_data = cast(dict[Any, Any], context.user_data)

    client: MedicoverClient = user_data["medicover_client"]
    location_id: int = user_data["location_id"]
    specialization_id: int = user_data["specialization_id"]
    clinic_id: int | None = user_data.get("clinic_id")

    user_input = cast(str, update_message.text)

    doctors = client.get_doctor(user_input, location_id, specialization_id, clinic_id)

    if doctors:
        user_data["doctors"] = {str(doctor["id"]): doctor for doctor in doctors}

        keyboard = [[InlineKeyboardButton(doctor["text"], callback_data=str(doctor["id"]))] for doctor in doctors]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update_message.reply_text("Wybierz lekarza z listy:", reply_markup=reply_markup)
        return READ_DOCTOR
    else:
        await update_message.reply_text("Nie znaleziono lekarza. Wpisz ponownie.")
        return None


async def handle_selected_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(dict[Any, Any], context.user_data)

    await query.answer()

    doctor_id = query.data
    doctors = user_data.get("doctors", {})
    selected_doctor = doctors.get(doctor_id)
    if selected_doctor is None:
        selected_doctor = "Jakikolwiek"
    else:
        selected_doctor = selected_doctor["text"]
        user_data["doctor_id"] = doctor_id

    await query.edit_message_text(f"\u2705 Wybrano lekarza: {selected_doctor}")

    day = date.today().day
    month = date.today().month
    year = date.today().year

    user_data["selected_from_day"] = day
    user_data["selected_from_month"] = month
    user_data["selected_from_year"] = year

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

    reply_markup = InlineKeyboardMarkup(keyboard)

    query_message = cast(Message, query.message)
    await query_message.reply_text(
        "Wybierz datę albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
    )

    return READ_DATE_FROM


async def update_date_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = cast(dict[Any, Any], context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    day = user_data["selected_from_day"]
    month = user_data["selected_from_month"]
    year = user_data["selected_from_year"]

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

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            "Wybierz datę albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024:", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        return None


async def prepare_time_from_selection(user_data: dict[str, Any]) -> InlineKeyboardMarkup:
    selected_hour = 7
    selected_minute = 0

    user_data["selected_from_hour"] = selected_hour
    user_data["selected_from_minute"] = selected_minute

    keyboard = [
        [
            InlineKeyboardButton("↑", callback_data="hour_up"),
            InlineKeyboardButton("↑", callback_data="minute_up"),
        ],
        [
            InlineKeyboardButton(f"{selected_hour:02d}", callback_data="ignore"),
            InlineKeyboardButton(f"{selected_minute:02d}", callback_data="ignore"),
        ],
        [
            InlineKeyboardButton("↓", callback_data="hour_down"),
            InlineKeyboardButton("↓", callback_data="minute_down"),
        ],
        [
            InlineKeyboardButton("Done", callback_data="time_done"),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    return reply_markup


async def handle_date_from_selection_with_buttons(
    user_data: dict[str, Any], query: CallbackQuery, data: str
) -> int | None:
    if data == "day_up":
        selected_day = user_data["selected_from_day"]
        selected_month = user_data["selected_from_month"]
        selected_year = user_data["selected_from_year"]
        selected_day = min(selected_day + 1, monthrange(selected_year, selected_month)[1])
        user_data["selected_from_day"] = selected_day
    elif data == "day_down":
        selected_day = user_data["selected_from_day"]
        selected_day = max(selected_day - 1, 1)
        user_data["selected_from_day"] = selected_day
    elif data == "month_up":
        selected_month = user_data["selected_from_month"]
        selected_month = min(selected_month + 1, 12)
        selected_day = user_data["selected_from_day"]
        selected_day = min(selected_day, monthrange(user_data["selected_from_year"], selected_month)[1])
        user_data["selected_from_month"] = selected_month
        user_data["selected_from_day"] = selected_day
    elif data == "month_down":
        selected_month = user_data["selected_from_month"]
        selected_month = max(selected_month - 1, 1)
        selected_day = user_data["selected_from_day"]
        selected_day = min(selected_day, monthrange(user_data["selected_from_year"], selected_month)[1])
        user_data["selected_from_month"] = selected_month
        user_data["selected_from_day"] = selected_day
    elif data == "year_up":
        selected_year = user_data["selected_from_year"]
        selected_year += 1
        selected_day = user_data["selected_from_day"]
        selected_day = min(selected_day, monthrange(selected_year, user_data["selected_from_month"])[1])
        user_data["selected_from_year"] = selected_year
        user_data["selected_from_day"] = selected_day
    elif data == "year_down":
        selected_year = user_data["selected_from_year"]
        if selected_year > datetime.now().year:
            selected_year -= 1
            selected_day = user_data["selected_from_day"]
            selected_day = min(selected_day, monthrange(selected_year, user_data["selected_from_month"])[1])
            user_data["selected_from_year"] = selected_year
            user_data["selected_from_day"] = selected_day
    elif data == "date_done":
        selected_day = user_data["selected_from_day"]
        selected_month = user_data["selected_from_month"]
        selected_year = user_data["selected_from_year"]
        selected_date = f"{selected_day:02d}-{selected_month:02d}-{selected_year}"

        await query.edit_message_text(f"\u2705 Wybrano datę od: {selected_date}")

        reply_markup = await prepare_time_from_selection(user_data)

        query_message = cast(Message, query.message)
        await query_message.reply_text(
            "Wybierz godzinę albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
        )

        return READ_TIME_FROM

    return None


async def handle_date_from_selection_with_text(
    update_message: Message, data: str, user_data: dict[str, Any]
) -> int | None:
    try:
        date = datetime.strptime(data, "%d-%m-%Y")
        user_data["selected_from_day"] = date.day
        user_data["selected_from_month"] = date.month
        user_data["selected_from_year"] = date.year

        await update_message.reply_text(f"\u2705 Wybrano datę od: {data}")

        reply_markup = await prepare_time_from_selection(user_data)

        await update_message.reply_text(
            "Wybierz godzinę albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
        )
        return READ_TIME_FROM
    except ValueError:
        await update_message.reply_text("Invalid date format. Please use DD-MM-YYYY.")
        return None


async def handle_date_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[Any, Any], context.user_data)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = cast(str, query.data)

        return_view = await handle_date_from_selection_with_buttons(user_data, query, data)
        if return_view is not None:
            return return_view
    else:
        update_message = cast(Message, update.message)
        data = cast(str, update_message.text)

        return_view = await handle_date_from_selection_with_text(update_message, data, user_data)
        if return_view is not None:
            return return_view

    await update_date_from_selection(update, context)

    return READ_DATE_FROM


async def update_time_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = cast(dict[str, Any], context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    selected_hour = user_data["selected_from_hour"]
    selected_minute = user_data["selected_from_minute"]

    keyboard = [
        [
            InlineKeyboardButton("↑", callback_data="hour_up"),
            InlineKeyboardButton("↑", callback_data="minute_up"),
        ],
        [
            InlineKeyboardButton(f"{selected_hour:02d}", callback_data="ignore"),
            InlineKeyboardButton(f"{selected_minute:02d}", callback_data="ignore"),
        ],
        [
            InlineKeyboardButton("↓", callback_data="hour_down"),
            InlineKeyboardButton("↓", callback_data="minute_down"),
        ],
        [
            InlineKeyboardButton("Done", callback_data="time_done"),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            "Wybierz godzinę albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        return None


async def handle_time_from_selection_with_buttons(
    user_data: dict[str, Any], query: CallbackQuery, data: str
) -> int | None:
    if data == "minute_up":
        selected_minute = user_data["selected_from_minute"]
        selected_minute = min(selected_minute + 15, 59)
        user_data["selected_from_minute"] = selected_minute
    elif data == "minute_down":
        selected_minute = user_data["selected_from_minute"]
        selected_minute = max(selected_minute - 15, 0)
        user_data["selected_from_minute"] = selected_minute
    elif data == "hour_up":
        selected_hour = user_data["selected_from_hour"]
        selected_hour = min(selected_hour + 1, 23)
        user_data["selected_from_hour"] = selected_hour
    elif data == "hour_down":
        selected_hour = user_data["selected_from_hour"]
        selected_hour = max(selected_hour - 1, 0)
        user_data["selected_from_hour"] = selected_hour
    elif data == "time_done":
        selected_hour = user_data["selected_from_hour"]
        selected_minute = user_data["selected_from_minute"]
        selected_time = f"{selected_hour:02d}:{selected_minute:02d}"

        await query.edit_message_text(f"\u2705 Wybrano godzinę od: {selected_time}")

        # TODO: Add next steps

        return ConversationHandler.END

    return None


async def handle_time_from_selection_with_text(
    update_message: Message, data: str, user_data: dict[str, Any]
) -> int | None:
    try:
        time = datetime.strptime(data, "%H:%M")
        user_data["selected_from_hour"] = time.hour
        user_data["selected_from_minute"] = time.minute

        await update_message.reply_text(f"\u2705 Wybrano godzinę od: {data}")

        # TODO: Add next steps

        return ConversationHandler.END
    except ValueError:
        await update_message.reply_text("Invalid time format. Please use HH:MM.")
        return None


async def handle_time_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[str, Any], context.user_data)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = cast(str, query.data)

        return_view = await handle_time_from_selection_with_buttons(user_data, query, data)
        if return_view is not None:
            return return_view
    else:
        update_message = cast(Message, update.message)
        data = cast(str, update_message.text)

        return_view = await handle_time_from_selection_with_text(update_message, data, user_data)
        if return_view is not None:
            return return_view

    await update_time_from_selection(update, context)

    return READ_TIME_FROM
