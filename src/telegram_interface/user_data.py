from typing import TypedDict

from src.client import MedicoverClient


class Location(TypedDict):
    location_id: int
    location_name: str


class Specialization(TypedDict):
    specialization_id: int
    specialization_name: str


class Clinic(TypedDict):
    clinic_id: int | None
    clinic_name: str


class Doctor(TypedDict):
    doctor_id: int | None
    doctor_name: str


class UserDataHistory(TypedDict):
    locations: list[Location]
    specializations: list[Specialization]
    clinics: dict[int, list[Clinic]]
    doctors: dict[int, list[Doctor]]

    temp_data: dict[str, dict[int, str]]


class MonitoringDate(TypedDict):
    day: int
    month: int
    year: int


class MonitoringTime(TypedDict):
    hour: str
    minute: str


class Bookings(TypedDict, total=False):
    location: Location
    specialization: Specialization
    clinic: Clinic
    doctor: Doctor | None
    from_date: MonitoringDate | None
    from_time: MonitoringTime | None
    to_date: MonitoringDate | None
    to_time: MonitoringTime | None

    is_active: bool
    is_done: bool


class UserDataDataclass(TypedDict):
    medicover_client: MedicoverClient | None
    history: UserDataHistory
    bookings: dict[int, Bookings]
    current_booking_number: int
