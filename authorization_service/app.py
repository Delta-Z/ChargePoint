from flask import Flask, jsonify, Response
import redis
import os
import uuid

app = Flask(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)


redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)


def _allowlist_key(station_id: uuid.UUID) -> str:
    return f"station:{station_id}:allowlist"


@app.route("/station/<uuid:station_id>/driver/<string:driver_token>/test_allowed")
def test_allowed(station_id: uuid.UUID, driver_token: str) -> Response:
    return jsonify(
        authorized=redis_client.sismember(_allowlist_key(station_id), driver_token)
    )


@app.route("/station/<uuid:station_id>/driver/<string:driver_token>/set_allowed")
def set_allowed(station_id: uuid.UUID, driver_token: str) -> Response:
    new_size = redis_client.sadd(_allowlist_key(station_id), driver_token)
    return jsonify(success=True, new_size=new_size)


@app.route("/station/<uuid:station_id>/driver/<string:driver_token>/clear_allowed")
def clear_allowed(station_id: uuid.UUID, driver_token: str) -> Response:
    new_size = redis_client.srem(_allowlist_key(station_id), driver_token)
    return jsonify(success=True, new_size=new_size)
