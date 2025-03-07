import logging
import os
import re
import requests
import uuid
from celery import Celery
from enum import StrEnum


URL = str
VALID_DRIVER_TOKEN_REGEX = re.compile(r"[a-zA-Z0-9\-._~]{20,80}")
AUTHORIZATION_SERVICE_URL = os.getenv(
    "AUTHORIZATION_SERVICE_URL", "http://localhost:5000"
)
CALLBACK_TIMEOUT_SEC = os.getenv("CALLBACK_TIMEOUT_SEC", 5)
AUTHORIZATION_SERVICE_TIMEOUT_SEC = os.getenv("AUTHORIZATION_SERVICE_TIMEOUT_SEC", 5)


class Status(StrEnum):
    ALLOWED = "allowed"
    NOT_ALLOWED = "not_allowed"
    INVALID = "invalid"
    UNKNOWN = "unknown"


app = Celery(__name__, broker="amqp://localhost")


def _make_callback_data(station_id: uuid.UUID, driver_token: str, status: Status):
    return {
        "station_id": station_id,
        "driver_token": driver_token,
        "status": str(status),
    }


def _authorize_impl(station_id: uuid.UUID, driver_token: str) -> Status:
    if not VALID_DRIVER_TOKEN_REGEX.fullmatch(driver_token):
        logging.error(f"Invalid driver token: {driver_token}")
        return Status.INVALID
    try:
        logging.debug(f"Authorizing {driver_token} for station {station_id}...")
        response = requests.get(
            f"{AUTHORIZATION_SERVICE_URL}/station/{station_id}/driver/{driver_token}/test_allowed",
            timeout=AUTHORIZATION_SERVICE_TIMEOUT_SEC,
        ).json()
        print(f"Authorization response: {response}")
        return Status.ALLOWED if response["authorized"] else Status.NOT_ALLOWED
    except requests.exceptions.Timeout:
        logging.error(f"Authorization service timed out.")
    except RuntimeError as e:
        logging.error(f"Unexpected error: {e}")
    return Status.UNKNOWN


logging.basicConfig(level=logging.DEBUG)


@app.task(name="authorization_worker.tasks.authorize")
def authorize(station_id: uuid.UUID, driver_token: str, callback_url: URL):
    result = _make_callback_data(
        station_id, driver_token, _authorize_impl(station_id, driver_token)
    )
    requests.post(callback_url, json=result, timeout=CALLBACK_TIMEOUT_SEC)
    return result
