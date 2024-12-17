from datetime import datetime
from typing import cast

from telegram import Message, Update
from telegram.ext import ContextTypes, ConversationHandler

from src.locale_handler import _
from src.medicover_client.types import AppointmentItem
from src.telegram_interface.user_data import UserDataDataclass


async def future_appointments_entrypoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(UserDataDataclass, context.user_data)
    update_message = cast(Message, update.message)
    client = user_data.get("medicover_client")
    if not client:
        await update_message.reply_text(_("Please log in first.", user_data["language"]))
        return ConversationHandler.END

    future_appointments: list[AppointmentItem] = await client.get_future_appointments()

    if not future_appointments:
        await update_message.reply_text(_("You have no future appointments.", user_data["language"]))
        return ConversationHandler.END

    await update_message.reply_text(_("You have the following future appointments:", user_data["language"]))

    for future_appointment in future_appointments:
        appointment_date = datetime.fromisoformat(future_appointment["date"])
        doctor_name = future_appointment["doctor"]["name"]
        clinic_name = future_appointment["clinic"]["name"]
        specialization_name = future_appointment["specialty"]["name"]

        await update_message.reply_text(
            f"{_("Date:", user_data["language"])} {appointment_date.strftime("%H:%M %d-%m-%Y")}\n"
            f"{_("Doctor:", user_data["language"])} {doctor_name}\n"
            f"{_("Specialization:", user_data["language"])} {specialization_name}\n"
            f"{_("Clinic:", user_data["language"])} {clinic_name}"
        )

    return ConversationHandler.END
