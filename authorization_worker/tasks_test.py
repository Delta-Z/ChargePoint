import unittest
from unittest.mock import patch
from uuid import uuid4

import requests

from authorization_worker.tasks import CALLBACK_TIMEOUT_SEC, authorize

CALLBACK_URL = "http://callback.url"
FAKE_TIME = 1234567890


class TestAuthorizationWorker(unittest.TestCase):
    @patch("authorization_worker.tasks.time.time_ns", return_value=FAKE_TIME)
    @patch("authorization_worker.tasks.requests.get")
    @patch("authorization_worker.tasks.requests.post", return_value=200)
    @patch("authorization_worker.tasks.redis_client.hset")
    def test_authorize_allowed(
        self, mock_hset, mock_post, mock_get, unused_mock_time_ns
    ):
        station_id = uuid4()
        driver_token = "valid_driver_token_12345"
        mock_get.return_value.json.return_value = {"authorized": True}

        authorize(station_id, driver_token, CALLBACK_URL)
        expected_response = {
            "station_id": str(station_id),
            "driver_token": driver_token,
            "status": "allowed",
        }
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{station_id}:{driver_token}",
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
        station_id = uuid4()
        driver_token = "valid_driver_token_12345"
        mock_get.return_value.json.return_value = {"authorized": False}

        authorize(station_id, driver_token, CALLBACK_URL)
        expected_response = {
            "station_id": str(station_id),
            "driver_token": driver_token,
            "status": "not_allowed",
        }
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{station_id}:{driver_token}",
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
        station_id = uuid4()
        driver_token = "invalid_token"
        mock_get.return_value.json.return_value = {"authorized": False}

        authorize(station_id, driver_token, CALLBACK_URL)
        expected_response = {
            "station_id": str(station_id),
            "driver_token": driver_token,
            "status": "invalid",
        }
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{station_id}:{driver_token}",
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
        station_id = uuid4()
        driver_token = "valid_driver_token_12345"

        authorize(station_id, driver_token, CALLBACK_URL)
        expected_response = {
            "station_id": str(station_id),
            "driver_token": driver_token,
            "status": "unknown",
        }
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{station_id}:{driver_token}",
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
        station_id = uuid4()
        driver_token = "valid_driver_token_12345"
        mock_get.return_value.json.return_value = {"authorized": True}

        authorize(station_id, driver_token, CALLBACK_URL)
        expected_response = {
            "station_id": str(station_id),
            "driver_token": driver_token,
            "status": "allowed",
        }
        mock_post.assert_called_once_with(
            CALLBACK_URL, json=expected_response, timeout=CALLBACK_TIMEOUT_SEC
        )
        mock_hset.assert_called_once_with(
            f"log:authorize:{FAKE_TIME}:{station_id}:{driver_token}",
            mapping=expected_response
            | {
                "callback_status": "Request timed out",
                "callback_url": CALLBACK_URL,
            },
        )


if __name__ == "__main__":
    unittest.main()
