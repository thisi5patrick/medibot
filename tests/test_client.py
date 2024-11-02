import pytest

from src.client import MedicoverClient
import os


class TestMedicoverClient:
    def test_log_in(self):
        username = os.environ["MEDICOVER_USERNAME"]
        password = os.environ["MEDICOVER_PASSWORD"]
        client = MedicoverClient(username, password)
        client.log_in()

    def test_failed_log_in(self):
        client = MedicoverClient("incorrect-username", "incorrect-password")
        with pytest.raises(ValueError):
            client.log_in()

