from typing import TypedDict


class Clinic(TypedDict):
    id: str
    name: str


class Doctor(TypedDict):
    id: str
    name: str


class Region(TypedDict):
    id: str
    name: str


class Specialty(TypedDict):
    id: str
    name: str


class Attributes(TypedDict):
    isNonShow: bool
    isKept: bool
    isAdHocTeleconsultation: bool


class AppointmentItem(TypedDict):
    id: str
    clinic: Clinic
    doctor: Doctor
    region: Region
    specialty: Specialty
    visitType: str
    date: str
    state: str


class SlotItem(TypedDict):
    appointmentDate: str
    bookingString: str
    clinic: Clinic
    doctor: Doctor
    specialty: Specialty
    visitType: str
