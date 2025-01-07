import asyncio
import hashlib
import logging
from datetime import date, datetime, time
from typing import cast

import httpx
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

from src.locale_handler import _
from src.medicover_client.client import MedicoverClient
from src.medicover_client.types import SlotItem
from src.telegram_interface.helpers import (
    NO_ANSWER,
    YES_ANSWER,
    get_summary_text,
    handle_date_selection,
    handle_time_selection,
    match_input_to_filter,
    prepare_clinic_keyboard,
    prepare_date_selection,
    prepare_doctor_keyboard,
    prepare_specialization_keyboard,
    prepare_summary,
    prepare_time_keyboard,
    send_to_dev_message,
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


async def new_monitoring_entrypoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if message is None:
        callback_query = cast(CallbackQuery, update.callback_query)
        message = cast(Message, callback_query.message)

    user_data = cast(UserDataDataclass, context.user_data)

    client = user_data.get("medicover_client")
    if not client:
        await message.reply_text(_("Please log in first.", user_data["language"]))
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
            _(
                "Type in a snippet of the city you are looking for, or select from your recent searches",
                user_data["language"],
            ),
            reply_markup=reply_markup,
        )

    else:
        await message.reply_text(_("Enter a fragment of the city you are looking for:", user_data["language"]))
    return GET_LOCATION


async def get_location_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)
    await query.answer()

    location_id = cast(str, query.data)

    location = next((item for item in user_data["history"]["locations"] if item["location_id"] == location_id), None)
    if not location:
        return ConversationHandler.END

    location_text = location["location_name"]

    bookings = user_data.get("bookings")

    if not bookings:
        user_data["bookings"] = {}

    next_booking_number = next(reversed(user_data["bookings"])) + 1

    user_data["current_booking_number"] = next_booking_number
    user_data["bookings"][next_booking_number] = {"location": location}

    await query.edit_message_text(f"\u2705 {_("Selected city:",user_data["language"])} {location_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_specialization_keyboard(user_data)

    await query_message.reply_text(
        _(
            "Type in a snippet of the specialization you are looking for, or select from your recent searches",
            user_data["language"],
        ),
        reply_markup=reply_markup,
    )

    return GET_SPECIALIZATION


async def get_location_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    update_message = cast(Message, update.message)
    location_input = cast(str, update_message.text)

    all_locations = await client.get_all_regions()

    found_locations = match_input_to_filter(location_input, all_locations)

    if not found_locations:
        await update_message.reply_text(_("City not found. Please re-enter.", user_data["language"]))
        return GET_LOCATION

    user_data["history"]["temp_data"]["locations"] = {location["id"]: location["value"] for location in found_locations}
    keyboard = [
        [InlineKeyboardButton(location["value"], callback_data=str(location["id"]))] for location in found_locations
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update_message.reply_text(
        _("Select a city from the list:", user_data["language"]),
        reply_markup=reply_markup,
    )

    return READ_LOCATION


async def read_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)

    await query.answer()

    user_input_location_id = cast(str, query.data)
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

    await query.edit_message_text(f"\u2705 {_("Selected city:",user_data["language"])} {location_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_specialization_keyboard(user_data)

    await query_message.reply_text(
        _(
            "Type in a snippet of the specialization you are looking for, or select from your recent searches",
            user_data["language"],
        ),
        reply_markup=reply_markup,
    )

    return GET_SPECIALIZATION


async def get_specialization_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)
    await query.answer()

    specialization_id = cast(str, query.data)
    specialization = next(
        (item for item in user_data["history"]["specializations"] if item["specialization_id"] == specialization_id),
        None,
    )
    if not specialization:
        return ConversationHandler.END

    specialization_text = specialization["specialization_name"]

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["specialization"] = specialization

    await query.edit_message_text(f"\u2705 {_("Selected specialization:",user_data["language"])} {specialization_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_clinic_keyboard(user_data, specialization_id)

    await query_message.reply_text(
        _(
            "Type in a snippet of the clinic you are looking for, or select from your recent searches",
            user_data["language"],
        ),
        reply_markup=reply_markup,
    )

    return GET_CLINIC


async def get_specialization_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    specialization_input = cast(str, update_message.text)
    booking_number = user_data["current_booking_number"]
    location_id: str = user_data["bookings"][booking_number]["location"]["location_id"]

    all_specializations = await client.get_all_specializations(location_id)

    found_specializations = match_input_to_filter(specialization_input, all_specializations)

    if not found_specializations:
        await update_message.reply_text(_("Specialization not found. Please re-enter.", user_data["language"]))
        return GET_SPECIALIZATION

    user_data["history"]["temp_data"]["specializations"] = {
        specialization["id"]: specialization["value"] for specialization in found_specializations
    }

    keyboard = [[InlineKeyboardButton(spec["value"], callback_data=str(spec["id"]))] for spec in found_specializations]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update_message.reply_text(
        _("Select specialization:", user_data["language"]),
        reply_markup=reply_markup,
    )

    return READ_SPECIALIZATION


async def read_specialization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(UserDataDataclass, context.user_data)

    await query.answer()

    user_input_specialization_id = cast(str, query.data)
    temp_specializations = user_data["history"]["temp_data"]["specializations"]
    specialization_text = temp_specializations[user_input_specialization_id]
    specialization = Specialization(
        specialization_id=user_input_specialization_id, specialization_name=specialization_text
    )

    user_data["history"]["specializations"].append(specialization)

    booking_number = user_data["current_booking_number"]
    user_data["bookings"][booking_number]["specialization"] = specialization

    await query.edit_message_text(f"\u2705 {_("Selected specialization:",user_data["language"])} {specialization_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_clinic_keyboard(user_data, user_input_specialization_id)
    await query_message.reply_text(
        _(
            "Type in a snippet of the clinic you are looking for, or select from your recent searches",
            user_data["language"],
        ),
        reply_markup=reply_markup,
    )

    return GET_CLINIC


async def get_clinic_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)
    await query.answer()

    user_input_clinic_id = cast(str, query.data)

    current_booking_number = user_data["current_booking_number"]

    specialization_id = user_data["bookings"][current_booking_number]["specialization"]["specialization_id"]

    if user_input_clinic_id == "any":
        clinic_text = _("Any-her", user_data["language"])
        clinic = Clinic(clinic_id=None, clinic_name=clinic_text)
    else:
        clinic = next(
            (
                item
                for item in user_data["history"]["clinics"][specialization_id]
                if item["clinic_id"] == user_input_clinic_id
            ),
            None,  # type: ignore
        )
        if clinic is None:
            return ConversationHandler.END

    user_data["bookings"][current_booking_number]["clinic"] = clinic
    clinic_text = clinic["clinic_name"]

    await query.edit_message_text(f"\u2705 {_("Selected clinic:",user_data["language"])} {clinic_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_doctor_keyboard(user_data, specialization_id)

    await query_message.reply_text(
        _(
            "Type in a snippet of the doctor you are looking for, or select from your recent searches",
            user_data["language"],
        ),
        reply_markup=reply_markup,
    )

    return GET_DOCTOR


async def get_clinic_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    clinic_input = cast(str, update_message.text)
    booking_number = user_data["current_booking_number"]
    location_id = user_data["bookings"][booking_number]["location"]["location_id"]
    specialization_id = user_data["bookings"][booking_number]["specialization"]["specialization_id"]

    all_clinics = await client.get_all_clinics(location_id, specialization_id)

    found_clinics = match_input_to_filter(clinic_input, all_clinics)

    if not found_clinics:
        await update_message.reply_text(_("Clinic not found. Please re-enter.", user_data["language"]))

        return GET_CLINIC

    user_data["history"]["temp_data"]["clinics"] = {clinic["id"]: clinic["value"] for clinic in found_clinics}

    keyboard = [[InlineKeyboardButton(clinic["value"], callback_data=str(clinic["id"]))] for clinic in found_clinics]
    keyboard.append([InlineKeyboardButton(_("Any-her", user_data["language"]), callback_data="any")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update_message.reply_text(_("Select clinic:", user_data["language"]), reply_markup=reply_markup)

    return READ_CLINIC


async def read_clinic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(UserDataDataclass, context.user_data)

    await query.answer()

    booking_number = user_data["current_booking_number"]
    specialization_id = user_data["bookings"][booking_number]["specialization"]["specialization_id"]

    if query.data == "any":
        clinic_name = _("Any-her", user_data["language"])
        clinic = Clinic(clinic_id=None, clinic_name=clinic_name)
    else:
        user_input_clinic_id = cast(str, query.data)
        temp_clinics = user_data["history"]["temp_data"]["clinics"]
        clinic_name = temp_clinics[user_input_clinic_id]
        clinic = Clinic(clinic_id=user_input_clinic_id, clinic_name=clinic_name)

        if specialization_id not in user_data["history"]["clinics"]:
            user_data["history"]["clinics"][specialization_id] = []

        user_data["history"]["clinics"][specialization_id].append(clinic)

    user_data["bookings"][booking_number]["clinic"] = clinic

    await query.edit_message_text(f"\u2705 {_("Selected clinic:",user_data["language"])} {clinic_name}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_doctor_keyboard(user_data, specialization_id)
    await query_message.reply_text(
        _(
            "Type in a snippet of the doctor you are looking for, or select from your recent searches",
            user_data["language"],
        ),
        reply_markup=reply_markup,
    )

    return GET_DOCTOR


async def get_doctor_from_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    query = cast(CallbackQuery, update.callback_query)
    await query.answer()

    user_input_doctor_id = cast(str, query.data)

    current_booking_number = user_data["current_booking_number"]

    specialization_id = user_data["bookings"][current_booking_number]["specialization"]["specialization_id"]

    if user_input_doctor_id == "any":
        doctor_text = _("Any-him", user_data["language"])
        doctor = Doctor(doctor_name=doctor_text, doctor_id=None)
    else:
        doctor = next(
            (
                item
                for item in user_data["history"]["doctors"][specialization_id]
                if item["doctor_id"] == user_input_doctor_id
            ),
            None,  # type: ignore
        )
        if doctor is None:
            return ConversationHandler.END

    user_data["bookings"][current_booking_number]["doctor"] = doctor
    doctor_text = doctor["doctor_name"]

    await query.edit_message_text(f"\u2705 {_("Selected doctor:",user_data["language"])} {doctor_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_date_selection(user_data, "from_date")

    message = await query_message.reply_text(
        _("Select date FROM or enter in dd-mm-yyyy format, e.g. 04-11-2024", user_data["language"]),
        reply_markup=reply_markup,
    )
    user_data["bookings"][current_booking_number]["message_id"] = message.message_id

    return GET_FROM_DATE


async def get_doctor_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    client = user_data.get("medicover_client")
    if not client:
        update_message = cast(Message, update.message)
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    doctor_input = cast(str, update_message.text)
    booking_number = user_data["current_booking_number"]
    location_id = user_data["bookings"][booking_number]["location"]["location_id"]
    specialization_id = user_data["bookings"][booking_number]["specialization"]["specialization_id"]
    clinic_id = user_data["bookings"][booking_number]["clinic"]["clinic_id"]

    all_doctors = await client.get_all_doctors(location_id, specialization_id, clinic_id)

    found_doctors = match_input_to_filter(doctor_input, all_doctors)

    if not found_doctors:
        await update_message.reply_text(_("Doctor not found. Please re-enter.", user_data["language"]))

        return GET_DOCTOR

    user_data["history"]["temp_data"]["doctors"] = {doctor["id"]: doctor["value"] for doctor in found_doctors}

    keyboard = [[InlineKeyboardButton(doctor["value"], callback_data=str(doctor["id"]))] for doctor in found_doctors]
    keyboard.append([InlineKeyboardButton(_("Any-him", user_data["language"]), callback_data="any")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update_message.reply_text(_("Select doctor:", user_data["language"]), reply_markup=reply_markup)

    return READ_DOCTOR


async def read_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = cast(CallbackQuery, update.callback_query)
    user_data = cast(UserDataDataclass, context.user_data)

    await query.answer()

    booking_number = user_data["current_booking_number"]
    specialization_id = user_data["bookings"][booking_number]["specialization"]["specialization_id"]

    if query.data == "any":
        doctor_text = _("Any-him", user_data["language"])
        doctor = Doctor(doctor_name=doctor_text, doctor_id=None)
    else:
        user_input_doctor_id = cast(str, query.data)
        temp_doctors = user_data["history"]["temp_data"]["doctors"]
        doctor_text = temp_doctors[user_input_doctor_id]
        doctor = Doctor(doctor_name=doctor_text, doctor_id=user_input_doctor_id)

        if specialization_id not in user_data["history"]["doctors"]:
            user_data["history"]["doctors"][specialization_id] = []

        user_data["history"]["doctors"][specialization_id].append(doctor)

    user_data["bookings"][booking_number]["doctor"] = doctor

    await query.edit_message_text(f"\u2705 {_("Selected doctor:",user_data["language"])} {doctor_text}")

    query_message = cast(Message, query.message)

    reply_markup = prepare_date_selection(user_data, "from_date")

    await query_message.reply_text(
        _("Select date FROM or enter in dd-mm-yyyy format, e.g. 04-11-2024", user_data["language"]),
        reply_markup=reply_markup,
    )

    return GET_FROM_DATE


async def get_from_date_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    date_input = cast(str, update_message.text)
    try:
        date_object = datetime.strptime(date_input, "%d-%m-%Y")
    except ValueError:
        await update_message.reply_text(
            _("The date format you entered is invalid. Please re-enter.", user_data["language"])
        )
        return GET_FROM_DATE

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["from_date"] = MonitoringDate(
        day=date_object.day, month=date_object.month, year=date_object.year
    )

    await context.bot.delete_message(
        chat_id=cast(Chat, update.effective_chat).id,
        message_id=user_data["bookings"][current_booking_number]["message_id"],
    )

    await update_message.reply_text(f"\u2705 {_("Search date selected from:",user_data["language"])} {date_input}")

    hour = 7
    minute = 0

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["from_time"] = MonitoringTime(hour=hour, minute=minute)

    reply_markup = prepare_time_keyboard(hour, minute, user_data["language"])

    query_message = cast(Message, update.message)
    message = await query_message.reply_text(
        _("Look for appointments AFTER the hour or enter in HH:MM format, e.g. 10:00", user_data["language"]),
        reply_markup=reply_markup,
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
                _("Select date FROM or enter in dd-mm-yyyy format, e.g. 04-11-2024", user_data["language"]),
                reply_markup=reply_markup,
            )
        except telegram.error.BadRequest:
            pass

        return GET_FROM_DATE

    await query.edit_message_text(f"\u2705 {_("Search date selected from:",user_data["language"])} {selected_date}")

    query_message = cast(Message, query.message)

    hour = 7
    minute = 0

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["from_time"] = MonitoringTime(hour=hour, minute=minute)

    reply_markup = prepare_time_keyboard(hour, minute, user_data["language"])

    message = await query_message.reply_text(
        _("Look for appointments AFTER the hour or enter in HH:MM format, e.g. 10:00", user_data["language"]),
        reply_markup=reply_markup,
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
        await update_message.reply_text(
            _("The time format you entered is invalid. Please re-enter.", user_data["language"])
        )
        return GET_FROM_TIME

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["from_time"] = MonitoringTime(
        hour=time_object.hour, minute=time_object.minute
    )

    await context.bot.delete_message(
        chat_id=cast(Chat, update.effective_chat).id,
        message_id=user_data["bookings"][current_booking_number]["message_id"],
    )

    await update_message.reply_text(
        f"\u2705 {_("Selected to search for appointments after the hour:",user_data["language"])} {time_input}"
    )

    reply_markup = prepare_date_selection(user_data, "to_date")

    await update_message.reply_text(
        _("Select date UNTIL or enter in dd-mm-yyyy format, e.g. 04-11-2024", user_data["language"]),
        reply_markup=reply_markup,
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
                _("Look for appointments AFTER the hour or enter in HH:MM format, e.g. 10:00", user_data["language"]),
                reply_markup=reply_markup,
            )
        except telegram.error.BadRequest:
            pass

        return GET_FROM_TIME

    await query.edit_message_text(
        f"\u2705 {_("Selected to search for appointments after the hour:",user_data["language"])} {selected_date}"
    )

    query_message = cast(Message, query.message)

    reply_markup = prepare_date_selection(user_data, "to_date")

    await query_message.reply_text(
        _("Select date UNTIL or enter in dd-mm-yyyy format, e.g. 04-11-2024", user_data["language"]),
        reply_markup=reply_markup,
    )

    return GET_TO_DATE


async def get_to_date_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)

    date_input = cast(str, update_message.text)
    try:
        date_object = datetime.strptime(date_input, "%d-%m-%Y")
    except ValueError:
        await update_message.reply_text(
            _("The date format you entered is invalid. Please re-enter.", user_data["language"])
        )
        return GET_TO_DATE

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["to_date"] = MonitoringDate(
        day=date_object.day, month=date_object.month, year=date_object.year
    )

    await context.bot.delete_message(
        chat_id=cast(Chat, update.effective_chat).id,
        message_id=user_data["bookings"][current_booking_number]["message_id"],
    )

    await update_message.reply_text(f"\u2705 {_("Search date selected until:",user_data["language"])} {date_input}")

    hour = 22
    minute = 0

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["to_time"] = MonitoringTime(hour=hour, minute=minute)

    reply_markup = prepare_time_keyboard(hour, minute, user_data["language"])

    query_message = cast(Message, update.message)
    message = await query_message.reply_text(
        _("Look for appointments BEFORE the hour or enter in HH:MM format, e.g. 21:00", user_data["language"]),
        reply_markup=reply_markup,
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
                _("Select date UNTIL or enter in dd-mm-yyyy format, e.g. 04-11-2024", user_data["language"]),
                reply_markup=reply_markup,
            )
        except telegram.error.BadRequest:
            pass

        return GET_TO_DATE

    await query.edit_message_text(f"\u2705 {_("Search date selected until:",user_data["language"])} {selected_date}")

    query_message = cast(Message, query.message)

    hour = 22
    minute = 0

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["to_time"] = MonitoringTime(hour=hour, minute=minute)

    reply_markup = prepare_time_keyboard(hour, minute, user_data["language"])

    message = await query_message.reply_text(
        _("Look for appointments BEFORE the hour or enter in HH:MM format, e.g. 21:00", user_data["language"]),
        reply_markup=reply_markup,
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
        await update_message.reply_text(
            _("The time format you entered is invalid. Please re-enter.", user_data["language"])
        )
        return GET_TO_TIME

    current_booking_number = user_data["current_booking_number"]
    user_data["bookings"][current_booking_number]["to_time"] = MonitoringTime(
        hour=time_object.hour, minute=time_object.minute
    )

    await context.bot.delete_message(
        chat_id=cast(Chat, update.effective_chat).id,
        message_id=user_data["bookings"][current_booking_number]["message_id"],
    )

    await update_message.reply_text(
        f"\u2705 {_("Selected to search for appointments before the hour:",user_data["language"])} {time_input}"
    )

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
                _("Look for appointments BEFORE the hour or enter in HH:MM format, e.g. 21:00", user_data["language"]),
                reply_markup=reply_markup,
            )
        except telegram.error.BadRequest:
            pass

        return GET_TO_TIME

    await query.edit_message_text(
        f"\u2705 {_("Selected to search for appointments before the hour:",user_data["language"])} {selected_date}"
    )

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
        await query_message.reply_text(_("Let's start from the beginning", user_data["language"]))
        return await new_monitoring_entrypoint(update, context)

    summary_text = f"{_("Summary:",user_data["language"])}\n"
    summary_text += get_summary_text(user_data)

    await query.edit_message_text(f"\u2705 {summary_text}")

    current_booking_number = user_data["current_booking_number"]

    location_id = user_data["bookings"][current_booking_number]["location"]["location_id"]
    specialization_id = user_data["bookings"][current_booking_number]["specialization"]["specialization_id"]
    clinic_id = user_data["bookings"][current_booking_number]["clinic"]["clinic_id"]
    doctor_id = user_data["bookings"][current_booking_number]["doctor"]["doctor_id"]
    from_date = user_data["bookings"][current_booking_number]["from_date"]
    from_time = user_data["bookings"][current_booking_number]["from_time"]
    to_date = user_data["bookings"][current_booking_number]["to_date"]
    to_time = user_data["bookings"][current_booking_number]["to_time"]

    user_data["bookings"][current_booking_number]["booking_hash"] = hashlib.md5(summary_text.encode()).hexdigest()

    update_message = cast(Message, query.message)

    client = user_data.get("medicover_client")
    if not client:
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    from_date_obj = date(
        year=from_date["year"],
        month=from_date["month"],
        day=from_date["day"],
    )

    available_slots = await client.get_available_slots(
        location_id,
        specialization_id,
        from_date_obj,
        doctor_id,
        clinic_id,
    )

    parsed_available_slot = []
    from_time_obj = time(hour=from_time["hour"], minute=from_time["minute"])
    to_time_obj = time(hour=to_time["hour"], minute=to_time["minute"])

    to_date_obj = datetime(
        year=to_date["year"],
        month=to_date["month"],
        day=to_date["day"],
        hour=23,
        minute=59,
    )
    for slot in available_slots:
        appointment_date = datetime.fromisoformat(slot["appointmentDate"])
        if from_time_obj <= appointment_date.time() <= to_time_obj and appointment_date <= to_date_obj:
            parsed_available_slot.append(slot)

    if not parsed_available_slot:
        await query_message.reply_text(_("No appointments available for selected parameters.", user_data["language"]))

        keyboard = [
            [InlineKeyboardButton(_("Yes", user_data["language"]), callback_data=YES_ANSWER)],
            [InlineKeyboardButton(_("No", user_data["language"]), callback_data=NO_ANSWER)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query_message.reply_text(
            f"\u2754 {_("Do you want to create a new monitoring?",user_data["language"])}", reply_markup=reply_markup
        )

        return READ_CREATE_MONITORING

    await query_message.reply_text(_("Available appointments:", user_data["language"]))

    for slot in parsed_available_slot:
        # TODO fix the translation
        await query_message.reply_text(
            f"Lekarz: {slot["doctor"]["name"]}\nKlinika: {slot["clinic"]["name"]}\nData: {slot['appointmentDate']}"
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
    from_time = user_data["bookings"][current_booking_number]["from_time"]
    to_date = user_data["bookings"][current_booking_number]["to_date"]
    to_time = user_data["bookings"][current_booking_number]["to_time"]

    from_date_obj = date(
        year=from_date["year"],
        month=from_date["month"],
        day=from_date["day"],
    )

    from_time_obj = time(hour=from_time["hour"], minute=from_time["minute"])
    to_time_obj = time(hour=to_time["hour"], minute=to_time["minute"])

    to_date_obj = datetime(
        year=to_date["year"],
        month=to_date["month"],
        day=to_date["day"],
        hour=23,
        minute=59,
    )

    while True:
        try:
            available_slots: list[SlotItem] = await client.get_available_slots(
                location_id,
                specialization_id,
                from_date_obj,
                doctor_id,
                clinic_id,
            )
        except httpx.TimeoutException:
            logger.error("Timeout error. Retrying...")
            await send_to_dev_message(context, "Timeout error")
            await asyncio.sleep(30)
            continue
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                logger.error("Too many requests. Retrying...")
                await send_to_dev_message(context, "Too many requests error.")
                await asyncio.sleep(300)
                continue
            else:
                raise e
        except Exception as e:
            error_message = f"{type(e).__name__}: {e!s}\n"
            logger.error("An error occurred: %s", error_message)
            await send_to_dev_message(context, error_message)
            await asyncio.sleep(600)
            continue

        parsed_available_slot = []

        for slot in available_slots:
            appointment_date = datetime.fromisoformat(slot["appointmentDate"])
            if from_time_obj <= appointment_date.time() <= to_time_obj and appointment_date <= to_date_obj:
                parsed_available_slot.append(slot)

        if parsed_available_slot:
            for slot in parsed_available_slot:
                await query_message.reply_text(_("A new appointment has been found.", user_data["language"]))

                # TODO fix the translation
                await query_message.reply_text(
                    f"Lekarz: {slot["doctor"]["name"]}\n"
                    f"Klinika: {slot["clinic"]["name"]}\n"
                    f"Data: {slot["appointmentDate"]}"
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

    await query.edit_message_text(
        f"\u2705 {_("Creating monitoring for parameters:",user_data["language"])}\n{summary_text}"
    )

    current_booking_number = user_data["current_booking_number"]
    task_hash = user_data["bookings"][current_booking_number]["booking_hash"]

    if user_data.get("booking_hashes") is None:
        user_data["booking_hashes"] = {}

    user_data["booking_hashes"][task_hash] = current_booking_number

    context.application.create_task(
        create_monitoring_task(update, context), update=update, name=f"{user_chat_id}_{task_hash}"
    )

    await query_message.reply_text(_("Monitoring has been set up.", user_data["language"]))

    return ConversationHandler.END
