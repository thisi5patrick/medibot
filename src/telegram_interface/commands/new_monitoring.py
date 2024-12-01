import asyncio
import hashlib
import logging
from datetime import datetime
from typing import cast

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
    get_summary_text,
    handle_date_selection,
    handle_time_selection,
    prepare_clinic_keyboard,
    prepare_date_selection,
    prepare_doctor_keyboard,
    prepare_specialization_keyboard,
    prepare_summary,
    prepare_time_keyboard,
    update_date_selection_buttons,
    update_time_selection_buttons,
)
from src.telegram_interface.states import (
    GET_CLINIC,
    GET_DOCTOR,
    GET_FROM_DATE,
    GET_FROM_TIME,
    GET_LOCATION,
    GET_SPECIALIZATION,
    GET_TO_DATE,
    GET_TO_TIME,
    READ_CLINIC,
    READ_CREATE_MONITORING,
    READ_DOCTOR,
    READ_LOCATION,
    READ_SPECIALIZATION,
    VERIFY_SUMMARY,
)
from src.telegram_interface.user_data import (
    Clinic,
    Doctor,
    Location,
    MonitoringDate,
    MonitoringTime,
    Specialization,
    UserDataDataclass,
)

logger = logging.getLogger(__name__)

MINUTE_INCREMENT = 15
HOUR_INCREMENT = 1
MAX_MINUTES = 60
MAX_HOURS = 24
MAX_MONTHS = 12


async def new_monitoring_entrypoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if message is None:
        callback_query = cast(CallbackQuery, update.callback_query)
        message = cast(Message, callback_query.message)

    user_data = cast(UserDataDataclass, context.user_data)

    client = user_data.get("medicover_client")
    if not client:
        await message.reply_text("Please log in first.")
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

        await message.reply_text(
            "Wpisz fragment szukanego miasta albo wybierz z ostatnio szukanych:", reply_markup=reply_markup
        )

    else:
        await message.reply_text("Wpisz fragment szukanego miasta:")
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

    next_booking_number = next(reversed(user_data["bookings"]), 0) + 1

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

    reply_markup = prepare_clinic_keyboard(user_data, specialization_id)

    await query_message.reply_text(
        "Wpisz fragment szukanej kliniki albo wybierz z ostatnio szukanych", reply_markup=reply_markup
    )

    return GET_CLINIC


async def get_specialization_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
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
    temp_specializations = user_data["history"]["temp_data"]["specializations"]
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
    await query_message.reply_text(
        "Wpisz fragment szukanej kliniki albo wybierz z ostatnio szukanych", reply_markup=reply_markup
    )

    return GET_CLINIC


async def get_clinic_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)
    await query.answer()

    clinic_id = cast(str, query.data)

    current_booking_number = user_data["current_booking_number"]

    specialization_id = user_data["bookings"][current_booking_number]["specialization"]["specialization_id"]

    if clinic_id == "any":
        clinic_id = None  # type: ignore[assignment]
        clinic_text = "Jakakolwiek"
        user_data["bookings"][current_booking_number]["clinic"] = Clinic(
            clinic_id=cast(None, clinic_id), clinic_name=clinic_text
        )
    else:
        clinic = next(
            (
                item
                for item in user_data["history"]["clinics"][specialization_id]
                if item["clinic_id"] == int(clinic_id)
            ),
            None,
        )
        if clinic is None:
            return ConversationHandler.END

        user_data["bookings"][current_booking_number]["clinic"] = clinic
        clinic_text = clinic["clinic_name"]

    await query.edit_message_text(f"\u2705 Wybrano klinikę: {clinic_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_doctor_keyboard(user_data, specialization_id)

    await query_message.reply_text(
        "Wpisz fragment nazwy lekarza albo wybierz z ostatnio szukanych", reply_markup=reply_markup
    )

    return GET_DOCTOR


async def get_clinic_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    clinic_input = cast(str, update_message.text)
    booking_number = user_data["current_booking_number"]
    location_id = user_data["bookings"][booking_number]["location"]["location_id"]
    specialization_id = user_data["bookings"][booking_number]["specialization"]["specialization_id"]

    clinics = await client.get_clinic(clinic_input, location_id, specialization_id)
    if clinics:
        user_data["history"]["temp_data"]["clinics"] = {clinic["id"]: clinic["text"] for clinic in clinics}

        keyboard = [[InlineKeyboardButton(clinic["text"], callback_data=str(clinic["id"]))] for clinic in clinics]
        keyboard.append([InlineKeyboardButton("Jakakolwiek", callback_data="any")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update_message.reply_text("Wybierz klinike:", reply_markup=reply_markup)

        return READ_CLINIC

    await update_message.reply_text("Nie znaleziono kliniki. Wpisz ponownie.")

    return GET_CLINIC


async def read_clinic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(UserDataDataclass, context.user_data)

    await query.answer()

    user_input_clinic_id = int(cast(str, query.data))
    temp_clinics = user_data["history"]["temp_data"]["clinics"]
    specialization_text = temp_clinics[user_input_clinic_id]
    clinic = Clinic(clinic_id=user_input_clinic_id, clinic_name=specialization_text)

    booking_number = user_data["current_booking_number"]
    specialization_id = user_data["bookings"][booking_number]["specialization"]["specialization_id"]

    if specialization_id not in user_data["history"]["clinics"]:
        user_data["history"]["clinics"][specialization_id] = []

    user_data["history"]["clinics"][specialization_id].append(clinic)
    user_data["bookings"][booking_number]["clinic"] = clinic

    await query.edit_message_text(f"\u2705 Wybrano klinikę: {specialization_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_doctor_keyboard(user_data, specialization_id)
    await query_message.reply_text(
        "Wpisz fragment nazwy lekarza albo wybierz z ostatnio szukanych", reply_markup=reply_markup
    )

    return GET_DOCTOR


async def get_doctor_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)
    await query.answer()

    doctor_id = cast(str, query.data)

    current_booking_number = user_data["current_booking_number"]

    specialization_id = user_data["bookings"][current_booking_number]["specialization"]["specialization_id"]

    if doctor_id == "any":
        doctor_id = None  # type: ignore[assignment]
        doctor_text = "Jakakolwiek"
        user_data["bookings"][current_booking_number]["doctor"] = Doctor(
            doctor_name=doctor_text, doctor_id=cast(None, doctor_id)
        )
    else:
        doctor = next(
            (
                item
                for item in user_data["history"]["doctors"][specialization_id]
                if item["doctor_id"] == int(doctor_id)
            ),
            None,
        )
        if doctor is None:
            return ConversationHandler.END

        user_data["bookings"][current_booking_number]["doctor"] = doctor
        doctor_text = doctor["doctor_name"]

    await query.edit_message_text(f"\u2705 Wybrano lekarza: {doctor_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_date_selection(user_data, "from_date")

    message = await query_message.reply_text(
        "Wybierz datę od albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
    )
    user_data["bookings"][current_booking_number]["message_id"] = message.message_id

    return GET_FROM_DATE


async def get_doctor_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    doctor_input = cast(str, update_message.text)
    booking_number = user_data["current_booking_number"]
    location_id = user_data["bookings"][booking_number]["location"]["location_id"]
    specialization_id = user_data["bookings"][booking_number]["specialization"]["specialization_id"]
    clinic_id = user_data["bookings"][booking_number]["clinic"]["clinic_id"]

    doctors = await client.get_doctor(doctor_input, location_id, specialization_id, clinic_id)
    if doctors:
        user_data["history"]["temp_data"]["doctors"] = {doctor["id"]: doctor["text"] for doctor in doctors}

        keyboard = [[InlineKeyboardButton(doctor["text"], callback_data=str(doctor["id"]))] for doctor in doctors]
        keyboard.append([InlineKeyboardButton("Jakikolwiek", callback_data="any")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update_message.reply_text("Wybierz lekarza:", reply_markup=reply_markup)

        return READ_DOCTOR

    await update_message.reply_text("Nie znaleziono lekarza. Wpisz ponownie.")

    return GET_DOCTOR


async def read_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(UserDataDataclass, context.user_data)

    await query.answer()

    user_input_doctor_id = int(cast(str, query.data))
    temp_doctors = user_data["history"]["temp_data"]["doctors"]
    specialization_text = temp_doctors[user_input_doctor_id]
    doctor = Doctor(doctor_name=specialization_text, doctor_id=user_input_doctor_id)

    booking_number = user_data["current_booking_number"]
    specialization_id = user_data["bookings"][booking_number]["specialization"]["specialization_id"]

    if specialization_id not in user_data["history"]["doctors"]:
        user_data["history"]["doctors"][specialization_id] = []

    user_data["history"]["doctors"][specialization_id].append(doctor)

    await query.edit_message_text(f"\u2705 Wybrano lekarza: {specialization_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_date_selection(user_data, "from_date")

    await query_message.reply_text(
        "Wybierz datę od albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
    )

    return GET_FROM_DATE


async def get_from_date_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    date_input = cast(str, update_message.text)
    try:
        date_object = datetime.strptime(date_input, "%d-%m-%Y")
    except ValueError:
        await update_message.reply_text("Podany format daty jest nieprawidłowy. Wpisz ponownie.")
        return GET_FROM_DATE

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["from_date"] = MonitoringDate(
        day=date_object.day, month=date_object.month, year=date_object.year
    )

    await context.bot.delete_message(
        chat_id=cast(Chat, update.effective_chat).id,
        message_id=user_data["bookings"][current_booking_number]["message_id"],
    )

    await update_message.reply_text(f"\u2705 Wybrano datę szukania od: {date_input}")

    hour = 7
    minute = 0

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["from_time"] = MonitoringTime(hour=hour, minute=minute)

    reply_markup = prepare_time_keyboard(hour, minute)

    query_message = cast(Message, update.message)
    message = await query_message.reply_text(
        "Szukaj terminów po godzinie albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
    )
    user_data["bookings"][current_booking_number]["message_id"] = message.message_id

    return GET_FROM_TIME


async def get_from_date_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    await query.answer()

    user_action = cast(str, query.data)

    selected_date = handle_date_selection(user_action, user_data, "from_date")
    if selected_date is None:
        reply_markup = update_date_selection_buttons(user_data, "from_date")

        try:
            await query.edit_message_text(
                "Wybierz datę od albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
            )
        except telegram.error.BadRequest:
            pass

        return GET_FROM_DATE

    await query.edit_message_text(f"\u2705 Wybrano datę od: {selected_date}")

    query_message = cast(Message, query.message)

    hour = 7
    minute = 0

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["from_time"] = MonitoringTime(hour=hour, minute=minute)

    reply_markup = prepare_time_keyboard(hour, minute)

    message = await query_message.reply_text(
        "Szukaj terminów po godzinie albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
    )
    user_data["bookings"][current_booking_number]["message_id"] = message.message_id

    return GET_FROM_TIME


async def get_from_time_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    time_input = cast(str, update_message.text)
    try:
        time_object = datetime.strptime(time_input, "%H:%M")
    except ValueError:
        await update_message.reply_text("Podany format godziny jest nieprawidłowy. Wpisz ponownie.")
        return GET_FROM_TIME

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["from_time"] = MonitoringTime(
        hour=time_object.hour, minute=time_object.minute
    )

    await context.bot.delete_message(
        chat_id=cast(Chat, update.effective_chat).id,
        message_id=user_data["bookings"][current_booking_number]["message_id"],
    )

    await update_message.reply_text(f"\u2705 Wybrano szukanie terminów po godzinie: {time_input}")

    reply_markup = prepare_date_selection(user_data, "to_date")

    await update_message.reply_text(
        "Wybierz datę do albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
    )

    return GET_TO_DATE


async def get_from_time_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    await query.answer()

    user_action = cast(str, query.data)

    selected_date = handle_time_selection(user_action, user_data, "from_time")
    if selected_date is None:
        reply_markup = update_time_selection_buttons(user_data, "from_time")

        try:
            await query.edit_message_text(
                "Szukaj terminów po godzinie albo zapisz w formacie HH:MM, np. 10:00", reply_markup=reply_markup
            )
        except telegram.error.BadRequest:
            pass

        return GET_FROM_TIME

    await query.edit_message_text(f"\u2705 Wybrano szukanie terminów po godzinie: {selected_date}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_date_selection(user_data, "to_date")

    await query_message.reply_text(
        "Wybierz datę do albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
    )

    return GET_TO_DATE


async def get_to_date_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    date_input = cast(str, update_message.text)
    try:
        date_object = datetime.strptime(date_input, "%d-%m-%Y")
    except ValueError:
        await update_message.reply_text("Podany format daty jest nieprawidłowy. Wpisz ponownie.")
        return GET_TO_DATE

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["to_date"] = MonitoringDate(
        day=date_object.day, month=date_object.month, year=date_object.year
    )

    await context.bot.delete_message(
        chat_id=cast(Chat, update.effective_chat).id,
        message_id=user_data["bookings"][current_booking_number]["message_id"],
    )

    await update_message.reply_text(f"\u2705 Wybrano datę szukania do: {date_input}")

    hour = 22
    minute = 0

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["to_time"] = MonitoringTime(hour=hour, minute=minute)

    reply_markup = prepare_time_keyboard(hour, minute)

    query_message = cast(Message, update.message)
    message = await query_message.reply_text(
        "Szukaj terminów po godzinie albo zapisz w formacie HH:MM, np. 21:00", reply_markup=reply_markup
    )
    user_data["bookings"][current_booking_number]["message_id"] = message.message_id

    return GET_TO_TIME


async def get_to_date_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    await query.answer()

    user_action = cast(str, query.data)

    selected_date = handle_date_selection(user_action, user_data, "to_date")
    if selected_date is None:
        reply_markup = update_date_selection_buttons(user_data, "to_date")

        try:
            await query.edit_message_text(
                "Wybierz datę do albo zapisz w formacie dd-mm-rrrr, np. 04-11-2024", reply_markup=reply_markup
            )
        except telegram.error.BadRequest:
            pass

        return GET_TO_DATE

    await query.edit_message_text(f"\u2705 Wybrano datę szukania do: {selected_date}")

    query_message = cast(Message, query.message)

    hour = 22
    minute = 0

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["to_time"] = MonitoringTime(hour=hour, minute=minute)

    reply_markup = prepare_time_keyboard(hour, minute)

    message = await query_message.reply_text(
        "Szukaj terminów do godziny albo zapisz w formacie HH:MM, np. 21:00", reply_markup=reply_markup
    )
    user_data["bookings"][current_booking_number]["message_id"] = message.message_id

    return GET_TO_TIME


async def get_to_time_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    time_input = cast(str, update_message.text)
    try:
        time_object = datetime.strptime(time_input, "%H:%M")
    except ValueError:
        await update_message.reply_text("Podany format godziny jest nieprawidłowy. Wpisz ponownie.")
        return GET_TO_TIME

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["to_time"] = MonitoringTime(
        hour=time_object.hour, minute=time_object.minute
    )

    await context.bot.delete_message(
        chat_id=cast(Chat, update.effective_chat).id,
        message_id=user_data["bookings"][current_booking_number]["message_id"],
    )

    await update_message.reply_text(f"\u2705 Wybrano szukanie terminów do godziny: {time_input}")

    await prepare_summary(user_data, update_message)

    return VERIFY_SUMMARY


async def get_to_time_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    query = cast(CallbackQuery, update.callback_query)

    await query.answer()

    user_action = cast(str, query.data)

    selected_date = handle_time_selection(user_action, user_data, "to_time")
    if selected_date is None:
        reply_markup = update_time_selection_buttons(user_data, "to_time")

        try:
            await query.edit_message_text(
                "Szukaj terminów po godzinie albo zapisz w formacie HH:MM, np. 21:00", reply_markup=reply_markup
            )
        except telegram.error.BadRequest:
            pass

        return GET_TO_TIME

    await query.edit_message_text(f"\u2705 Wybrano szukanie terminów do godziny: {selected_date}")

    query_message = cast(Message, query.message)
    await prepare_summary(user_data, query_message)

    return VERIFY_SUMMARY


async def verify_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    query_message = cast(Message, query.message)
    user_data = cast(UserDataDataclass, context.user_data)

    await query.answer()
    data = cast(str, query.data)

    if data == NO_ANSWER:
        await query_message.reply_text("Zacznijmy od poczatku")
        return await new_monitoring_entrypoint(update, context)

    summary_text = "Podsumowanie:\n"
    summary_text += get_summary_text(user_data)

    await query.edit_message_text(f"\u2705 {summary_text}")

    current_booking_number = user_data["current_booking_number"]

    location_id = user_data["bookings"][current_booking_number]["location"]["location_id"]
    specialization_id = user_data["bookings"][current_booking_number]["specialization"]["specialization_id"]
    clinic_id = user_data["bookings"][current_booking_number]["clinic"]["clinic_id"]
    doctor_id = user_data["bookings"][current_booking_number]["doctor"]["doctor_id"]
    from_date = user_data["bookings"][current_booking_number]["from_date"]
    from_date_str = f"{from_date['day']}-{from_date['month']}-{from_date['year']}"
    from_time = user_data["bookings"][current_booking_number]["from_time"]
    from_time_str = f"{from_time['hour']}:{from_time['minute']}"
    to_date = user_data["bookings"][current_booking_number]["to_date"]
    to_date_str = f"{to_date['day']}-{to_date['month']}-{to_date['year']}"
    to_time = user_data["bookings"][current_booking_number]["to_time"]
    to_time_str = f"{to_time['hour']}:{to_time['minute']}"

    user_data["bookings"][current_booking_number]["booking_hash"] = hashlib.md5(summary_text.encode()).hexdigest()

    update_message = cast(Message, query.message)

    client = user_data.get("medicover_client")
    if not client:
        await update_message.reply_text("Please log in first.")
        return ConversationHandler.END

    available_slots = await client.get_available_slots(
        location_id,
        specialization_id,
        from_date_str,
        from_time_str,
        to_time_str,
        doctor_id,
        clinic_id,
    )

    parsed_available_slot = []
    search_to_date = datetime.strptime(f"{to_date_str} {to_time_str}", "%d-%m-%Y %H:%M")
    for slot in available_slots:
        appointment_date = datetime.fromisoformat(slot["appointmentDate"])
        if appointment_date < search_to_date:
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
    user_data = cast(UserDataDataclass, context.user_data)
    query = cast(CallbackQuery, update.callback_query)
    query_message = cast(Message, query.message)

    client = cast(MedicoverClient, user_data["medicover_client"])

    current_booking_number = user_data["current_booking_number"]

    location_id = user_data["bookings"][current_booking_number]["location"]["location_id"]
    specialization_id = user_data["bookings"][current_booking_number]["specialization"]["specialization_id"]
    clinic_id = user_data["bookings"][current_booking_number]["clinic"]["clinic_id"]
    doctor_id = user_data["bookings"][current_booking_number]["doctor"]["doctor_id"]
    from_date = user_data["bookings"][current_booking_number]["from_date"]
    from_date_str = f"{from_date['day']}-{from_date['month']}-{from_date['year']}"
    from_time = user_data["bookings"][current_booking_number]["from_time"]
    from_time_str = f"{from_time['hour']}:{from_time['minute']}"
    to_date = user_data["bookings"][current_booking_number]["to_date"]
    to_date_str = f"{to_date['day']}-{to_date['month']}-{to_date['year']}"
    to_time = user_data["bookings"][current_booking_number]["to_time"]
    to_time_str = f"{to_time['hour']}:{to_time['minute']}"

    kwargs = {
        "region_id": location_id,
        "specialization_id": specialization_id,
        "doctor_id": doctor_id,
        "clinic_id": clinic_id,
        "from_date": from_date_str,
        "from_time": from_time_str,
        "to_time": to_time_str,
    }

    search_to_date = datetime.strptime(f"{to_date_str} {to_time_str}", "%d-%m-%Y %H:%M")

    while True:
        slots = await client.get_available_slots(**kwargs)
        parsed_available_slot = []

        for slot in slots:
            appointment_date = datetime.fromisoformat(slot["appointmentDate"])
            if appointment_date < search_to_date:
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
    user_data = cast(UserDataDataclass, context.user_data)

    await query.answer()
    data = cast(str, query.data)

    if data == NO_ANSWER:
        return ConversationHandler.END

    summary_text = get_summary_text(user_data)

    await query.edit_message_text(f"\u2705 Tworzenie monitoringu dla parametrów:\n{summary_text}")

    current_booking_number = user_data["current_booking_number"]
    task_hash = user_data["bookings"][current_booking_number]["booking_hash"]

    if user_data.get("booking_hashes") is None:
        user_data["booking_hashes"] = {}

    user_data["booking_hashes"][task_hash] = current_booking_number

    context.application.create_task(
        create_monitoring_task(update, context), update=update, name=f"{user_chat_id}_{task_hash}"
    )

    await query_message.reply_text("Monitoring został utworzony.")

    return ConversationHandler.END
