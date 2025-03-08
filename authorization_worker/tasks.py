"""Authorization Worker which polls authorization tasks from the message queue, queries the Authorization Service, calls the callback and logs the response."""

from __future__ import annotations

import logging
import os
import re
import time
from enum import StrEnum
from uuid import UUID

import redis
import requests
import validators
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


class _AuthorizationTask:
    """Wrapper around task parameters and authorization logic."""

    class Status(StrEnum):
        """Enumeration of possible authorization statuses."""

        ALLOWED = "allowed"
        NOT_ALLOWED = "not_allowed"
        INVALID = "invalid"
        UNKNOWN = "unknown"

    def __init__(self, station_id: UUID, driver_token: str, callback_url: URL):
        self._station_id = station_id
        self._driver_token = driver_token
        self._callback_url = callback_url

    def is_valid(self) -> bool:
        """Returns true if the user-provided task parameters are valid."""
        if not VALID_DRIVER_TOKEN_REGEX.match(self._driver_token):
            logging.error(f"Invalid driver token provided: {self._driver_token}")
            return False
        if not self.callback_url.lower().startswith("http") or not validators.url(
            self.callback_url
        ):
            logging.error(f"Invalid callback URL provided: {self.callback_url}")
            return False
        return True

    def run(self) -> _AuthorizationTask.Status:
        if not self.is_valid():
            return _AuthorizationTask.Status.INVALID
        try:
            logging.debug(
                f"Authorizing {self._driver_token} for station {self._station_id}..."
            )
            response = requests.get(
                f"{AUTHORIZATION_SERVICE_URL}/station/{self._station_id}/driver/{self._driver_token}/acl",
                timeout=AUTHORIZATION_SERVICE_TIMEOUT_SEC,
            ).json()
            print(f"Authorization response: {response}")
            return (
                _AuthorizationTask.Status.ALLOWED
                if response["authorized"]
                else _AuthorizationTask.Status.NOT_ALLOWED
            )
        except requests.exceptions.Timeout:
            logging.error("Authorization service timed out.")
        except RuntimeError as e:
            logging.error(f"Unexpected error: {e}")
        return _AuthorizationTask.Status.UNKNOWN

    def response_for_status(self, status: Status) -> dict[str, str]:
        """Builds response dictionary for the given status."""
        return {
            "station_id": str(self._station_id),
            "driver_token": self._driver_token,
            "status": str(status),
        }

    @property
    def callback_url(self) -> URL:
        return self._callback_url


app = Celery(__name__, broker=BROKER_URL)


@app.task(ignore_result=True)
def authorize(station_id: UUID, driver_token: str, callback_url: URL):
    start_time_ns = time.time_ns()
    task = _AuthorizationTask(station_id, driver_token, callback_url)
    response = task.response_for_status(task.run())
    callback_status = None
    try:
        callback_status = str(
            requests.post(callback_url, json=response, timeout=CALLBACK_TIMEOUT_SEC)
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send callback: {e}")
        callback_status = str(e)
    log_data = response | {
        "callback_status": callback_status,
        "callback_url": callback_url,
    }
    redis_client.hset(
        f"log:authorize:{start_time_ns}:{station_id}:{driver_token}",
        mapping=log_data,
    )
