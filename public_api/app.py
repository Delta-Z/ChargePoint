"""Public API service which returns the acknowledgement to the user and enqueues the authorization task."""

import os
import time
from uuid import UUID

from flask import Flask, jsonify, request

from authorization_worker.tasks import authorize as authorize_task

app = Flask(__name__)

CALLBACK_URL_ARG = "callback_url"
CANNED_RESPONSE = {
    "status": "accepted",
    "message": "Request is being processed asynchronously. The result will be sent to the provided callback URL.",
}
AUTHORIZATION_TIMEOUT_NS = (
    int(os.getenv("AUTHORIZATION_TIMEOUT_SEC", 5)) * 1_000_000_000
)


@app.route(
    "/station/<uuid:station_id>/driver/<string:driver_token>/authorize",
    methods=["GET", "POST"],
)
def authorize(station_id: UUID, driver_token: str):
    if request.is_json:
        callback_url = request.json.get(CALLBACK_URL_ARG)
    else:
        callback_url = request.args.get(CALLBACK_URL_ARG)
    if not callback_url:
        return (
            jsonify({"error": f"Missing required parameter: {CALLBACK_URL_ARG}"}),
            400,
        )
    print(f"Authorizing {driver_token} for station {station_id}")
    authorize_task.delay(
        station_id,
        driver_token,
        callback_url,
        time.time_ns() + AUTHORIZATION_TIMEOUT_NS,
    )
    return jsonify(CANNED_RESPONSE)
