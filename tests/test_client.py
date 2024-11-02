import os

import pytest

from src.client import MedicoverClient


class TestMedicoverClient:
    def test_log_in(self) -> None:
        username = os.environ["MEDICOVER_USERNAME"]
        password = os.environ["MEDICOVER_PASSWORD"]
        client = MedicoverClient(username, password)
        client.log_in()

    def test_failed_log_in(self) -> None:
        client = MedicoverClient("incorrect-username", "incorrect-password")
        with pytest.raises(ValueError, match="Login failed"):
            client.log_in()

    def test_get_appointments(self) -> None:
        client = MedicoverClient("", "")
        client.get_appointments()
