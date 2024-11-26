import asyncio
import hashlib
import logging
from calendar import monthrange
from datetime import date, datetime
from typing import Any, cast

import telegram
from telegram import (
    CallbackQuery,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from telegram.ext import ContextTypes, ConversationHandler

from src.client import MedicoverClient
from src.telegram_interface.helpers import (
    NO_ANSWER,
    YES_ANSWER,
    extract_dates_from_user_data,
    prepare_clinic_keyboard,
    prepare_date_keyboard,
    prepare_specialization_keyboard,
    prepare_time_keyboard,
)
from src.telegram_interface.states import (
    GET_LOCATION,
    GET_SPECIALIZATION,
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
from src.telegram_interface.user_data import Location, Specialization, UserDataDataclass

logger = logging.getLogger(__name__)

MINUTE_INCREMENT = 15
HOUR_INCREMENT = 1
MAX_MINUTES = 60
MAX_HOURS = 24
MAX_MONTHS = 12


async def find_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    user_data = cast(UserDataDataclass, context.user_data)

    client = user_data.get("medicover_client")
    if not client:
        await update.message.reply_text("Please log in first.")
        return ConversationHandler.END

    if user_data.get("history") is None:
        user_data["history"] = {
            "locations": [],
            "specializations": [],
            "clinics": {},
            "doctors": {},
            "temp_data": {},
        }

    locations_history = user_data["history"]["locations"]

    if locations_history:
        keyboard = [
            [InlineKeyboardButton(location["location_name"], callback_data=str(location["location_id"]))]
            for location in locations_history
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Wpisz fragment szukanego miasta albo wybierz z ostatnio szukanych:", reply_markup=reply_markup
        )

    else:
        await update.message.reply_text("Wpisz fragment szukanego miasta:")
    return GET_LOCATION


async def get_location_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)
    await query.answer()

    location_id = cast(str, query.data)

    location = next(
        (item for item in user_data["history"]["locations"] if item["location_id"] == int(location_id)), None
    )
    if not location:
        return ConversationHandler.END

    location_text = location["location_name"]

    bookings = user_data.get("bookings")

    if not bookings:
        user_data["bookings"] = {}

    next_booking_number = next(reversed(user_data["bookings"])) + 1

    user_data["current_booking_number"] = next_booking_number
    user_data["bookings"][next_booking_number] = {"location": location}

    await query.edit_message_text(f"\u2705 Wybrano miasto: {location_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_specialization_keyboard(user_data)

    await query_message.reply_text(
        "Wpisz fragment szukanej specjalizacji albo wybierz z ostatnio szukanych",
        reply_markup=reply_markup,
    )

    return GET_SPECIALIZATION


async def get_location_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    update_message = cast(Message, update.message)
    location_input = cast(str, update_message.text)

    locations = await client.get_region(location_input)
    if not locations:
        await update_message.reply_text("Nie znaleziono miasta. Wpisz ponownie.")
        return GET_LOCATION

    user_data["history"]["temp_data"]["locations"] = {location["id"]: location["text"] for location in locations}
    keyboard = [[InlineKeyboardButton(location["text"], callback_data=str(location["id"]))] for location in locations]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update_message.reply_text("Wybierz miasto z listy:", reply_markup=reply_markup)

    return READ_LOCATION


async def read_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)

    await query.answer()

    user_input_location_id = int(cast(str, query.data))
    temp_locations = user_data["history"]["temp_data"]["locations"]
    location_text = temp_locations[user_input_location_id]
    location = Location(location_id=user_input_location_id, location_name=location_text)

    user_data["history"]["locations"].append(location)

    bookings = user_data.get("bookings")

    if not bookings:
        user_data["bookings"] = {}

    next_booking_number = next(reversed(user_data["bookings"])) + 1

    user_data["current_booking_number"] = next_booking_number
    user_data["bookings"][next_booking_number] = {"location": location}

    await query.edit_message_text(f"\u2705 Wybrano miasto: {location_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_specialization_keyboard(user_data)

    await query_message.reply_text(
        "Wpisz fragment szukanej specjalizacji albo wybierz z ostatnio szukanych",
        reply_markup=reply_markup,
    )

    return GET_SPECIALIZATION


async def get_specialization_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)
    await query.answer()

    specialization_id = int(cast(str, query.data))
    specialization = next(
        (item for item in user_data["history"]["specializations"] if item["specialization_id"] == specialization_id),
        None,
    )
    if not specialization:
        return ConversationHandler.END

    specialization_text = specialization["specialization_name"]

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["specialization"] = specialization

    await query.edit_message_text(f"\u2705 Wybrano specjalizacje: {specialization_text}")

    query_message = cast(Message, query.message)

    clinics = user_data["history"]["clinics"].get(specialization_id)
    if clinics:
        clinic_buttons = [
            [InlineKeyboardButton(clinic["clinic_name"], callback_data=str(clinic["clinic_id"]))] for clinic in clinics
        ]
    else:
        clinic_buttons = []
    keyboard = [
        [InlineKeyboardButton("Jakakolwiek", callback_data="any")],
        *clinic_buttons,
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query_message.reply_text("Wybierz klinikę albo podaj własną:", reply_markup=reply_markup)

    return READ_CLINIC


async def get_specialization_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[str, Any], context.user_data)
    update_message = cast(Message, update.message)

    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    specialization_input = cast(str, update_message.text)
    booking_number = user_data["current_booking_number"]
    location_id: int = user_data["bookings"][booking_number]["location"]["location_id"]

    specializations = await client.get_specialization(specialization_input, location_id)

    if specializations:
        user_data["history"]["temp_data"]["specializations"] = {
            specialization["id"]: specialization["text"] for specialization in specializations
        }

        keyboard = [[InlineKeyboardButton(spec["text"], callback_data=str(spec["id"]))] for spec in specializations]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update_message.reply_text("Wybierz specjalizację:", reply_markup=reply_markup)

        return READ_SPECIALIZATION

    await update_message.reply_text("Nie znaleziono specjalizacji. Wpisz ponownie.")
    return GET_SPECIALIZATION


async def read_specialization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(UserDataDataclass, context.user_data)

    await query.answer()

    user_input_specialization_id = int(cast(str, query.data))
    temp_specializations = user_data["history"]["temp_data"]
    specialization_text = temp_specializations[user_input_specialization_id]

    specialization = Specialization(
        specialization_id=user_input_specialization_id, specialization_name=specialization_text
    )

    user_data["history"]["specializations"].append(specialization)

    booking_number = user_data["current_booking_number"]
    user_data["bookings"][booking_number]["specialization"] = specialization

    await query.edit_message_text(text=f"\u2705 Wybrano specjalizacje: {specialization_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_clinic_keyboard(user_data, user_input_specialization_id)
    await query_message.reply_text("Wybierz klinikę albo podaj własną:", reply_markup=reply_markup)

    return READ_CLINIC


async def handle_clinic_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[str, Any], context.user_data)
    update_message = cast(Message, update.message)

    client: MedicoverClient = user_data["medicover_client"]
    location_id = user_data["location_id"]
    specialization_id = user_data["specialization_id"]

    user_input = cast(str, update_message.text)

    clinics = await client.get_clinic(user_input, location_id, specialization_id)

    if clinics:
        user_data["clinics"] = {str(clinic["id"]): clinic for clinic in clinics}

        keyboard = [[InlineKeyboardButton(clinic["text"], callback_data=str(clinic["id"]))] for clinic in clinics]
        keyboard.append([InlineKeyboardButton("Jakakolwiek", callback_data="any")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update_message.reply_text("Wybierz klinikę z listy:", reply_markup=reply_markup)
        return READ_CLINIC

    await update_message.reply_text("Nie znaleziono kliniki. Wpisz ponownie.")
    return READ_CLINIC


async def handle_selected_clinic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(dict[str, Any], context.user_data)

    await query.answer()

    clinic_id = query.data
    clinics = user_data.get("clinics", {})
    selected_clinic = clinics.get(clinic_id)
    if not selected_clinic:
        selected_clinic = "Jakakolwiek"
    else:
        selected_clinic = selected_clinic["text"]
        user_data["clinic_id"] = clinic_id

    await query.edit_message_text(f"\u2705 Wybrano klinikę: {selected_clinic}")

    keyboard = [[InlineKeyboardButton("Jakikolwiek", callback_data="any")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query_message = cast(Message, query.message)
    await query_message.reply_text("Wybierz lekarza albo podaj:", reply_markup=reply_markup)

    return READ_DOCTOR


async def handle_doctor_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    update_message = cast(Message, update.message)
    user_data = cast(dict[str, Any], context.user_data)

    client: MedicoverClient = user_data["medicover_client"]
    location_id: int = user_data["location_id"]
    specialization_id: int = user_data["specialization_id"]
    clinic_id: int | None = user_data.get("clinic_id")

    user_input = cast(str, update_message.text)

    doctors = await client.get_doctor(user_input, location_id, specialization_id, clinic_id)

    if doctors:
        user_data["doctors"] = {str(doctor["id"]): doctor for doctor in doctors}

        keyboard = [[InlineKeyboardButton(doctor["text"], callback_data=str(doctor["id"]))] for doctor in doctors]
        keyboard.append([InlineKeyboardButton("Jakikolwiek", callback_data="any")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update_message.reply_text("Wybierz lekarza z listy:", reply_markup=reply_markup)
        return READ_DOCTOR
    else:
        await update_message.reply_text("Nie znaleziono lekarza. Wpisz ponownie.")
        return None


async def handle_selected_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(dict[str, Any], context.user_data)

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

    await prepare_date_from_selection(user_data, query)

    return READ_DATE_FROM


async def prepare_date_from_selection(user_data: dict[str, Any], query: CallbackQuery) -> None:
    day = date.today().day
    month = date.today().month
    year = date.today().year

    user_data["selected_from_day"] = day
    user_data["selected_from_month"] = month
    user_data["selected_from_year"] = year

    reply_markup = prepare_date_keyboard(day, month, year)

    query_message = cast(Message, query.message)
    try:
        await query_message.reply_text(
            "Wybierz datę od albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        pass


async def update_date_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = cast(dict[str, Any], context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    day = user_data["selected_from_day"]
    month = user_data["selected_from_month"]
    year = user_data["selected_from_year"]

    reply_markup = prepare_date_keyboard(day, month, year)

    try:
        await query.edit_message_text(
            "Wybierz datę od albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        pass


async def handle_date_from_selection_with_buttons(
    data: str, user_data: dict[str, Any], query: CallbackQuery
) -> int | None:
    def adjust_day(user_data: dict[str, Any], increment: int) -> None:
        day = user_data["selected_from_day"]
        month = user_data["selected_from_month"]
        year = user_data["selected_from_year"]
        max_day = monthrange(year, month)[1]
        day = max(1, min(day + increment, max_day))
        user_data["selected_from_day"] = day

    def adjust_month(user_data: dict[str, Any], increment: int) -> None:
        month = user_data["selected_from_month"]
        month += increment
        if month > MAX_MONTHS:
            month = 1
        elif month < 1:
            month = 12
        user_data["selected_from_month"] = month
        adjust_day(user_data, 0)

    def adjust_year(user_data: dict[str, Any], increment: int) -> None:
        year = user_data["selected_from_year"]
        year += increment
        if year >= datetime.now().year or increment > 0:
            user_data["selected_from_year"] = year
            adjust_day(user_data, 0)

    if data == "day_up":
        adjust_day(user_data, 1)
    elif data == "day_down":
        adjust_day(user_data, -1)
    elif data == "month_up":
        adjust_month(user_data, 1)
    elif data == "month_down":
        adjust_month(user_data, -1)
    elif data == "year_up":
        adjust_year(user_data, 1)
    elif data == "year_down":
        adjust_year(user_data, -1)
    elif data == "date_done":
        selected_day = user_data["selected_from_day"]
        selected_month = user_data["selected_from_month"]
        selected_year = user_data["selected_from_year"]
        selected_date = f"{selected_day:02d}-{selected_month:02d}-{selected_year}"

        await query.edit_message_text(f"\u2705 Wybrano datę od: {selected_date}")

        query_message = cast(Message, query.message)
        await prepare_time_from_selection(user_data, query_message)

        return READ_TIME_FROM

    return None


async def handle_date_from_selection_with_text(
    data: str, user_data: dict[str, Any], update_message: Message
) -> int | None:
    try:
        date_ = datetime.strptime(data, "%d-%m-%Y")
        user_data["selected_from_day"] = date_.day
        user_data["selected_from_month"] = date_.month
        user_data["selected_from_year"] = date_.year

        await update_message.reply_text(f"\u2705 Wybrano datę od: {data}")

        await prepare_time_from_selection(user_data, update_message)

        return READ_TIME_FROM
    except ValueError:
        await update_message.reply_text("Niepoprawny format daty. Podaj datę w formacie dd-mm-rrrr.")
        return None


async def handle_date_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[str, Any], context.user_data)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = cast(str, query.data)

        return_view = await handle_date_from_selection_with_buttons(data, user_data, query)
        if return_view is not None:
            return return_view
    else:
        update_message = cast(Message, update.message)
        data = cast(str, update_message.text)

        return_view = await handle_date_from_selection_with_text(data, user_data, update_message)
        if return_view is not None:
            return return_view

    await update_date_from_selection(update, context)

    return READ_DATE_FROM


async def prepare_time_from_selection(user_data: dict[str, Any], query_message: Message) -> None:
    hour = 7
    minute = 0

    user_data["selected_from_hour"] = hour
    user_data["selected_from_minute"] = minute

    reply_markup = prepare_time_keyboard(hour, minute)

    try:
        await query_message.reply_text(
            "Szukaj terminów po godzinie albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        pass


async def update_time_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = cast(dict[str, Any], context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    hour = user_data["selected_from_hour"]
    minute = user_data["selected_from_minute"]

    reply_markup = prepare_time_keyboard(hour, minute)

    try:
        await query.edit_message_text(
            "Szukaj terminów po godzinie albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        pass


async def handle_time_from_selection_with_buttons(
    data: str, user_data: dict[str, Any], query: CallbackQuery
) -> int | None:
    if data == "minute_up":
        minute = user_data["selected_from_minute"]
        minute += 15
        if minute >= MAX_MINUTES:
            minute = 0
        user_data["selected_from_minute"] = minute
    elif data == "minute_down":
        minute = user_data["selected_from_minute"]
        minute -= 15
        if minute < 0:
            minute = 45
        user_data["selected_from_minute"] = minute
    elif data == "hour_up":
        hour = user_data["selected_from_hour"]
        hour += 1
        if hour >= MAX_HOURS:
            hour = 0
        user_data["selected_from_hour"] = hour
    elif data == "hour_down":
        hour = user_data["selected_from_hour"]
        hour -= 1
        if hour < 0:
            hour = 23
        user_data["selected_from_hour"] = hour
    elif data == "time_done":
        selected_hour = user_data["selected_from_hour"]
        selected_minute = user_data["selected_from_minute"]
        selected_time = f"{selected_hour:02d}:{selected_minute:02d}"

        await query.edit_message_text(f"\u2705 Terminy po godzinie: {selected_time}")

        query_message = cast(Message, query.message)
        await prepare_date_to_selection(user_data, query_message)

        return READ_DATE_TO

    return None


async def handle_time_from_selection_with_text(
    data: str, user_data: dict[str, Any], update_message: Message
) -> int | None:
    try:
        time = datetime.strptime(data, "%H:%M")
        user_data["selected_from_hour"] = time.hour
        user_data["selected_from_minute"] = time.minute

        await update_message.reply_text(f"\u2705 Wybrano godzinę od: {data}")

        await prepare_date_to_selection(user_data, update_message)

        return READ_DATE_TO
    except ValueError:
        await update_message.reply_text("Niepoprawny format godziny. Podaj godzinę w formacie HH:MM.")
        return None


async def handle_time_from_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[str, Any], context.user_data)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = cast(str, query.data)

        return_view = await handle_time_from_selection_with_buttons(data, user_data, query)
        if return_view is not None:
            return return_view
    else:
        update_message = cast(Message, update.message)
        data = cast(str, update_message.text)

        return_view = await handle_time_from_selection_with_text(data, user_data, update_message)
        if return_view is not None:
            return return_view

    await update_time_from_selection(update, context)

    return READ_TIME_FROM


async def prepare_date_to_selection(user_data: dict[str, Any], update_message: Message) -> None:
    day = date.today().day
    month = date.today().month
    year = date.today().year

    user_data["selected_to_day"] = day
    user_data["selected_to_month"] = month
    user_data["selected_to_year"] = year

    reply_markup = prepare_date_keyboard(day, month, year)

    try:
        await update_message.reply_text(
            "Wybierz datę do albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        pass


async def update_date_to_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = cast(dict[str, Any], context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    day = user_data["selected_to_day"]
    month = user_data["selected_to_month"]
    year = user_data["selected_to_year"]

    reply_markup = prepare_date_keyboard(day, month, year)

    try:
        await query.edit_message_text(
            "Wybierz datę do albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        pass


async def handle_date_to_selection_with_buttons(
    user_data: dict[str, Any], query: CallbackQuery, data: str
) -> int | None:
    def adjust_day(user_data: dict[str, Any], increment: int) -> None:
        day = user_data["selected_to_day"]
        month = user_data["selected_to_month"]
        year = user_data["selected_to_year"]
        max_day = monthrange(year, month)[1]
        day = max(1, min(day + increment, max_day))
        user_data["selected_to_day"] = day

    def adjust_month(user_data: dict[str, Any], increment: int) -> None:
        month = user_data["selected_to_month"]
        month += increment
        if month > MAX_MONTHS:
            month = 1
        elif month < 1:
            month = 12
        user_data["selected_to_month"] = month
        adjust_day(user_data, 0)

    def adjust_year(user_data: dict[str, Any], increment: int) -> None:
        year = user_data["selected_to_year"]
        year += increment
        if year >= datetime.now().year or increment > 0:
            user_data["selected_to_year"] = year
            adjust_day(user_data, 0)

    if data == "day_up":
        adjust_day(user_data, 1)
    elif data == "day_down":
        adjust_day(user_data, -1)
    elif data == "month_up":
        adjust_month(user_data, 1)
    elif data == "month_down":
        adjust_month(user_data, -1)
    elif data == "year_up":
        adjust_year(user_data, 1)
    elif data == "year_down":
        adjust_year(user_data, -1)
    elif data == "date_done":
        selected_day = user_data["selected_to_day"]
        selected_month = user_data["selected_to_month"]
        selected_year = user_data["selected_to_year"]
        selected_date = f"{selected_day:02d}-{selected_month:02d}-{selected_year}"

        await query.edit_message_text(f"\u2705 Wybrano datę do: {selected_date}")

        query_message = cast(Message, query.message)
        await prepare_time_to_selection(user_data, query_message)

        return READ_TIME_TO

    return None


async def handle_date_to_selection_with_text(
    update_message: Message, data: str, user_data: dict[str, Any]
) -> int | None:
    try:
        date = datetime.strptime(data, "%d-%m-%Y")
        user_data["selected_to_day"] = date.day
        user_data["selected_to_month"] = date.month
        user_data["selected_to_year"] = date.year

        await update_message.reply_text(f"\u2705 Wybrano datę do: {data}")

        await prepare_time_to_selection(user_data, update_message)

        return READ_TIME_FROM
    except ValueError:
        await update_message.reply_text("Niepoprawny format daty. Podaj datę w formacie dd-mm-rrrr.")
        return None


async def handle_date_to_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[str, Any], context.user_data)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = cast(str, query.data)

        return_view = await handle_date_to_selection_with_buttons(user_data, query, data)
        if return_view is not None:
            return return_view
    else:
        update_message = cast(Message, update.message)
        data = cast(str, update_message.text)

        return_view = await handle_date_to_selection_with_text(update_message, data, user_data)
        if return_view is not None:
            return return_view

    await update_date_to_selection(update, context)

    return READ_DATE_TO


async def prepare_time_to_selection(user_data: dict[str, Any], update_message: Message) -> None:
    hour = 23
    minute = 0

    user_data["selected_to_hour"] = hour
    user_data["selected_to_minute"] = minute

    reply_markup = prepare_time_keyboard(hour, minute)

    try:
        await update_message.reply_text(
            "Szukaj terminów przed godziną albo zapisz w formacie HH:MM, np. 21:00", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        pass


async def update_time_to_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = cast(dict[str, Any], context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    hour = user_data["selected_to_hour"]
    minute = user_data["selected_to_minute"]

    reply_markup = prepare_time_keyboard(hour, minute)

    try:
        await query.edit_message_text(
            "Szukaj terminów przed godziną albo zapisz w formacie HH:MM, np. 21:00", reply_markup=reply_markup
        )
    except telegram.error.BadRequest:
        pass


async def handle_time_to_selection_with_buttons(
    user_data: dict[str, Any], query: CallbackQuery, data: str
) -> int | None:
    if data == "minute_up":
        minute = user_data["selected_to_minute"]
        minute += 15
        if minute >= MAX_MINUTES:
            minute = 0
        user_data["selected_to_minute"] = minute
    elif data == "minute_down":
        minute = user_data["selected_to_minute"]
        minute -= 15
        if minute < 0:
            minute = 45
        user_data["selected_to_minute"] = minute
    elif data == "hour_up":
        hour = user_data["selected_to_hour"]
        hour += 1
        if hour >= MAX_HOURS:
            hour = 0
        user_data["selected_to_hour"] = hour
    elif data == "hour_down":
        hour = user_data["selected_to_hour"]
        hour -= 1
        if hour < 0:
            hour = 23
        user_data["selected_to_hour"] = hour
    elif data == "time_done":
        selected_hour = user_data["selected_to_hour"]
        selected_minute = user_data["selected_to_minute"]
        selected_time = f"{selected_hour:02d}:{selected_minute:02d}"

        await query.edit_message_text(f"\u2705 Wybrano godzinę do: {selected_time}")

        query_message = cast(Message, query.message)
        await prepare_summary(user_data, query_message)

        return VERIFY_SUMMARY

    return None


async def handle_time_to_selection_with_text(
    update_message: Message, data: str, user_data: dict[str, Any]
) -> int | None:
    try:
        time = datetime.strptime(data, "%H:%M")
        user_data["selected_to_hour"] = time.hour
        user_data["selected_to_minute"] = time.minute

        await update_message.reply_text(f"\u2705 Wybrano godzinę do: {data}")

        await prepare_summary(user_data, update_message)

        return VERIFY_SUMMARY
    except ValueError:
        await update_message.reply_text("Niepoprawny format godziny. Podaj godzinę w formacie HH:MM.")
        return None


async def handle_time_to_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[str, Any], context.user_data)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = cast(str, query.data)

        return_view = await handle_time_to_selection_with_buttons(user_data, query, data)
        if return_view is not None:
            return return_view
    else:
        update_message = cast(Message, update.message)
        data = cast(str, update_message.text)

        return_view = await handle_time_to_selection_with_text(update_message, data, user_data)
        if return_view is not None:
            return return_view

    await update_time_to_selection(update, context)

    return READ_TIME_TO


async def prepare_summary(user_data: dict[str, Any], update_message: Message) -> int:
    all_locations = user_data["locations"]
    location_id = user_data["location_id"]
    location = all_locations[location_id]

    all_specializations = user_data["specializations"]
    specialization_id = user_data.get("specialization_id")
    specialization = all_specializations[specialization_id]

    all_clinics = user_data.get("clinics")
    if all_clinics:
        clinic_id = user_data["clinic_id"]
        clinic = all_clinics[clinic_id]
    else:
        clinic = {"id": "any", "text": "Jakakolwiek"}

    all_doctors = user_data.get("doctors")
    if all_doctors:
        doctor_id = user_data["doctor_id"]
        doctor = all_doctors[doctor_id]
    else:
        doctor = {"id": "any", "text": "Jakikolwiek"}

    selected_from_date, selected_from_time, selected_to_date, selected_to_time = extract_dates_from_user_data(user_data)

    keyboard = [
        [InlineKeyboardButton("Tak", callback_data=YES_ANSWER)],
        [InlineKeyboardButton("Nie", callback_data=NO_ANSWER)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    summary_text = "Podsumowanie:\n"
    summary_text += f"Miasto: {location['text']}\n"
    summary_text += f"Specjalizacja: {specialization['text']}\n"
    summary_text += f"Klinika: {clinic['text']}\n"
    summary_text += f"Doktor: {doctor['text']}\n"
    summary_text += f"Data od: {selected_from_date}\n"
    summary_text += f"Data do: {selected_to_date}\n"
    summary_text += f"Godzina od: {selected_from_time}\n"
    summary_text += f"Godzina do: {selected_to_time}"

    await update_message.reply_text(
        f"\u2754 {summary_text}\nPodsumowanie jest prawidłowe?",
        reply_markup=reply_markup,
    )

    user_data["summary_text"] = summary_text

    return VERIFY_SUMMARY


async def verify_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    query_message = cast(Message, query.message)
    user_data = cast(dict[str, Any], context.user_data)

    await query.answer()
    data = cast(str, query.data)

    if data == NO_ANSWER:
        await query_message.reply_text("Zacznijmy od poczatku")

        # TODO fix this -> it's not running correctly
        return await find_appointments(update, context)

    await query.edit_message_text(f"\u2705 {user_data['summary_text']}")

    client: MedicoverClient = user_data["medicover_client"]
    location_id: int = user_data["location_id"]
    specialization_id: int = user_data["specialization_id"]
    doctor_id: int | None = user_data.get("doctor_id")
    clinic_id: int | None = user_data.get("clinic_id")

    (
        selected_from_date,
        selected_from_time,
        selected_to_date,
        selected_to_time,
    ) = extract_dates_from_user_data(user_data)

    available_slots = await client.get_available_slots(
        location_id,
        specialization_id,
        doctor_id,
        clinic_id,
        from_date=selected_from_date,
        from_time=selected_from_time,
        to_time=selected_to_time,
    )

    parsed_available_slot = []
    to_date = datetime.strptime(f"{selected_to_date} {selected_to_time}", "%d-%m-%Y %H:%M")
    for slot in available_slots:
        appointment_date = datetime.fromisoformat(slot["appointmentDate"])
        if appointment_date < to_date:
            parsed_available_slot.append(slot)

    if not parsed_available_slot:
        await query_message.reply_text("Brak dostępnych terminów dla wybranych parametrów.")

        keyboard = [
            [InlineKeyboardButton("Tak", callback_data=YES_ANSWER)],
            [InlineKeyboardButton("Nie", callback_data=NO_ANSWER)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query_message.reply_text("\u2754 Czy chcesz utworzyć monitoring?", reply_markup=reply_markup)

        return READ_CREATE_MONITORING

    await query_message.reply_text("Dostępne terminy:")

    for slot in parsed_available_slot:
        await query_message.reply_text(
            f"Lekarz: {slot['doctorName']}\nKlinika: {slot['clinicName']}\nData: {slot['appointmentDate']}"
        )

    # TODO add reserve slot
    return ConversationHandler.END


async def create_monitoring_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = cast(dict[str, Any], context.user_data)
    query = cast(CallbackQuery, update.callback_query)
    query_message = cast(Message, query.message)
    chat = cast(Chat, update.effective_chat)
    user_chat_id = chat.id

    client: MedicoverClient = user_data["medicover_client"]

    location_id: int = user_data["location_id"]
    specialization_id: int = user_data["specialization_id"]
    doctor_id: int | None = user_data.get("doctor_id")
    clinic_id: int | None = user_data.get("clinic_id")

    (
        selected_from_date,
        selected_from_time,
        selected_to_date,
        selected_to_time,
    ) = extract_dates_from_user_data(user_data)

    kwargs = {
        "region_id": location_id,
        "specialization_id": specialization_id,
        "doctor_id": doctor_id,
        "clinic_id": clinic_id,
        "from_date": selected_from_date,
        "from_time": selected_from_time,
        "to_time": selected_to_time,
    }

    task_hash = hashlib.md5(user_data["summary_text"].encode()).hexdigest()
    user_data[f"{user_chat_id}_{task_hash}"] = user_data["summary_text"]

    to_date = datetime.strptime(f"{selected_to_date} {selected_to_time}", "%d-%m-%Y %H:%M")

    while True:
        slots = await client.get_available_slots(**kwargs)
        parsed_available_slot = []

        for slot in slots:
            appointment_date = datetime.fromisoformat(slot["appointmentDate"])
            if appointment_date < to_date:
                parsed_available_slot.append(slot)

        if parsed_available_slot:
            for slot in parsed_available_slot:
                await query_message.reply_text("Znaleziono nowy termin.")

                await query_message.reply_text(
                    f"Lekarz: {slot['doctorName']}\nKlinika: {slot['clinicName']}\nData: {slot['appointmentDate']}"
                )
            break
        logger.info("No slots available for given parameters. Trying again in 30 seconds...")
        await asyncio.sleep(30)


async def read_create_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat = cast(Chat, update.effective_chat)
    user_chat_id = chat.id

    query = cast(CallbackQuery, update.callback_query)
    query_message = cast(Message, query.message)
    user_data = cast(dict[str, Any], context.user_data)

    await query.answer()
    data = cast(str, query.data)

    if data == NO_ANSWER:
        return ConversationHandler.END

    await query.edit_message_text(f"✅ Tworzenie monitoringu dla parametrów:\n{user_data['summary_text']}")

    task_hash = hashlib.md5(user_data["summary_text"].encode()).hexdigest()

    context.application.create_task(
        create_monitoring_task(update, context), update=update, name=f"{user_chat_id}_{task_hash}"
    )

    await query_message.reply_text("Monitoring został utworzony.")

    return ConversationHandler.END
