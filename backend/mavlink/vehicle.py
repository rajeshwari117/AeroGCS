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
        self.latitude = 0.0        # degrees
        self.longitude = 0.0       # degrees
        self.relative_alt = 0.0    # meters, above home/takeoff point
        self.absolute_alt = 0.0    # meters, above sea level (MSL)
        self.heading = 0.0         # degrees, 0-360

        # Speed / climb (from VFR_HUD)
        self.groundspeed = 0.0     # m/s
        self.airspeed = 0.0        # m/s
        self.climb_rate = 0.0      # m/s, positive = climbing

        # Battery (from SYS_STATUS)
        self.battery_voltage = 0.0     # volts
        self.battery_current = -1.0    # amps, -1 if sensor unsupported
        self.battery_percentage = -1   # percent, -1 if invalid

        # GPS (from GPS_RAW_INT)
        self.gps_satellites = 0
        self.gps_fix_type = 0      # 0-1 = no fix, 2 = 2D, 3 = 3D, 4+ = augmented

        # Attitude (from ATTITUDE) — needed for the PFD/artificial horizon later
        self.roll = 0.0    # degrees
        self.pitch = 0.0   # degrees
        self.yaw = 0.0      # degrees

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
        catches typos early (a bad kwarg is silently ignored rather than
        creating a new stray attribute, which would be a much harder bug
        to spot later).
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
                "failsafe_triggered": self.failsafe_triggered,
                "failsafe_reason": self.failsafe_reason,
                "timestamp": time.time(),
            }


# Single shared instance — every other module imports THIS object,
# never creates its own VehicleState(). That's what makes it a singleton.
vehicle_state = VehicleState()