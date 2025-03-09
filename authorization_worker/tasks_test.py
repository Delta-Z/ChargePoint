import unittest
from unittest.mock import patch
from uuid import uuid4

import requests

from authorization_worker.tasks import CALLBACK_TIMEOUT_SEC, Status, authorize

CALLBACK_URL = "http://callback.url"
INVALID_CALLBACK_URL = "invalid_url"
FAKE_TIME = 1234567890
STATION_ID = uuid4()
VALID_DRIVER_TOKEN = "valid_driver_token_12345"


def create_expected_response(status: Status, driver_token: str=VALID_DRIVER_TOKEN):
    return {
        "station_id": str(STATION_ID),
        "driver_token": driver_token,
        "status": status,
    }


class TestAuthorizationWorker(unittest.TestCase):
    @patch("authorization_worker.tasks.time.time_ns", return_value=FAKE_TIME)
    @patch("authorization_worker.tasks.requests.get")
    @patch("authorization_worker.tasks.requests.post", return_value=200)
    @patch("authorization_worker.tasks.redis_client.hset")
    def test_authorize_allowed(
        self, mock_hset, mock_post, mock_get, unused_mock_time_ns
    ):
        mock_get.return_value.json.return_value = {"authorized": True}

        authorize(STATION_ID, VALID_DRIVER_TOKEN, CALLBACK_URL, FAKE_TIME + 1)
        expected_response = create_expected_response(Status.ALLOWED)
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{STATION_ID}:{VALID_DRIVER_TOKEN}",
            mapping=expected_response
            | {
                "callback_status": "200",
                "callback_url": CALLBACK_URL,
            },
        )

    @patch("authorization_worker.tasks.time.time_ns", return_value=FAKE_TIME)
    @patch("authorization_worker.tasks.requests.get")
    @patch("authorization_worker.tasks.requests.post", return_value=200)
    @patch("authorization_worker.tasks.redis_client.hset")
    def test_authorize_not_allowed(
        self, mock_hset, mock_post, mock_get, unused_mock_time_ns
    ):
        mock_get.return_value.json.return_value = {"authorized": False}

        authorize(STATION_ID, VALID_DRIVER_TOKEN, CALLBACK_URL, FAKE_TIME + 1)
        expected_response = create_expected_response(Status.NOT_ALLOWED)
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{STATION_ID}:{VALID_DRIVER_TOKEN}",
            mapping=expected_response
            | {
                "callback_status": "200",
                "callback_url": CALLBACK_URL,
            },
        )

    @patch("authorization_worker.tasks.time.time_ns", return_value=FAKE_TIME)
    @patch("authorization_worker.tasks.requests.get")
    @patch("authorization_worker.tasks.requests.post", return_value=200)
    @patch("authorization_worker.tasks.redis_client.hset")
    def test_authorize_invalid_driver_token(
        self, mock_hset, mock_post, mock_get, unused_mock_time_ns
    ):
        driver_token_too_short = "invalid_token"
        mock_get.return_value.json.return_value = {"authorized": False}

        authorize(STATION_ID, driver_token_too_short, CALLBACK_URL, FAKE_TIME + 1)
        expected_response = create_expected_response(
            Status.INVALID, driver_token_too_short
        )
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{STATION_ID}:{driver_token_too_short}",
            mapping=expected_response
            | {
                "callback_status": "200",
                "callback_url": CALLBACK_URL,
            },
        )

    @patch("authorization_worker.tasks.time.time_ns", return_value=FAKE_TIME)
    @patch(
        "authorization_worker.tasks.requests.get",
        side_effect=requests.exceptions.Timeout,
    )
    @patch("authorization_worker.tasks.requests.post", return_value=200)
    @patch("authorization_worker.tasks.redis_client.hset")
    def test_authorize_timeout(
        self, mock_hset, mock_post, unused_mock_get, unused_mock_time_ns
    ):
        authorize(STATION_ID, VALID_DRIVER_TOKEN, CALLBACK_URL, FAKE_TIME + 1)
        expected_response = create_expected_response(Status.UNKNOWN)
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{STATION_ID}:{VALID_DRIVER_TOKEN}",
            mapping=expected_response
            | {
                "callback_status": "200",
                "callback_url": CALLBACK_URL,
            },
        )

    @patch("authorization_worker.tasks.time.time_ns", return_value=FAKE_TIME)
    @patch("authorization_worker.tasks.requests.get")
    @patch(
        "authorization_worker.tasks.requests.post",
        side_effect=requests.exceptions.Timeout("Request timed out"),
    )
    @patch("authorization_worker.tasks.redis_client.hset")
    def test_authorize_callback_Failure(
        self, mock_hset, mock_post, mock_get, unused_mock_time_ns
    ):
        mock_get.return_value.json.return_value = {"authorized": True}

        authorize(STATION_ID, VALID_DRIVER_TOKEN, CALLBACK_URL, FAKE_TIME + 1)
        expected_response = create_expected_response(Status.ALLOWED)
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{STATION_ID}:{VALID_DRIVER_TOKEN}",
            mapping=expected_response
            | {
                "callback_status": "Request timed out",
                "callback_url": CALLBACK_URL,
            },
        )

    @patch("authorization_worker.tasks.time.time_ns", return_value=FAKE_TIME)
    @patch("authorization_worker.tasks.requests.get")
    @patch("authorization_worker.tasks.requests.post", return_value=200)
    @patch("authorization_worker.tasks.redis_client.hset")
    def test_authorize_task_expired(
        self, mock_hset, mock_post, mock_get, unused_mock_time_ns
    ):
        expired_time_ns = FAKE_TIME - 1

        authorize(STATION_ID, VALID_DRIVER_TOKEN, CALLBACK_URL, expired_time_ns)
        expected_response = create_expected_response(Status.UNKNOWN)
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{STATION_ID}:{VALID_DRIVER_TOKEN}",
            mapping=expected_response
            | {
                "callback_status": "200",
                "callback_url": CALLBACK_URL,
            },
        )

    @patch("authorization_worker.tasks.time.time_ns", return_value=FAKE_TIME)
    @patch("authorization_worker.tasks.requests.get")
    @patch("authorization_worker.tasks.requests.post", return_value=200)
    @patch("authorization_worker.tasks.redis_client.hset")
    def test_authorize_invalid_callback_url(
        self, mock_hset, mock_post, mock_get, unused_mock_time_ns
    ):
        mock_get.return_value.json.return_value = {"authorized": True}

        authorize(STATION_ID, VALID_DRIVER_TOKEN, INVALID_CALLBACK_URL, FAKE_TIME + 1)
        expected_response = create_expected_response(Status.INVALID)
        mock_post.assert_not_called()
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{STATION_ID}:{VALID_DRIVER_TOKEN}",
            mapping=expected_response
            | {
                "callback_status": "Invalid callback URL",
                "callback_url": INVALID_CALLBACK_URL,
            },
        )


if __name__ == "__main__":
    unittest.main()
