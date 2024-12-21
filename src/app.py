import asyncio
import logging.config
import os
from datetime import date, datetime, timedelta
from typing import cast

import asyncclick as click
import httpx
from dotenv import load_dotenv
from pick import pick

from src.app_notifiers import Notifier, TelegramNotifier
from src.logger_config import configure_logging
from src.medicover_client.client import FilterDataType, MedicoverClient
from src.medicover_client.exceptions import IncorrectLoginError
from src.medicover_client.types import SlotItem

load_dotenv()

configure_logging()

logger = logging.getLogger(__name__)


def match_input_to_filter(user_text: str, filters_data: list[FilterDataType]) -> list[FilterDataType]:
    selected_filters = []
    for available_filter in filters_data:
        if user_text.lower() in available_filter["value"].lower():
            selected_filters.append(available_filter)
    return selected_filters


def pick_from_items(items: list[FilterDataType], title: str) -> FilterDataType:
    options = [location["value"] for location in items]
    option, index = pick(options, title)
    return cast(FilterDataType, items[index])


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option(
    "--username",
    "-u",
    prompt="Username",
    help="Medicover username",
    type=str,
    default=lambda: os.getenv("MEDICOVER_USERNAME", ""),
    show_default="Value from .env or empty",
)
@click.option(
    "--password",
    "-p",
    prompt="Password",
    help="Medicover password",
    hide_input=True,
    type=str,
    default=lambda: os.getenv("MEDICOVER_PASSWORD", ""),
    show_default="Value from .env or empty",
)
@click.option("--location-id", "-l", help="Location ID", type=str)
@click.option("--specialization-id", "-s", help="Specialization ID", type=str)
@click.option("--clinic-id", "-c", help="Clinic ID", type=str)
@click.option("--doctor-id", "-d", help="Doctor ID", type=str)
@click.option(
    "--date-start",
    "-ds",
    help="Start date of search",
    type=click.DateTime(formats=["%d-%m-%Y"]),
    default=date.today().strftime("%d-%m-%Y"),
    show_default="Today",
)
@click.option(
    "--time-start",
    "-ts",
    help="Start time of search",
    type=click.DateTime(formats=["%H:%M"]),
    default="07:00",
    show_default="07:00",
)
@click.option(
    "--date-end",
    "-de",
    help="End date of search",
    type=click.DateTime(formats=["%d-%m-%Y"]),
    default=(date.today() + timedelta(days=30)).strftime("%d-%m-%Y"),
    show_default="30 days from today",
)
@click.option(
    "--time-end",
    "-te",
    help="End time of search",
    type=click.DateTime(formats=["%H:%M"]),
    default="23:00",
    show_default="23:00",
)
@click.option(
    "--notifier",
    "-n",
    help="Notifier to send notifications to. ex. telegram",
    type=click.Choice(["telegram"]),
)
async def new_monitoring(
    username: str,
    password: str,
    location_id: str | None,
    specialization_id: str | None,
    clinic_id: str | None,
    doctor_id: str | None,
    date_start: datetime,
    time_start: datetime,
    date_end: datetime,
    time_end: datetime,
    notifier: str | None,
) -> None:
    logger.info("Starting new monitoring")
    client = MedicoverClient(username, password)
    try:
        await client.log_in()
    except IncorrectLoginError:
        click.secho("Unsuccessful logging in. Check username and password", fg="red")
        return

    all_locations = await client.get_all_regions()

    if location_id is None:
        logger.info("No location ID provided. Picking location from user input")
        location_input = click.prompt("Enter a city or part of it", type=str)
        matching_locations = match_input_to_filter(location_input, all_locations)

        logger.info("Found %s matching locations", len(matching_locations))

        if not matching_locations:
            region = pick_from_items(all_locations, "City not found. Select the location from the list:")
        elif len(matching_locations) > 1:
            region = pick_from_items(matching_locations, "Select the region")
        else:
            region = matching_locations[0]

    else:
        logger.info("Location ID provided. Using provided location ID")
        matching_location = next((location for location in all_locations if location["id"] == location_id), None)
        if not matching_location:
            region = pick_from_items(all_locations, "City not found. Select the location from the list:")
        else:
            region = matching_location

    logger.info("Selected region: id=%s, value=%s", region["id"], region["value"])
    location_id = region["id"]

    click.secho(f"Selected region: {region["value"]} (id={region["id"]})", fg="green")

    all_specializations = await client.get_all_specializations(region["id"])

    if specialization_id is None:
        logger.info("No specialization ID provided. Picking specialization from user input")
        specialization_input = click.prompt("Enter a specialization or part of it", type=str)
        matching_specializations = match_input_to_filter(specialization_input, all_specializations)

        logger.info("Found %s matching specializations", len(matching_specializations))

        if not matching_specializations:
            specialization = pick_from_items(
                all_specializations, "Specialization not found. Select the specialization from the list:"
            )
        elif len(matching_specializations) > 1:
            specialization = pick_from_items(matching_specializations, "Select the specialization")
        else:
            specialization = matching_specializations[0]
    else:
        logger.info("Specialization ID provided. Using provided specialization ID")
        matching_specialization: FilterDataType | None = next(
            (specialization for specialization in all_specializations if specialization["id"] == specialization_id),
            None,
        )
        if not matching_specialization:
            specialization = pick_from_items(
                all_specializations, "Specialization not found. Select the specialization from the list:"
            )
        else:
            specialization = matching_specialization
    logger.info("Selected specialization: id=%s, value=%s", specialization["id"], specialization["value"])
    specialization_id = specialization["id"]

    click.secho(f"Selected specialization: {specialization["value"]} (id={specialization["id"]})", fg="green")

    all_clinics = await client.get_all_clinics(region["id"], specialization["id"])

    if clinic_id is None:
        logger.info("No clinic ID provided. Picking clinic from user input")
        clinic_input = click.prompt(
            "Enter a clinic or part of it or Enter for any", type=str, default="", show_default=False
        )
        if clinic_input == "":
            clinic = FilterDataType(id=None, value="Any")  # type: ignore
        else:
            matching_clinics = match_input_to_filter(clinic_input, all_clinics)

            if not matching_clinics:
                clinic = pick_from_items(all_clinics, "Clinic not found. Select the clinic from the list:")
            elif len(matching_clinics) > 1:
                clinic = pick_from_items(matching_clinics, "Select the clinic")
            else:
                clinic = matching_clinics[0]
    else:
        logger.info("Clinic ID provided. Using provided clinic ID")
        matching_clinic = next((clinic for clinic in all_clinics if clinic["id"] == clinic_id), None)
        if not matching_clinic:
            clinic = pick_from_items(all_clinics, "Clinic not found. Select the clinic from the list:")
        else:
            clinic = matching_clinic

    logger.info("Selected clinic: id=%s, value=%s", clinic["id"], clinic["value"])
    clinic_id = clinic["id"]

    click.secho(f"Selected clinic: {clinic["value"]} (id={clinic["id"]})", fg="green")

    all_doctors = await client.get_all_doctors(region["id"], specialization["id"], clinic["id"])

    if doctor_id is None:
        logger.info("No doctor ID provided. Picking doctor from user input")
        doctor_input = click.prompt(
            "Enter a doctor or part of it or Enter for any", type=str, default="", show_default=False
        )
        if doctor_input == "":
            doctor = FilterDataType(id=None, value="Any")  # type: ignore
        else:
            matching_doctors = match_input_to_filter(doctor_input, all_doctors)

            if not matching_doctors:
                doctor = pick_from_items(all_doctors, "Doctor not found. Select the doctor from the list:")
            elif len(matching_doctors) > 1:
                doctor = pick_from_items(matching_doctors, "Select the doctor")
            else:
                doctor = matching_doctors[0]
    else:
        logger.info("Doctor ID provided. Using provided doctor ID")
        matching_doctor = next((doctor for doctor in all_doctors if doctor["id"] == doctor_id), None)
        if not matching_doctor:
            doctor = pick_from_items(all_doctors, "Doctor not found. Select the doctor from the list:")
        else:
            doctor = matching_doctor
    logger.info("Selected doctor: id=%s, value=%s", doctor["id"], doctor["value"])
    doctor_id = doctor["id"]

    click.secho(f"Selected doctor: {doctor["value"]} (id={doctor["id"]})", fg="green")
    click.echo("Looking for available appointments...")

    now = date.today()
    slots = await client.get_available_slots(
        region["id"],
        specialization["id"],
        now,
        doctor["id"],
        clinic["id"],
    )

    if slots:
        click.echo("Found the following available slots:")

        for slot in slots:
            click.secho("-----------------------", fg="yellow")
            click.secho(f"Clinic: {slot["clinic"]["name"]}", fg="green")
            click.secho(f"Doctor: {slot["doctor"]["name"]}", fg="green")
            click.secho(
                f"Date: {datetime.fromisoformat(slot["appointmentDate"]).strftime("%H:%M %d-%m-%Y")}", fg="green"
            )

        return

    click.secho("No available slots found", fg="red")
    create_new_monitoring = click.prompt(
        "Do you want to create a new monitoring?", type=click.Choice(["y", "n"]), default="y"
    )
    if create_new_monitoring == "n":
        logger.info("Not creating new monitoring")
        return

    logger.info("Creating new monitoring")
    notifier_class: None | Notifier = None

    if notifier is None:
        create_notifier = click.prompt(
            "Do you want to send a notification when an appointment is found?",
            type=click.Choice(["y", "n"]),
            default="y",
        )
        if create_notifier == "y":
            notifier = click.prompt(
                "Enter the notifier to send notifications to. ex. telegram", type=click.Choice(["telegram"])
            )
    if notifier == "telegram":
        telegram_bot_token = os.getenv("NOTIFIERS_TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.getenv("NOTIFIERS_TELEGRAM_CHAT_ID")
        if telegram_bot_token is None or telegram_chat_id is None:
            click.secho("Telegram notification is not configured properly. See README. Skipping...", fg="yellow")
            logger.info("Telegram notification is not configured properly. Skipping...")
        else:
            logger.info("Telegram notification configured")
            notifier_class = TelegramNotifier(telegram_bot_token, telegram_chat_id)

    click.secho("Creating new monitoring for parameters:", fg="green")
    click.secho(f"City: {region["value"]}", fg="green")
    click.secho(f"Specialization: {specialization["value"]}", fg="green")
    click.secho(f"Clinic: {clinic["value"]}", fg="green")
    click.secho(f"Doctor: {doctor["value"]}", fg="green")
    click.secho(f"Date from: {date_start.date()}", fg="green")
    click.secho(f"Time from: {time_start.time()}", fg="green")
    click.secho(f"Date to: {date_end.date()}", fg="green")
    click.secho(f"Time to: {time_end.time()}", fg="green")

    while True:
        try:
            available_slots: list[SlotItem] = await client.get_available_slots(
                location_id,
                specialization_id,
                date_start,
                doctor_id,
                clinic_id,
            )
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error: %s", e)
            if httpx.codes.is_server_error(e.response.status_code):
                click.secho("Server error. Retrying in 30 seconds...", fg="red")
                if notifier_class:
                    notifier_class.send_message("Server error.")
                await asyncio.sleep(30)
                continue
            else:
                click.secho("Something went wrong with the API. Retrying in 30 seconds...", fg="red")
                if notifier_class:
                    notifier_class.send_message("API error.")
                await asyncio.sleep(30)
                continue
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            logger.error("Timeout error: %s", e)
            click.secho("Timeout error. Retrying in 60 seconds...", fg="red")
            if notifier_class:
                notifier_class.send_message("Timeout error")
            await asyncio.sleep(60)
            continue

        parsed_available_slot = []
        for slot in available_slots:
            appointment_date = datetime.fromisoformat(slot["appointmentDate"])
            if time_start.time() <= appointment_date.time() <= time_end.time() and appointment_date <= date_end:
                parsed_available_slot.append(slot)

        if parsed_available_slot:
            logger.info("Found %s matching available slots", len(parsed_available_slot))
            notifier_text = "Found the following available slots:\n"
            click.echo("Found the following available slots:")

            for idx, slot in enumerate(parsed_available_slot):
                click.secho("-----------------------", fg="yellow")
                click.secho(f"Clinic: {slot["clinic"]["name"]}", fg="green")
                click.secho(f"Doctor: {slot["doctor"]["name"]}", fg="green")
                click.secho(
                    f"Date: {datetime.fromisoformat(slot["appointmentDate"]).strftime("%H:%M %d-%m-%Y")}", fg="green"
                )
                if idx != 0:
                    notifier_text += "-----------------------\n"
                notifier_text += (
                    f"Specialization: {slot["specialty"]["name"]}\n"
                    f"Clinic: {slot["clinic"]["name"]}\n"
                    f"Doctor: {slot["doctor"]["name"]}\n"
                    f"Date: {datetime.fromisoformat(slot["appointmentDate"]).strftime("%H:%M %d-%m-%Y")}\n"
                )

            if notifier_class:
                logger.info("Sending notification to notifier")
                notifier_class.send_message(notifier_text)
            return

        logger.info("No available slots found")
        click.secho("No available slots found for the given parameters. Retrying in 30 seconds...", fg="yellow")
        await asyncio.sleep(30)


@cli.command()
@click.option(
    "--username",
    "-u",
    prompt="Username",
    help="Medicover username",
    type=str,
    default=lambda: os.getenv("MEDICOVER_USERNAME", ""),
    show_default="Value from .env or empty",
)
@click.option(
    "--password",
    "-p",
    prompt="Password",
    help="Medicover password",
    hide_input=True,
    type=str,
    default=lambda: os.getenv("MEDICOVER_PASSWORD", ""),
    show_default="Value from .env or empty",
)
async def future_appointments(username: str, password: str) -> None:
    client = MedicoverClient(username, password)
    logger.info("Starting future appointments check")
    try:
        await client.log_in()
    except IncorrectLoginError:
        click.secho("Unsuccessful logging in. Check username and password", fg="red")
        return
    all_future_appointments = await client.get_future_appointments()
    if not all_future_appointments:
        click.echo("No future appointments")

    for appointment in all_future_appointments:
        click.secho("-----------------------", fg="yellow")
        click.secho(f"Specialization: {appointment["specialty"]["name"]}", fg="green")
        click.secho(f"Clinic: {appointment["clinic"]["name"]}", fg="green")
        click.secho(f"Doctor: {appointment["doctor"]["name"]}", fg="green")
        click.secho(f"Date: {datetime.fromisoformat(appointment["date"]).strftime("%H:%M %d-%m-%Y")}", fg="green")


if __name__ == "__main__":
    cli()
