"""Authorization Worker which polls authorization tasks from the message queue, queries the Authorization Service, calls the callback and logs the response."""

import logging
import os
import re
import time
from enum import StrEnum
from uuid import UUID

import redis
import requests
from celery import Celery

URL = str
VALID_DRIVER_TOKEN_REGEX = re.compile(r"[a-zA-Z0-9\-._~]{20,80}")
AUTHORIZATION_SERVICE_URL = os.getenv(
    "AUTHORIZATION_SERVICE_URL", "http://localhost:5000"
)
BROKER_URL = os.getenv("BROKER_URL", "amqp://localhost")
CALLBACK_TIMEOUT_SEC = int(os.getenv("CALLBACK_TIMEOUT_SEC", 5))
AUTHORIZATION_SERVICE_TIMEOUT_SEC = int(
    os.getenv("AUTHORIZATION_SERVICE_TIMEOUT_SEC", 5)
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)


logging.basicConfig(level=logging.DEBUG)

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)


class Status(StrEnum):
    """Enumeration of possible authorization statuses."""
    ALLOWED = "allowed"
    NOT_ALLOWED = "not_allowed"
    INVALID = "invalid"
    UNKNOWN = "unknown"


app = Celery(__name__, broker=BROKER_URL)


def _make_callback_data(station_id: UUID, driver_token: str, status: Status):
    return {
        "station_id": str(station_id),
        "driver_token": driver_token,
        "status": str(status),
    }


def _authorize_impl(station_id: UUID, driver_token: str) -> Status:
    if not VALID_DRIVER_TOKEN_REGEX.fullmatch(driver_token):
        logging.error(f"Invalid driver token: {driver_token}")
        return Status.INVALID
    # TODO: what sort of checks do we want to do for the callback URL?
    try:
        logging.debug(f"Authorizing {driver_token} for station {station_id}...")
        response = requests.get(
            f"{AUTHORIZATION_SERVICE_URL}/station/{station_id}/driver/{driver_token}/acl",
            timeout=AUTHORIZATION_SERVICE_TIMEOUT_SEC,
        ).json()
        print(f"Authorization response: {response}")
        return Status.ALLOWED if response["authorized"] else Status.NOT_ALLOWED
    except requests.exceptions.Timeout:
        logging.error("Authorization service timed out.")
    except RuntimeError as e:
        logging.error(f"Unexpected error: {e}")
    return Status.UNKNOWN


@app.task(ignore_result=True)
def authorize(station_id: UUID, driver_token: str, callback_url: URL):
    start_time_ns = time.time_ns()
    result = _make_callback_data(
        station_id, driver_token, _authorize_impl(station_id, driver_token)
    )
    callback_status = None
    try:
        callback_status = str(
            requests.post(callback_url, json=result, timeout=CALLBACK_TIMEOUT_SEC)
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send callback: {e}")
        callback_status = str(e)
    log_data = result | {
        "callback_status": callback_status,
        "callback_url": callback_url,
    }
    redis_client.hset(
        f"log:authorize:{start_time_ns}:{station_id}:{driver_token}",
        mapping=log_data,
    )
