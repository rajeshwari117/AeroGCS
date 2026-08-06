from flask import Blueprint, request, jsonify

from backend.mavlink.missions import upload_mission, download_mission, clear_mission
from backend.utils.validators import validate_coordinates, validate_altitude

mission_bp = Blueprint("mission", __name__)


@mission_bp.route("/api/mission", methods=["GET"])
def get_mission():
    """Downloads the current mission waypoints from the vehicle."""
    success, result = download_mission()
    if success:
        return jsonify({"success": True, "waypoints": result})
    return jsonify({"success": False, "error": result}), 400


@mission_bp.route("/api/mission", methods=["POST"])
def post_mission():
    """
    Uploads a waypoint mission.
    Payload: {"waypoints": [{"lat": 37.77, "lng": -122.41, "alt": 10}, ...]}
    """
    data = request.get_json() or {}
    waypoints = data.get("waypoints")

    if not waypoints or not isinstance(waypoints, list):
        return jsonify({"success": False, "error": "Missing or invalid 'waypoints' list."}), 400

    for idx, wp in enumerate(waypoints):
        lat, lng, alt = wp.get("lat"), wp.get("lng"), wp.get("alt")
        if lat is None or lng is None or alt is None:
            return jsonify({"success": False, "error": f"Waypoint {idx} missing lat/lng/alt."}), 400

        coord_ok, coord_err = validate_coordinates(lat, lng)
        if not coord_ok:
            return jsonify({"success": False, "error": f"Waypoint {idx}: {coord_err}"}), 400

        alt_ok, alt_err = validate_altitude(alt)
        if not alt_ok:
            return jsonify({"success": False, "error": f"Waypoint {idx}: {alt_err}"}), 400

    success, msg = upload_mission(waypoints)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)


@mission_bp.route("/api/mission", methods=["DELETE"])
def delete_mission():
    """Clears all mission waypoints on the vehicle."""
    success, msg = clear_mission()
    return jsonify({"success": success, "message": msg}), (200 if success else 400)
