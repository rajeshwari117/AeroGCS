import os
import atexit

from flask import Flask, send_from_directory
from flask_cors import CORS

from backend.config import FLASK_HOST, FLASK_PORT, DEBUG_MODE
from backend.mavlink.connection import vehicle_connection

from backend.api.telemetry_routes import telemetry_bp
from backend.api.command_routes import command_bp
from backend.api.mission_routes import mission_bp
from backend.api.parameter_routes import parameter_bp

backend_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(backend_dir, "..", "frontend"))

app = Flask(__name__, static_folder=frontend_dir, static_url_path="")
CORS(app)  # allows the frontend to call the API even if served from a different origin during dev

app.register_blueprint(telemetry_bp)
app.register_blueprint(command_bp)
app.register_blueprint(mission_bp)
app.register_blueprint(parameter_bp)


@app.route("/")
def serve_index():
    return send_from_directory(frontend_dir, "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(frontend_dir, path)


def cleanup():
    """Stops the MAVLink background thread cleanly on shutdown (Ctrl+C, atexit)."""
    print("Stopping MAVLink background listener...")
    vehicle_connection.stop()


atexit.register(cleanup)


if __name__ == "__main__":
    # Flask's debug reloader runs your app in a CHILD process and re-imports
    # this file in the parent too. Without this check, vehicle_connection.start()
    # would run twice -> two background threads -> two MAVLink connections
    # fighting over the same UDP port. WERKZEUG_RUN_MAIN is only set in the
    # child, so this guarantees exactly one listener thread.
    is_main_process = not DEBUG_MODE or os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if is_main_process:
        print("Starting MAVLink background listener...")
        vehicle_connection.start()
    else:
        print("Reloader parent process — waiting for child to start listener...")

    print(f"AeroGCS server starting on http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG_MODE, use_reloader=DEBUG_MODE)
