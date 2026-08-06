from flask import Blueprint, request, jsonify

from backend.mavlink.parameters import get_parameter, set_parameter, request_all_parameters
from backend.utils.validators import validate_parameter

parameter_bp = Blueprint("parameter", __name__)


@parameter_bp.route("/api/params/refresh", methods=["POST"])
def refresh_parameters():
    """Triggers a full parameter dump from the vehicle (fills vehicle_state.parameters over time)."""
    success, msg = request_all_parameters()
    return jsonify({"success": success, "message": msg}), (200 if success else 400)


@parameter_bp.route("/api/params/<name>", methods=["GET"])
def read_parameter(name):
    """Reads a single parameter live from the vehicle (not from cache)."""
    success, result = get_parameter(name)
    if success:
        return jsonify({"success": True, "name": name, "value": result})
    return jsonify({"success": False, "error": result}), 400


@parameter_bp.route("/api/params/<name>", methods=["POST"])
def write_parameter(name):
    """Payload: {"value": 20}. Writes a parameter and waits for vehicle confirmation."""
    data = request.get_json() or {}
    value = data.get("value")

    if value is None:
        return jsonify({"success": False, "error": "Missing 'value' parameter."}), 400

    is_valid, err = validate_parameter(name, value)
    if not is_valid:
        return jsonify({"success": False, "error": err}), 400

    success, result = set_parameter(name, value)
    if success:
        return jsonify({"success": True, "name": name, "confirmed_value": result})
    return jsonify({"success": False, "error": result}), 400
