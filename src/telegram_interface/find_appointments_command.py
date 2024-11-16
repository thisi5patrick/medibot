import json
import logging
from calendar import monthrange
from datetime import date, datetime

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
    if context.user_data is None or update.message is None:
        return ConversationHandler.END

    client: MedicoverClient | None = context.user_data.get("medicover_client")
    if not client:
        await update.message.reply_text("Please log in first.")
        return ConversationHandler.END

    await update.message.reply_text("Podaj fragment szukanego miasta")

    return GET_LOCATION


async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None or update.message is None:
        return ConversationHandler.END

    client: MedicoverClient = context.user_data["medicover_client"]
    location_input = update.message.text
    locations = client.get_region(location_input)

    if locations:
        context.user_data["locations"] = {str(loc["id"]): loc for loc in locations}

        keyboard = [[InlineKeyboardButton(loc["text"], callback_data=json.dumps(loc))] for loc in locations]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Wybierz miasto z listy:", reply_markup=reply_markup)

        return READ_LOCATION

    await update.message.reply_text("Nie znaleziono miasta. Wpisz ponownie.")
    return GET_LOCATION


async def read_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        return ConversationHandler.END

    query = update.callback_query

    if query is None:
        await update.message.reply_text("An error occurred while retrieving the location.")
        return ConversationHandler.END

    await query.answer()

    if query.data is None:
        await update.message.reply_text("An error occurred while retrieving the location.")
        return ConversationHandler.END

    data = json.loads(query.data)
    location_id = data["id"]
    location_text = data["text"]

    context.user_data["location_id"] = location_id
    await query.edit_message_text(f"\u2705 Wybrano miasto: {location_text}")

    await query.message.reply_text("Wpisz fragment szukanej specjalizacji")

    return GET_SPECIALIZATION


async def get_specialization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None or update.message is None:
        return ConversationHandler.END

    client: MedicoverClient = context.user_data["medicover_client"]
    specialization_input = update.message.text

    if specialization_input is None:
        await update.message.reply_text("An error occurred while retrieving the specialization.")
        return ConversationHandler.END

    specializations = client.get_specialization(specialization_input, context.user_data["location_id"])

    if specializations:
        context.user_data["specializations"] = {str(spec["id"]): spec for spec in specializations}

        keyboard = [[InlineKeyboardButton(spec["text"], callback_data=str(spec["id"]))] for spec in specializations]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Wybierz specjalizację:", reply_markup=reply_markup)

        return READ_SPECIALIZATION

    await update.message.reply_text("Nie znaleziono specjalizacji. Wpisz ponownie.")
    return GET_SPECIALIZATION


async def read_specialization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    specialization_id = query.data
    specializations = context.user_data.get("specializations", {})
    selected_spec = specializations.get(specialization_id)

    if not selected_spec:
        await query.edit_message_text(text="An error occurred while retrieving the specialization.")
        return ConversationHandler.END

    specialization_text = selected_spec["text"]

    context.user_data["specialization_id"] = specialization_id

    await query.edit_message_text(text=f"\u2705 Wybrano specjalizacje: {specialization_text}")

    keyboard = [[InlineKeyboardButton("Jakakolwiek", callback_data="any")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text("Wybierz klinikę albo podaj własną:", reply_markup=reply_markup)

    return READ_CLINIC


async def handle_clinic_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None or update.message is None:
        return ConversationHandler.END

    client: MedicoverClient = context.user_data["medicover_client"]
    location_id: int = context.user_data["location_id"]
    specialization_id: int = context.user_data["specialization_id"]

    user_input = update.message.text

    clinics = client.get_clinic(user_input, location_id, specialization_id)

    if clinics:
        context.user_data["clinics"] = {str(clinic["id"]): clinic for clinic in clinics}

        keyboard = [[InlineKeyboardButton(clinic["text"], callback_data=str(clinic["id"]))] for clinic in clinics]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Wybierz klinikę z listy:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Nie znaleziono kliniki. Wpisz ponownie.")
        return READ_CLINIC


async def handle_selected_clinic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        return ConversationHandler.END

    query = update.callback_query
    if query is None:
        return ConversationHandler.END

    await query.answer()

    clinic_id = query.data
    clinics = context.user_data.get("clinics", {})
    selected_clinic = clinics.get(clinic_id)
    if not selected_clinic:
        selected_clinic = "jakakolwiek"
    else:
        selected_clinic = selected_clinic["text"]
        context.user_data["clinic_id"] = clinic_id

    await query.edit_message_text(f"\u2705 Wybrano: {selected_clinic}")

    keyboard = [[InlineKeyboardButton("Jakikolwiek", callback_data="any")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text("Wybierz lekarza albo podaj:", reply_markup=reply_markup)

    return READ_DOCTOR


async def handle_doctor_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None or update.message is None:
        return ConversationHandler.END

    client: MedicoverClient = context.user_data["medicover_client"]
    location_id: int = context.user_data["location_id"]
    specialization_id: int = context.user_data["specialization_id"]
    clinic_id: int | None = context.user_data.get("clinic_id")

    user_input: str = update.message.text

    doctors = client.get_doctor(user_input, location_id, specialization_id, clinic_id)

    if doctors:
        context.user_data["doctors"] = {str(doctor["id"]): doctor for doctor in doctors}

        keyboard = [[InlineKeyboardButton(doctor["text"], callback_data=str(doctor["id"]))] for doctor in doctors]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Wybierz lekarza z listy:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Nie znaleziono lekarza. Wpisz ponownie.")
        return READ_DOCTOR


async def handle_selected_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    doctor_id = query.data
    doctors = context.user_data.get("doctors", {})
    selected_doctor = doctors.get(doctor_id)
    if selected_doctor is None:
        selected_doctor = "Jakikolwiek"
    else:
        selected_doctor = selected_doctor["text"]
        context.user_data["doctor_id"] = doctor_id

    await query.edit_message_text(f"\u2705 Wybrano lekarza: {selected_doctor}")

    day = date.today().day
    month = date.today().month
    year = date.today().year

    context.user_data["selected_from_day"] = day
    context.user_data["selected_from_month"] = month
    context.user_data["selected_from_year"] = year

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

    await query.message.reply_text(
        "Wybierz datę albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
    )

    return READ_DATE_FROM


async def update_date_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    day = context.user_data["selected_from_day"]
    month = context.user_data["selected_from_month"]
    year = context.user_data["selected_from_year"]

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

    query = update.callback_query
    try:
        await query.edit_message_text(
            "Wybierz datę albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024:", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        return READ_DATE_FROM


async def prepare_time_from_selection(context: ContextTypes.DEFAULT_TYPE) -> int:
    selected_hour = 7
    selected_minute = 0

    context.user_data["selected_from_hour"] = selected_hour
    context.user_data["selected_from_minute"] = selected_minute

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


async def handle_date_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:  # noqa: PLR0912, PLR0915
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
    else:
        data = update.message.text

    if data == "day_up":
        selected_day = context.user_data["selected_from_day"]
        selected_month = context.user_data["selected_from_month"]
        selected_year = context.user_data["selected_from_year"]
        selected_day = min(selected_day + 1, monthrange(selected_year, selected_month)[1])
        context.user_data["selected_from_day"] = selected_day
    elif data == "day_down":
        selected_day = context.user_data["selected_from_day"]
        selected_day = max(selected_day - 1, 1)
        context.user_data["selected_from_day"] = selected_day
    elif data == "month_up":
        selected_month = context.user_data["selected_from_month"]
        selected_month = min(selected_month + 1, 12)
        selected_day = context.user_data["selected_from_day"]
        selected_day = min(selected_day, monthrange(context.user_data["selected_from_year"], selected_month)[1])
        context.user_data["selected_from_month"] = selected_month
        context.user_data["selected_from_day"] = selected_day
    elif data == "month_down":
        selected_month = context.user_data["selected_from_month"]
        selected_month = max(selected_month - 1, 1)
        selected_day = context.user_data["selected_from_day"]
        selected_day = min(selected_day, monthrange(context.user_data["selected_from_year"], selected_month)[1])
        context.user_data["selected_from_month"] = selected_month
        context.user_data["selected_from_day"] = selected_day
    elif data == "year_up":
        selected_year = context.user_data["selected_from_year"]
        selected_year += 1
        selected_day = context.user_data["selected_from_day"]
        selected_day = min(selected_day, monthrange(selected_year, context.user_data["selected_from_month"])[1])
        context.user_data["selected_from_year"] = selected_year
        context.user_data["selected_from_day"] = selected_day
    elif data == "year_down":
        selected_year = context.user_data["selected_from_year"]
        if selected_year > datetime.now().year:
            selected_year -= 1
            selected_day = context.user_data["selected_from_day"]
            selected_day = min(selected_day, monthrange(selected_year, context.user_data["selected_from_month"])[1])
            context.user_data["selected_from_year"] = selected_year
            context.user_data["selected_from_day"] = selected_day
    elif data == "date_done":
        selected_day = context.user_data["selected_from_day"]
        selected_month = context.user_data["selected_from_month"]
        selected_year = context.user_data["selected_from_year"]
        selected_date = f"{selected_day:02d}-{selected_month:02d}-{selected_year}"

        await query.edit_message_text(f"\u2705 Wybrano datę od: {selected_date}")

        reply_markup = await prepare_time_from_selection(context)

        await query.message.reply_text(
            "Wybierz godzinę albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
        )

        return READ_TIME_FROM

    elif data == "ignore":
        pass

    else:
        try:
            date = datetime.strptime(data, "%d-%m-%Y")
            context.user_data["selected_from_day"] = date.day
            context.user_data["selected_from_month"] = date.month
            context.user_data["selected_from_year"] = date.year

            reply_markup = await prepare_time_from_selection(context)

            await update.message.reply_text(
                "Wybierz godzinę albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
            )
            return READ_TIME_FROM
        except ValueError:
            if update.callback_query:
                await update.callback_query.answer(text="Invalid date format. Please use DD-MM-YYYY.")
            else:
                await update.message.reply_text("Invalid date format. Please use DD-MM-YYYY.")

    await update_date_from_selection(update, context)

    return READ_DATE_FROM


async def update_time_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    selected_hour = context.user_data["selected_from_hour"]
    selected_minute = context.user_data["selected_from_minute"]

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

    query = update.callback_query
    try:
        await query.edit_message_text(
            "Wybierz godzinę albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        return


async def handle_time_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:  # noqa: PLR0912
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
    else:
        data = update.message.text

    if data == "minute_up":
        selected_minute = context.user_data["selected_from_minute"]
        selected_minute = min(selected_minute + 15, 59)
        context.user_data["selected_from_minute"] = selected_minute
    elif data == "minute_down":
        selected_minute = context.user_data["selected_from_minute"]
        selected_minute = max(selected_minute - 15, 0)
        context.user_data["selected_from_minute"] = selected_minute
    elif data == "hour_up":
        selected_hour = context.user_data["selected_from_hour"]
        selected_hour = min(selected_hour + 1, 23)
        context.user_data["selected_from_hour"] = selected_hour
    elif data == "hour_down":
        selected_hour = context.user_data["selected_from_hour"]
        selected_hour = max(selected_hour - 1, 0)
        context.user_data["selected_from_hour"] = selected_hour
    elif data == "time_done":
        selected_hour = context.user_data["selected_from_hour"]
        selected_minute = context.user_data["selected_from_minute"]
        selected_time = f"{selected_hour:02d}:{selected_minute:02d}"

        if update.callback_query:
            await update.callback_query.edit_message_text(f"\u2705 Wybrano godzinę od: {selected_time}")
        else:
            await update.message.reply_text(f"\u2705 Wybrano godzinę od: {selected_time}")

        return ConversationHandler.END

    elif data == "ignore":
        pass

    else:
        try:
            time = datetime.strptime(data, "%H:%M")
            context.user_data["selected_from_hour"] = time.hour
            context.user_data["selected_from_minute"] = time.minute
        except ValueError:
            if update.callback_query:
                await update.callback_query.answer(text="Invalid time format. Please use HH:MM.")
            else:
                await update.message.reply_text("Invalid time format. Please use HH:MM.")

    await update_time_from_selection(update, context)

    return READ_TIME_FROM
