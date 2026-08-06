from flask import Blueprint, request, jsonify

from backend.mavlink.commands import arm_vehicle, change_flight_mode, takeoff_vehicle, goto_position
from backend.utils.validators import validate_coordinates, validate_altitude

command_bp = Blueprint("command", __name__)


@command_bp.route("/api/command/arm", methods=["POST"])
def arm():
    """Payload: {"arm": true} or {"arm": false}. Blocks until confirmed by vehicle state."""
    data = request.get_json() or {}
    arm_req = data.get("arm")

    if arm_req is None:
        return jsonify({"success": False, "error": "Missing 'arm' parameter."}), 400
    if not isinstance(arm_req, bool):
        return jsonify({"success": False, "error": "'arm' must be a boolean."}), 400

    success, msg = arm_vehicle(arm_req)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)


@command_bp.route("/api/command/mode", methods=["POST"])
def change_mode():
    """Payload: {"mode": "GUIDED"}. Blocks until vehicle_state.flight_mode confirms the change."""
    data = request.get_json() or {}
    mode = data.get("mode")

    if not mode:
        return jsonify({"success": False, "error": "Missing 'mode' parameter."}), 400

    success, msg = change_flight_mode(mode)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)


@command_bp.route("/api/command/takeoff", methods=["POST"])
def takeoff():
    """Payload: {"altitude": 10.0}"""
    data = request.get_json() or {}
    altitude = data.get("altitude")

    if altitude is None:
        return jsonify({"success": False, "error": "Missing 'altitude' parameter."}), 400

    is_valid, err = validate_altitude(altitude)
    if not is_valid:
        return jsonify({"success": False, "error": err}), 400

    success, msg = takeoff_vehicle(altitude)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)


@command_bp.route("/api/command/goto", methods=["POST"])
def goto():
    """Payload: {"lat": 37.7, "lng": -122.4, "alt": 15.0}"""
    data = request.get_json() or {}
    lat, lng, alt = data.get("lat"), data.get("lng"), data.get("alt")

    if lat is None or lng is None or alt is None:
        return jsonify({"success": False, "error": "Missing 'lat', 'lng', or 'alt'."}), 400

    coord_ok, coord_err = validate_coordinates(lat, lng)
    if not coord_ok:
        return jsonify({"success": False, "error": coord_err}), 400

    alt_ok, alt_err = validate_altitude(alt)
    if not alt_ok:
        return jsonify({"success": False, "error": alt_err}), 400

    success, msg = goto_position(lat, lng, alt)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)


@command_bp.route("/api/command/land", methods=["POST"])
def land():
    """Commands an immediate LAND. Confirmed via flight mode readback."""
    success, msg = change_flight_mode("LAND")
    return jsonify({"success": success, "message": msg}), (200 if success else 400)


@command_bp.route("/api/command/rtl", methods=["POST"])
def rtl():
    """Commands Return-To-Launch. Confirmed via flight mode readback."""
    success, msg = change_flight_mode("RTL")
    return jsonify({"success": success, "message": msg}), (200 if success else 400)
