import os
from flask import Blueprint, jsonify

from backend.mavlink.vehicle import vehicle_state
from backend.config import LOG_DIR

telemetry_bp = Blueprint("telemetry", __name__)


@telemetry_bp.route("/api/telemetry", methods=["GET"])
def get_telemetry():
    """Returns the current vehicle state as JSON. Polled by the frontend every 1-2s."""
    return jsonify(vehicle_state.to_dict())


@telemetry_bp.route("/api/logs/sessions", methods=["GET"])
def get_sessions():
    """Lists past flight session .jsonl log files, newest first."""
    try:
        if not os.path.exists(LOG_DIR):
            return jsonify({"sessions": []})

        files = [f for f in os.listdir(LOG_DIR) if f.endswith(".jsonl")]
        files.sort(reverse=True)
        return jsonify({"sessions": files})
    except Exception as e:
        return jsonify({"error": f"Failed to list session logs: {str(e)}"}), 500
