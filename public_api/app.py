from flask import Flask, jsonify, request
from authorization_worker.tasks import authorize

app = Flask(__name__)

CALLBACK_URL_ARG = "callback_url"
CANNED_RESPONSE = jsonify(
    {
        "status": "accepted",
        "message": "Request is being processed asynchronously. The result will be sent to the provided callback URL.",
    }
)

@app.route("/station/<uuid:station_id>/driver/<string:driver_token>/authorize", methods=["GET", "POST"])
def authorize(station_id: str, driver_token: str):
    if request.is_json:
        callback_url = request.json.get(CALLBACK_URL_ARG)
    else:
        callback_url = request.args.get(CALLBACK_URL_ARG)
    if not callback_url:
        return jsonify({"error": f"Missing required parameter: {CALLBACK_URL_ARG}"}), 400
    print(f"Authorizing {driver_token} for station {station_id}")
    authorize.delay(station_id, driver_token, callback_url)
    return CANNED_RESPONSE
