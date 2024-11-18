import asyncio
import logging
from datetime import datetime
from functools import wraps
from typing import Any, Awaitable, Callable, TypedDict, TypeVar, cast

import httpx
from bs4 import BeautifulSoup
from httpx import AsyncClient, Cookies, Headers
from pick import pick

from src.api_urls import APPOINTMENTS, AVAILABLE_SLOTS, BASE_OAUTH_URL, BASE_URL, FILTERS, REGIONS

logger = logging.getLogger(__name__)


class FilterDataType(TypedDict):
    id: int
    text: str


class AuthenticationError(Exception):
    pass


R = TypeVar("R")
MAX_RETRY_ATTEMPTS = 3


def with_login_retry(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
    @wraps(func)
    async def wrapper(self: "MedicoverClient", *args: Any, **kwargs: Any) -> R:
        attempts = 0

        while attempts < MAX_RETRY_ATTEMPTS:
            if self.sign_in_cookie is None:
                logger.warning("Attempt %s to sign in.", attempts + 1)
                await self.log_in()

            try:
                return await func(self, *args, **kwargs)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == httpx.codes.UNAUTHORIZED:
                    self.sign_in_cookie = None
                    logger.warning("Received 401 Unauthorized. Attempt %s to re-authenticate.", attempts + 1)
                    await self.log_in()
                else:
                    raise
            finally:
                attempts += 1

        raise AuthenticationError("Failed to sign in after 3 attempts.")

    return wrapper


class MedicoverClient:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.sign_in_cookie: None | str = None

    async def log_in(self) -> None:
        async with AsyncClient() as client:
            response = await client.get(BASE_URL + "/Users/Account/LogOn?ReturnUrl=%2F", follow_redirects=True)
            signin_hash = response.url.params.get("signin")

            response = await client.get(
                f"{BASE_OAUTH_URL}/external",
                params={
                    "provider": "IS3",
                    "signin": signin_hash,
                    "owner": "Mcov_Mol",
                    "ui_locales": "pl-PL",
                },
                follow_redirects=True,
            )

            login_url = str(response.url)

            data = self.extract_data_from_login_form(response.text)

            response = await client.post(
                login_url,
                data=data,
                follow_redirects=True,
            )

            data = self.form_to_dict(response.text)

            if not data:
                raise ValueError("Login failed")

            response = await client.post(
                f"{BASE_OAUTH_URL}/signin-oidc",
                data=data,
                follow_redirects=True,
            )

            data = self.form_to_dict(response.text)

            await client.post(
                BASE_URL + "/Medicover.OpenIdConnectAuthentication/Account/OAuthSignIn",
                data=data,
                follow_redirects=True,
            )

            response = await client.get(BASE_URL + "/", follow_redirects=True)
            response.raise_for_status()

            self.sign_in_cookie = response.cookies[".ASPXAUTH"]
            logger.info("Successfully logged in")

    @with_login_retry
    async def find_region(self, user_input: str) -> FilterDataType:
        found_regions = await self.get_region(user_input)
        if len(found_regions) > 1:
            title = "Select the region"
            options = [region["text"] for region in found_regions]
            index: int
            option, index = pick(options, title)
            region = found_regions[index]
        elif len(found_regions) == 1:
            region = found_regions[0]
        else:
            raise ValueError("Region not found")
        return region

    async def find_specialization(self, user_input: str, region_id: int) -> FilterDataType:
        found_specializations = await self.get_specialization(user_input, region_id)
        if len(found_specializations) > 1:
            title = "Select the specialization"
            options = [specialization["text"] for specialization in found_specializations]
            index: int
            option, index = pick(options, title)
            specialization = found_specializations[index]
        elif len(found_specializations) == 1:
            specialization = found_specializations[0]
        else:
            raise ValueError("Specialization not found")
        return specialization

    async def find_clinic(self, user_input: str, region_id: int, specialization_id: int) -> FilterDataType:
        found_clinics = await self.get_clinic(user_input, region_id, specialization_id)
        if len(found_clinics) > 1:
            title = "Select the clinic"
            options = [clinic["text"] for clinic in found_clinics]
            index: int
            option, index = pick(options, title)
            clinic = found_clinics[index]
        elif len(found_clinics) == 1:
            clinic = found_clinics[0]
        else:
            raise ValueError("Clinic not found")
        return clinic

    async def find_doctor(
        self, user_input: str, region_id: int, specialization_id: int, clinic_id: int | None
    ) -> FilterDataType:
        found_doctors = await self.get_doctor(user_input, region_id, specialization_id, clinic_id)
        if len(found_doctors) > 1:
            title = "Select the doctor"
            options = [doctor["text"] for doctor in found_doctors]
            index: int
            option, index = pick(options, title)
            doctor = found_doctors[index]
        elif len(found_doctors) == 1:
            doctor = found_doctors[0]
        else:
            raise ValueError("Doctor not found")
        return doctor

    async def create_new_appointment(self) -> None:
        region_input = input("Give the region: ")
        region = await self.find_region(region_input)
        region_id = region["id"]
        logging.info("Selected region: %s", region["text"])

        user_expected_specialization = input("Give the specialization: ")
        specialization = await self.find_specialization(user_expected_specialization, region_id)
        specialization_id = specialization["id"]
        logging.info("Selected specialization: %s", specialization["text"])

        user_expected_clinic = input("Give the clinic name or ENTER: ")
        clinic_id: int | None = None
        if user_expected_clinic:
            clinic = await self.find_clinic(user_expected_clinic, region_id, specialization_id)
            clinic_id = clinic["id"]
            logging.info("Selected clinic: %s", clinic["text"])

        user_expected_doctor = input("Give the doctor's name or ENTER: ")
        doctor_id: int | None = None
        if user_expected_doctor:
            doctor = await self.find_doctor(user_expected_doctor, region_id, specialization_id, clinic_id)
            doctor_id = doctor["id"]
            logging.info("Selected doctor: %s", doctor["text"])

        from_date_input = input("Give the date from (dd-mm-yyyy HH:MM) or ENTER for now: ")
        if from_date_input:
            from_date, from_time = self.extract_dates(from_date_input)
        else:
            from_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
            from_time = "00:00"

        to_time_input = input("Give the time to (HH:MM): ")
        if to_time_input:
            to_time = datetime.strptime(to_time_input, "%H:%M").strftime("%H:%M")
        else:
            to_time = datetime.now().strftime("%H:%M")

        slots = await self.get_available_slots(
            region_id,
            specialization_id,
            doctor_id,
            clinic_id,
            from_date=from_date,
            from_time=from_time,
            to_time=to_time,
        )

        if not slots:
            logging.info("No slots available")
            y_n = input("Do you want to create a monitor? (y/n) ")
            if y_n == "y":
                await self.create_monitor(
                    region_id=region_id,
                    specialization_id=specialization_id,
                    clinic_id=clinic_id,
                    doctor_id=doctor_id,
                    from_date=from_date,
                    from_time=from_time,
                    to_time=to_time,
                )
            else:
                return
        logger.info("Available slots: %s", slots)

    async def create_monitor(self, **kwargs: Any) -> None:
        while True:
            slots = await self.get_available_slots(**kwargs)
            if slots:
                break
            logger.info("No slots available for given parameters. Trying again in 30 seconds...")
            await asyncio.sleep(30)

    @staticmethod
    def extract_dates(user_input: str) -> tuple[str, str]:
        date_format = "%d-%m-%Y %H:%M"
        datetime_object = datetime.strptime(user_input, date_format)
        date_ = datetime_object.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        time_ = datetime_object.strftime("%H:%M")

        return date_, time_

    @with_login_retry
    async def get_available_slots(
        self,
        region_id: int,
        specialization_id: int,
        doctor_id: int | None = None,
        clinic_id: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        async with AsyncClient(cookies=Cookies({".ASPXAUTH": cast(str, self.sign_in_cookie)})) as client:
            response = await client.post(
                AVAILABLE_SLOTS,
                json={
                    "regionIds": [region_id],
                    "serviceTypeId": 2,
                    "serviceIds": [specialization_id],
                    "clinicIds": [clinic_id] if clinic_id else [],
                    "doctorIds": [doctor_id] if doctor_id else [],
                    "searchSince": kwargs["from_date"],
                    "startTime": kwargs["from_time"],
                    "endTime": kwargs["to_time"],
                },
                headers=Headers({"X-Requested-With": "XMLHttpRequest"}),
            )
            response.raise_for_status()

        response_json = response.json()
        return cast(list[dict[str, Any]], response_json["items"])

    @with_login_retry
    async def get_region(self, user_region: str) -> list[FilterDataType]:
        async with AsyncClient(cookies=Cookies({".ASPXAUTH": cast(str, self.sign_in_cookie)})) as client:
            response = await client.get(REGIONS)
            response.raise_for_status()

        response_json = response.json()
        response_regions = response_json.get("regions", [])

        found_regions = self.parse_filters_data(user_region, response_regions)

        return found_regions

    async def get_specialization(self, user_expected_specialization: str, region_id: int) -> list[FilterDataType]:
        response_json = await self.get_filters_data(region_id, None, None)

        response_specializations = response_json.get("services", [])
        found_specializations = self.parse_filters_data(user_expected_specialization, response_specializations)

        return found_specializations

    async def get_doctor(
        self, user_expected_doctor: str, region_id: int, specialization_id: int, clinic_id: int | None = None
    ) -> list[FilterDataType]:
        response_json = await self.get_filters_data(region_id, specialization_id, clinic_id)

        response_specializations = response_json.get("doctors", [])
        selected_doctors = self.parse_filters_data(user_expected_doctor, response_specializations)

        return selected_doctors

    async def get_clinic(
        self, user_expected_clinic: str, region_id: int, specialization_id: int
    ) -> list[FilterDataType]:
        response_json = await self.get_filters_data(region_id, specialization_id)

        response_clinics = response_json.get("clinics", [])
        selected_clinics = self.parse_filters_data(user_expected_clinic, response_clinics)

        return selected_clinics

    @with_login_retry
    async def get_filters_data(
        self, region_id: int, specialization_id: int | None = None, clinic_id: int | None = None
    ) -> dict[str, list[FilterDataType]]:
        async with AsyncClient(cookies=Cookies({".ASPXAUTH": cast(str, self.sign_in_cookie)})) as client:
            response = await client.get(
                FILTERS,
                params={
                    "regionIds": region_id,
                    "serviceTypeId": 2,
                    "serviceIds": specialization_id,
                    "clinic": clinic_id,
                },
            )
            response.raise_for_status()

        response_json = response.json()
        return cast(dict[str, list[FilterDataType]], response_json)

    @staticmethod
    def parse_filters_data(user_text: str, filters_data: list[FilterDataType]) -> list[FilterDataType]:
        selected_filters = []
        for available_filter in filters_data:
            if user_text.lower() in available_filter["text"].lower():
                selected_filters.append(available_filter)
        return selected_filters

    async def get_appointments(self) -> list[dict[str, str]] | None:
        # TODO: Needs refactoring
        if self.sign_in_cookie:
            async with AsyncClient(cookies=Cookies({".ASPXAUTH": self.sign_in_cookie})) as client:
                response = await client.post(
                    APPOINTMENTS, headers=Headers({"X-Requested-With": "XMLHttpRequest"}), data={"PageSize": 100}
                )
                if response.status_code == httpx.codes.OK:
                    return cast(list[dict[str, str]], response.json().get("items"))
                await self.log_in()
                return None
        return None

    def extract_data_from_login_form(self, page_text: str) -> dict[str, str]:
        """Extract values from input fields and prepare data for login request."""
        data = {"UserName": self.username, "Password": self.password}
        soup = BeautifulSoup(page_text, "html.parser")
        for input_tag in soup.find_all("input"):
            if input_tag["name"] == "ReturnUrl":
                data["ReturnUrl"] = input_tag["value"]
            elif input_tag["name"] == "__RequestVerificationToken":
                data["__RequestVerificationToken"] = input_tag["value"]
        return data

    @staticmethod
    def form_to_dict(page_text: str) -> dict[str, str]:
        """Extract values from input fields."""
        data = {}
        soup = BeautifulSoup(page_text, "html.parser")
        for input_tag in soup.find_all("input"):
            if input_tag["name"] == "code":
                data["code"] = input_tag["value"]
            elif input_tag["name"] == "id_token":
                data["id_token"] = input_tag["value"]
            elif input_tag["name"] == "scope":
                data["scope"] = input_tag["value"]
            elif input_tag["name"] == "state":
                data["state"] = input_tag["value"]
            elif input_tag["name"] == "session_state":
                data["session_state"] = input_tag["value"]
        return data
