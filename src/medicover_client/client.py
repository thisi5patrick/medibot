import base64
import hashlib
import logging
import uuid
from datetime import date, datetime
from functools import wraps
from typing import Any, Awaitable, Callable, TypedDict, TypeVar, cast

import httpx
from bs4 import BeautifulSoup, Tag
from httpx import AsyncClient, Headers, QueryParams

from src.medicover_client.api_urls import (
    APPOINTMENT_SEARCH_URL,
    AUTHORIZATION_URL,
    AVAILABLE_SLOT_SEARCH_URL,
    FILTER_SEARCH_URL,
    OIDC_URL,
    REGION_SEARCH_URL,
    TOKEN_URL,
)
from src.medicover_client.exceptions import AuthenticationError, IncorrectLoginError
from src.medicover_client.types import AppointmentItem, SlotItem

logger = logging.getLogger(__name__)


class FilterDataType(TypedDict):
    id: str
    value: str


R = TypeVar("R")
MAX_RETRY_ATTEMPTS = 3


def with_login_retry(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
    @wraps(func)
    async def wrapper(self: "MedicoverClient", *args: Any, **kwargs: Any) -> R:
        attempts = 0

        while attempts < MAX_RETRY_ATTEMPTS:
            try:
                if not self._token:
                    logger.warning("Attempt %s to sign in.", attempts + 1)
                    await self.log_in()
                else:
                    await self.do_refresh_token()
                return await func(self, *args, **kwargs)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == httpx.codes.UNAUTHORIZED:
                    self.sign_in_cookie = None
                    logger.warning("Received 401 Unauthorized. Attempt %s to re-authenticate.", attempts + 1)
                    await self.log_in()
                else:
                    raise
            except IncorrectLoginError as e:
                self.sign_in_cookie = None
                logger.warning("Incorrect login credentials. Will not attempt to re-authenticate.")
                raise AuthenticationError from e
            finally:
                attempts += 1

        raise AuthenticationError("Failed to sign in after 3 attempts.")

    return wrapper


class MedicoverClient:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.sign_in_cookie: None | str = None
        self._token: str = ""
        self.refresh_token: None | str = None

    @property
    def token(self) -> str:
        return "Bearer " + self._token

    @property
    def headers(self) -> Headers:
        return Headers({"authorization": self.token, "Host": "api-gateway-online24.medicover.pl"})

    async def do_refresh_token(self) -> None:
        logger.info("Refreshing token")
        refresh_token_data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "scope": "openid offline_access profile",
            "client_id": "web",
        }

        headers = self.headers
        headers.pop("Host")

        async with AsyncClient() as client:
            response = await client.post(TOKEN_URL, headers=headers, data=refresh_token_data)
            if response.status_code != httpx.codes.OK:
                logger.warning("Failed to refresh token")
                logger.warning(response.text)
                return
            logger.info("Successfully refreshed token")
            self._token = response.json()["access_token"]
            self.refresh_token = response.json()["refresh_token"]

    async def log_in(self) -> None:
        async with AsyncClient() as client:
            code_verifier = "".join(uuid.uuid4().hex for _ in range(3))
            code_challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")
            )

            url_params = QueryParams(
                {
                    "client_id": "web",
                    "redirect_uri": OIDC_URL,
                    "response_type": "code",
                    "scope": "openid offline_access profile",
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                }
            )

            response = await client.get(AUTHORIZATION_URL, params=url_params, follow_redirects=True)

            page = BeautifulSoup(response.content, "html.parser")
            token = cast(Tag, page.find("input", {"name": "__RequestVerificationToken"})).get("value")

            login_form = {
                "Input.ReturnUrl": "/connect/authorize/callback?" + str(url_params),
                "Input.LoginType": "FullLogin",
                "Input.Username": self.username,
                "Input.Password": self.password,
                "Input.Button": "login",
                "__RequestVerificationToken": token,
            }

            response = await client.post(response.url, data=login_form, follow_redirects=True)
            try:
                code = response.url.params["code"]
            except KeyError as err:
                raise IncorrectLoginError() from err

            token_data = {
                "grant_type": "authorization_code",
                "redirect_uri": OIDC_URL,
                "code": code,
                "code_verifier": code_verifier,
                "client_id": "web",
            }

            response = await client.post(TOKEN_URL, data=token_data)
            response_json = response.json()

            self._token = response_json["id_token"]
            self.refresh_token = response_json["refresh_token"]

            logger.info("Successfully logged in")

    @with_login_retry
    async def get_available_slots(
        self,
        region_id: int,
        specialization_id: int,
        from_date: datetime | date,
        doctor_id: int | None = None,
        clinic_id: int | None = None,
    ) -> list[SlotItem]:
        if isinstance(from_date, datetime):
            from_date = from_date.date()
        logger.info(
            "Getting available slots for region=%s, specialization=%s, from_date=%s, doctor_id=%s, clinic_id=%s",
            region_id,
            specialization_id,
            from_date,
            doctor_id,
            clinic_id,
        )
        search_since_formatted = from_date.strftime("%Y-%m-%d")
        async with AsyncClient(headers=self.headers) as client:
            response = await client.get(
                AVAILABLE_SLOT_SEARCH_URL,
                params={
                    "Page": 1,
                    "PageSize": 5000,
                    "RegionIds": [region_id],
                    "SpecialtyIds": [specialization_id],
                    "ClinicIds": [clinic_id] if clinic_id else [],
                    "DoctorIds": [doctor_id] if doctor_id else [],
                    "StartTime": search_since_formatted,
                },
                timeout=15,
            )
            response.raise_for_status()

        response_json = response.json()

        slots: list[SlotItem] = response_json.get("slots", [])
        logger.info("Found %s available slots", len(slots))

        return slots

    @with_login_retry
    async def get_all_regions(self) -> list[FilterDataType]:
        logger.info("Getting all regions")
        async with AsyncClient(headers=self.headers) as client:
            response = await client.get(REGION_SEARCH_URL)
            response.raise_for_status()

        response_json = response.json()
        response_regions: list[FilterDataType] = response_json.get("regions", [])
        logger.info("Found %s regions", len(response_regions))

        return response_regions

    async def get_all_specializations(self, region_id: str) -> list[FilterDataType]:
        response_json = await self.get_filters_data(region_id, None, None)

        response_specializations: list[FilterDataType] = response_json.get("specialties", [])
        logger.info("Found %s specializations", len(response_specializations))

        return response_specializations

    async def get_all_clinics(self, region_id: str, specialization_id: str) -> list[FilterDataType]:
        response_json = await self.get_filters_data(region_id, specialization_id)

        response_clinics: list[FilterDataType] = response_json.get("clinics", [])
        logger.info("Found %s clinics", len(response_clinics))

        return response_clinics

    async def get_all_doctors(
        self, region_id: str, specialization_id: str, clinic_id: str | None = None
    ) -> list[FilterDataType]:
        response_json = await self.get_filters_data(region_id, specialization_id, clinic_id)

        response_specializations: list[FilterDataType] = response_json.get("doctors", [])
        logger.info("Found %s doctors", len(response_specializations))

        return response_specializations

    @with_login_retry
    async def get_filters_data(
        self, region_id: str, specialization_id: str | None = None, clinic_id: str | None = None
    ) -> dict[str, list[FilterDataType]]:
        logger.info(
            "Getting filters data for region=%s, specialization=%s, clinic=%s", region_id, specialization_id, clinic_id
        )
        async with AsyncClient(headers=self.headers) as client:
            response = await client.get(
                FILTER_SEARCH_URL,
                params={
                    "RegionIds": region_id,
                    "SpecialtyIds": specialization_id,
                    "ClinicIds": clinic_id,
                },
            )
            response.raise_for_status()

        response_json: dict[str, list[FilterDataType]] = response.json()
        return response_json

    @with_login_retry
    async def get_future_appointments(self) -> list[AppointmentItem]:
        logger.info("Getting future appointments")
        today = date.today().strftime("%Y-%m-%d")

        async with AsyncClient(headers=self.headers) as client:
            response = await client.get(
                APPOINTMENT_SEARCH_URL,
                params={
                    "Page": 1,
                    "PageSize": 5000,
                    "AppointmentState": "All",
                    "dateFrom": today,
                },
            )
            response.raise_for_status()

        items = cast(list[AppointmentItem], response.json().get("items", []))
        logger.info("Found %s future appointments", len(items))

        return items
