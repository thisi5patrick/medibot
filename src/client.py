import requests
from bs4 import BeautifulSoup
from httpx import Client, Headers, Cookies

from src.api_urls import BASE_URL, BASE_OAUTH_URL, APPOINTMENTS


class MedicoverClient:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.sign_in_cookie: None | str = None

    def extract_data_from_login_form(self, page_text: str) -> dict[str, str]:
        """ Extract values from input fields and prepare data for login request. """
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
        """ Extract values from input fields. """
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

    def log_in(self) -> None:
        with Client() as client:
            response = client.get(
                BASE_URL + "/Users/Account/LogOn?ReturnUrl=%2F",
                follow_redirects=True
            )
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


    def get_appointments(self) -> list[dict[str, str]]:
        with Client(cookies=Cookies({".ASPXAUTH": self.sign_in_cookie})) as client:
            response = client.get(APPOINTMENTS, headers=Headers({"X-Requested-With": "XMLHttpRequest"}))
            ...
