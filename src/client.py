from functools import wraps
from typing import Any, Callable, TypeVar, cast

import httpx
from bs4 import BeautifulSoup
from httpx import Client, Cookies, Headers

from src.api_urls import APPOINTMENTS, BASE_OAUTH_URL, BASE_URL

R = TypeVar("R")


def with_login_retry(max_attempts: int = 3, **kwargs: Any) -> Callable[[Callable[..., R]], Callable[..., R]]:
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            attempts = 0
            while attempts < max_attempts:
                result = func(*args, **kwargs)
                if result:
                    return result
                attempts += 1
            raise ValueError("Login failed")

        return wrapper

    return decorator


class MedicoverClient:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.sign_in_cookie: None | str = None

    def log_in(self) -> None:
        with Client() as client:
            response = client.get(BASE_URL + "/Users/Account/LogOn?ReturnUrl=%2F", follow_redirects=True)
            signin_hash = response.url.params.get("signin")

            response = client.get(
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

            response = client.post(
                login_url,
                data=data,
                follow_redirects=True,
            )

            data = self.form_to_dict(response.text)

            if not data:
                raise ValueError("Login failed")

            response = client.post(
                f"{BASE_OAUTH_URL}/signin-oidc",
                data=data,
                follow_redirects=True,
            )

            data = self.form_to_dict(response.text)

            client.post(
                BASE_URL + "/Medicover.OpenIdConnectAuthentication/Account/OAuthSignIn",
                data=data,
                follow_redirects=True,
            )

            response = client.get(BASE_URL + "/", follow_redirects=True)
            response.raise_for_status()

            self.sign_in_cookie = response.cookies[".ASPXAUTH"]

    @with_login_retry(max_attempts=3)
    def get_appointments(self) -> list[dict[str, str]] | None:
        # TODO: Needs refactoring
        if self.sign_in_cookie:
            with Client(cookies=Cookies({".ASPXAUTH": self.sign_in_cookie})) as client:
                response = client.post(APPOINTMENTS, headers=Headers({"X-Requested-With": "XMLHttpRequest"}))
                if response.status_code == httpx.codes.OK:
                    return cast(list[dict[str, str]], response.json())
                self.log_in()
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
