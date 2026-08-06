import os

# ---------------------------------------------------------------------------
# MAVLink Connection Settings
# ---------------------------------------------------------------------------
# udpin:127.0.0.1:14550  -> we act as the UDP server, SITL connects to us (typical for SITL)
# udpout:127.0.0.1:14550 -> we connect out to a listening endpoint
# tcp:127.0.0.1:5760     -> TCP connection (some SITL configs use this)
# /dev/tty.usbmodemXXXX  -> real flight controller over USB/serial
MAVLINK_CONNECTION_STRING = os.getenv("MAVLINK_CONNECTION_STRING", "udpin:127.0.0.1:14550")

# ---------------------------------------------------------------------------
# Flask API Configuration
# ---------------------------------------------------------------------------
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
DEBUG_MODE = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Safety Thresholds
# ---------------------------------------------------------------------------
# If no heartbeat is received within this window, we consider telemetry lost.
HEARTBEAT_TIMEOUT_SEC = 5.0

# Battery failsafe thresholds (checked independently — either can trigger a warning)
LOW_BATTERY_THRESHOLD_V = 11.1     # 3S LiPo nominal-low voltage
LOW_BATTERY_THRESHOLD_PCT = 20     # percent

# Minimum satellite count considered a "reliable" GPS fix for arming purposes.
# Note: this is a soft advisory threshold — the actual arm-safety check uses
# GPS_RAW_INT.fix_type, not satellite count alone. Satellite count alone can be
# misleading (many sats with poor geometry can still give a weak fix).
GPS_MIN_SATELLITES = 6