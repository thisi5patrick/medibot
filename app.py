from datetime import date, datetime
from typing import cast

import asyncclick as click
from dotenv import load_dotenv
from pick import pick

from src.medicover_client.client import FilterDataType, MedicoverClient
from src.medicover_client.exceptions import IncorrectLoginError

load_dotenv()


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
@click.option("--username", "-u", prompt="Username", help="Medicover username", type=str)
@click.option("--password", "-p", prompt="Password", help="Medicover password", hide_input=True, type=str)
@click.option("--location-id", "-l", help="Location ID", type=str)
@click.option("--specialization-id", "-s", help="Specialization ID", type=str)
@click.option("--clinic-id", "-c", help="Clinic ID", type=str)
@click.option("--doctor-id", "-d", help="Doctor ID", type=str)
async def new_monitoring(
    username: str,
    password: str,
    location_id: str | None,
    specialization_id: str | None,
    clinic_id: str | None,
    doctor_id: str | None,
) -> None:
    client = MedicoverClient(username, password)
    try:
        await client.log_in()
    except IncorrectLoginError:
        click.secho("Unsuccessful logging in. Check username and password", fg="red")
        return
    click.secho("Logged in", fg="green")

    all_locations = await client.get_all_regions()

    if location_id is None:
        location_input = click.prompt("Enter a city or part of it", type=str)
        matching_locations = match_input_to_filter(location_input, all_locations)

        if not matching_locations:
            region = pick_from_items(all_locations, "City not found. Select the location from the list:")
        elif len(matching_locations) > 1:
            region = pick_from_items(matching_locations, "Select the region")
        else:
            region = matching_locations[0]

    else:
        matching_location = next((location for location in all_locations if location["id"] == location_id), None)
        if not matching_location:
            region = pick_from_items(all_locations, "City not found. Select the location from the list:")
        else:
            region = matching_location

    click.secho(f"Selected region: {region["value"]}", fg="green")

    all_specializations = await client.get_all_specializations(region["id"])
    if specialization_id is None:
        specialization_input = click.prompt("Enter a specialization or part of it", type=str)
        matching_specializations = match_input_to_filter(specialization_input, all_specializations)

        if not matching_specializations:
            specialization = pick_from_items(
                all_specializations, "Specialization not found. Select the specialization from the list:"
            )
        elif len(matching_specializations) > 1:
            specialization = pick_from_items(matching_specializations, "Select the specialization")
        else:
            specialization = matching_specializations[0]
    else:
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

    click.secho(f"Selected specialization: {specialization["value"]}", fg="green")

    all_clinics = await client.get_all_clinics(region["id"], specialization["id"])

    if clinic_id is None:
        clinic_input = click.prompt("Enter a clinic or part of it or Any", type=str)
        if clinic_input == "Any":
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
        matching_clinic = next((clinic for clinic in all_clinics if clinic["id"] == clinic_id), None)
        if not matching_clinic:
            clinic = pick_from_items(all_clinics, "Clinic not found. Select the clinic from the list:")
        else:
            clinic = matching_clinic

    click.secho(f"Selected clinic: {clinic["value"]}", fg="green")

    all_doctors = await client.get_all_doctors(region["id"], specialization["id"], clinic["id"])

    if doctor_id is None:
        doctor_input = click.prompt("Enter a doctor or part of it or Any", type=str)
        if doctor_input == "Any":
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
        matching_doctor = next((doctor for doctor in all_doctors if doctor["id"] == doctor_id), None)
        if not matching_doctor:
            doctor = pick_from_items(all_doctors, "Doctor not found. Select the doctor from the list:")
        else:
            doctor = matching_doctor

    click.secho(f"Selected doctor: {doctor['value']}", fg="green")
    click.echo("Looking for available appointments...")

    now = date.today()
    slots = await client.get_available_slots(
        region["id"],
        specialization["id"],
        now,
        doctor["id"],
        clinic["id"],
    )
    click.echo("Found the following available slots:")

    if slots:
        for slot in slots:
            click.secho("-----------------------", fg="yellow")
            click.secho(f"Clinic: {slot["clinic"]["name"]}", fg="green")
            click.secho(f"Doctor: {slot["doctor"]["name"]}", fg="green")
            click.secho(
                f"Date: {datetime.fromisoformat(slot["appointmentDate"]).strftime("%H:%M %d-%m-%Y")}", fg="green"
            )
    else:
        click.secho("No available slots found", fg="red")
        create_new_monitoring = click.prompt("Do you want to create a new monitoring? (y/n)", type=str)
        if create_new_monitoring == "n":
            return
        # TODO implement monitoring


if __name__ == "__main__":
    cli()
