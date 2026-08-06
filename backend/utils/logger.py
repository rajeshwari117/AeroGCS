import os
import json
import time
import threading
from datetime import datetime

from backend.config import LOG_DIR


class FlightLogger:
    """
    Writes one JSON object per line to a per-session .jsonl file.

    Two kinds of entries:
      - telemetry snapshots  (written frequently, from the listener thread)
      - events               (written occasionally, from any thread —
                               commands sent, failsafes triggered, etc.)

    A new file is created each time the backend process starts, named
    with the start timestamp, so every run gets its own clean session log.
    """

    def __init__(self):
        self.lock = threading.Lock()
        session_name = datetime.now().strftime("flight_session_%Y%m%d_%H%M%S.jsonl")
        self.filepath = os.path.join(LOG_DIR, session_name)

    def _write_line(self, entry: dict):
        """Appends one JSON object as a single line. Thread-safe."""
        with self.lock:
            with open(self.filepath, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def log_telemetry(self, state_dict: dict):
        """Logs a telemetry snapshot (expects the dict from vehicle_state.to_dict())."""
        entry = {
            "log_type": "telemetry",
            "timestamp": time.time(),
            "data": state_dict,
        }
        self._write_line(entry)

    def log_event(self, event_type: str, data: dict = None):
        """
        Logs a discrete event — e.g. logger.log_event("command_sent",
        {"command": "arm"}).
        """
        entry = {
            "log_type": "event",
            "timestamp": time.time(),
            "event": event_type,
            "data": data or {},
        }
        self._write_line(entry)


# Single shared instance, created once when the backend starts.
logger = FlightLogger()