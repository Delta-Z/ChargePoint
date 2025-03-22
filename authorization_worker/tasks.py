"""Authorization Worker which polls authorization tasks from the message queue, queries the Authorization Service, calls the callback and logs the response."""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from datetime import timedelta
from enum import StrEnum
from uuid import UUID

import requests
import validators
from celery import Celery

from authorization_worker.elastic_logger import ElasticLogger
from authorization_worker.logger import Logger
from authorization_worker.redis_logger import RedisLogger

URL = str
VALID_DRIVER_TOKEN_REGEX = re.compile(r"[a-zA-Z0-9\-._~]{20,80}")
AUTHORIZATION_SERVICE_URL = os.getenv(
    "AUTHORIZATION_SERVICE_URL", "http://localhost:5000"
)
BROKER_URL = os.getenv("BROKER_URL", "amqp://localhost")
CALLBACK_TIMEOUT_SEC = int(os.getenv("CALLBACK_TIMEOUT_SEC", 5))


class Status(StrEnum):
    """Enumeration of possible authorization statuses."""

    ALLOWED = "allowed"
    NOT_ALLOWED = "not_allowed"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class _AuthorizationTask:
    """Wrapper around task parameters and authorization logic."""

    def __init__(
        self,
        station_id: UUID,
        driver_token: str,
        callback_url: URL,
        expiry_time_ns: int,
    ):
        self._station_id = station_id
        self._driver_token = driver_token
        self._callback_url = callback_url
        self._expiry_time_ns = expiry_time_ns

    def is_valid_driver_token(self) -> bool:
        return VALID_DRIVER_TOKEN_REGEX.match(self._driver_token)

    def is_valid_callback_url(self) -> bool:
        return self.callback_url.lower().startswith("http") and validators.url(
            self.callback_url
        )

    def is_expired(self) -> bool:
        return time.time_ns() >= self._expiry_time_ns

    def run(self) -> Status:
        if self.is_expired():
            return Status.UNKNOWN
        if not (self.is_valid_driver_token() and self.is_valid_callback_url()):
            return Status.INVALID
        try:
            timeout_sec = timedelta(
                microseconds=(self._expiry_time_ns - time.time_ns()) // 1000
            ).total_seconds()
            print(
                f"Authorizing {self._driver_token} for station {self._station_id}, {timeout_sec} sec remaining..."
            )
            response = requests.get(
                f"{AUTHORIZATION_SERVICE_URL}/station/{self._station_id}/driver/{self._driver_token}/acl",
                timeout=timeout_sec,
            ).json()
            print(f"Authorization response: {response}")
            return Status.ALLOWED if response["authorized"] else Status.NOT_ALLOWED
        except requests.exceptions.Timeout:
            logging.error("Authorization service timed out.")
        except RuntimeError as e:
            logging.error(f"Unexpected error: {e}")
        return Status.UNKNOWN

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

logger = Logger()
if sys.argv and sys.argv[0].endswith("celery") and "worker" in sys.argv:
    if os.getenv("ELASTICSEARCH_URL"):
        logger = ElasticLogger(
            os.getenv("ELASTICSEARCH_URL"),
            os.getenv("ELASTIC_PASSWORD"),
            os.getenv("ELASTICSEARCH_CERTS_PATH", None),
        )
    elif os.getenv("REDIS_HOST"):
        logger = RedisLogger(os.getenv("REDIS_HOST"), os.getenv("REDIS_PORT", 6379))


@app.task(ignore_result=True)
def authorize(
    station_id: UUID, driver_token: str, callback_url: URL, expiry_time_ns: int
):
    start_time_ns = time.time_ns()
    task = _AuthorizationTask(station_id, driver_token, callback_url, expiry_time_ns)
    response = task.response_for_status(task.run())
    if task.is_valid_callback_url():
        try:
            callback_status = str(
                requests.post(callback_url, json=response, timeout=CALLBACK_TIMEOUT_SEC)
            )
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to send callback: {e}")
            callback_status = str(e)
    else:
        callback_status = "Invalid callback URL"
    logger.log_authorize(
        start_time_ns,
        response | {"callback_status": callback_status, "callback_url": callback_url},
    )
