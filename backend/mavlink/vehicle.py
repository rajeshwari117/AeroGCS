import time
import threading


class VehicleState:
    """
    Thread-safe container for everything we currently know about the vehicle.

    Written to by the MAVLink listener thread (backend/mavlink/telemetry.py).
    Read by Flask request threads (backend/api/*.py) whenever the frontend
    polls /api/telemetry.

    Every read or write goes through self.lock so the two sides never see a
    half-updated, inconsistent state.
    """

    def __init__(self):
        self.lock = threading.Lock()

        # Connection status
        self.connected = False
        self.last_heartbeat = 0.0

        # Flight state
        self.armed = False
        self.flight_mode = "UNKNOWN"

        # Position (from GLOBAL_POSITION_INT)
        self.latitude = 0.0
        self.longitude = 0.0
        self.relative_alt = 0.0
        self.absolute_alt = 0.0
        self.heading = 0.0

        # Speed / climb (from VFR_HUD)
        self.groundspeed = 0.0
        self.airspeed = 0.0
        self.climb_rate = 0.0

        # Battery (from SYS_STATUS)
        self.battery_voltage = 0.0
        self.battery_current = -1.0
        self.battery_percentage = -1

        # GPS (from GPS_RAW_INT)
        self.gps_satellites = 0
        self.gps_fix_type = 0

        # Attitude (from ATTITUDE)
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0

        # Sensor health (from SYS_STATUS onboard_control_sensors_present/health bitmasks).
        # None = sensor not present on this vehicle / not yet reported.
        # True/False = actual reported health once a SYS_STATUS message has arrived.
        self.ekf_ok = None
        self.compass_ok = None
        self.gps_sensor_ok = None

        # Last STATUSTEXT received (used to surface real pre-arm/rejection reasons
        # alongside COMMAND_ACK results, which are often just a numeric code).
        self.last_statustext = ""
        self.last_statustext_severity = 0
        self.last_statustext_time = 0.0

        # Failsafe status (set by failsafe.py)
        self.failsafe_triggered = False
        self.failsafe_reason = ""

        # Parameter cache — populated as PARAM_VALUE messages arrive
        self.parameters = {}

    def update(self, **kwargs):
        """
        Thread-safe batch update. Call as:
            vehicle_state.update(armed=True, flight_mode="GUIDED")
        Only updates attributes that already exist on the object — this
        catches typos early.
        """
        with self.lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def to_dict(self):
        """
        Returns a plain dict snapshot of the current state — safe to hand
        straight to Flask's jsonify(). Takes the lock so the snapshot is
        internally consistent even if the listener thread is mid-update.
        """
        with self.lock:
            return {
                "connected": self.connected,
                "last_heartbeat": self.last_heartbeat,
                "armed": self.armed,
                "flight_mode": self.flight_mode,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "relative_alt": self.relative_alt,
                "absolute_alt": self.absolute_alt,
                "heading": self.heading,
                "groundspeed": self.groundspeed,
                "airspeed": self.airspeed,
                "climb_rate": self.climb_rate,
                "battery_voltage": self.battery_voltage,
                "battery_current": self.battery_current,
                "battery_percentage": self.battery_percentage,
                "gps_satellites": self.gps_satellites,
                "gps_fix_type": self.gps_fix_type,
                "roll": self.roll,
                "pitch": self.pitch,
                "yaw": self.yaw,
                "ekf_ok": self.ekf_ok,
                "compass_ok": self.compass_ok,
                "gps_sensor_ok": self.gps_sensor_ok,
                "last_statustext": self.last_statustext,
                "last_statustext_severity": self.last_statustext_severity,
                "last_statustext_time": self.last_statustext_time,
                "failsafe_triggered": self.failsafe_triggered,
                "failsafe_reason": self.failsafe_reason,
                "timestamp": time.time(),
            }


# Single shared instance — every other module imports THIS object.
vehicle_state = VehicleState()
