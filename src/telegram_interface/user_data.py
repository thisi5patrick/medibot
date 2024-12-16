from typing import Literal, TypedDict

from src.medicover_client.client import MedicoverClient


class Location(TypedDict):
    location_id: str
    location_name: str


class Specialization(TypedDict):
    specialization_id: str
    specialization_name: str


class Clinic(TypedDict):
    clinic_id: str | None
    clinic_name: str


class Doctor(TypedDict):
    doctor_id: str | None
    doctor_name: str


class UserDataHistory(TypedDict):
    locations: list[Location]
    specializations: list[Specialization]
    clinics: dict[str, list[Clinic]]
    doctors: dict[str, list[Doctor]]

    temp_data: dict[str, dict[str, str]]


class MonitoringDate(TypedDict):
    day: int
    month: int
    year: int


class MonitoringTime(TypedDict):
    hour: int
    minute: int


class Bookings(TypedDict, total=False):
    location: Location
    specialization: Specialization
    clinic: Clinic
    doctor: Doctor
    from_date: MonitoringDate
    from_time: MonitoringTime
    to_date: MonitoringDate
    to_time: MonitoringTime

    booking_hash: str
    message_id: int


class UserDataDataclass(TypedDict):
    medicover_client: MedicoverClient | None
    history: UserDataHistory
    bookings: dict[int, Bookings]
    current_booking_number: int
    booking_hashes: dict[str, int]
    language: Literal["en", "pl"]
    username: str
    password: str
