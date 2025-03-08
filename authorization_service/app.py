"""Authorization Service which exposes station/driver ACLs as a REST API."""

import os
from uuid import UUID

import redis
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)


redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)


def _allowlist_key(station_id: UUID) -> str:
    return f"station:{station_id}:allowlist"


@app.route(
    "/station/<uuid:station_id>/driver/<string:driver_token>/acl",
    methods=["GET", "PUT", "DELETE"],
)
def handle_allowed(station_id: UUID, driver_token: str) -> Response:
    if request.method == "GET":
        return jsonify(
            authorized=redis_client.sismember(_allowlist_key(station_id), driver_token)
        )
    elif request.method == "PUT":
        new_size = redis_client.sadd(_allowlist_key(station_id), driver_token)
        return jsonify(success=True, new_size=new_size)
    elif request.method == "DELETE":
        new_size = redis_client.srem(_allowlist_key(station_id), driver_token)
        return jsonify(success=True, new_size=new_size)
