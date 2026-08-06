import math
import time

from backend.mavlink.vehicle import vehicle_state

# Fallback Copter mode map, used only if pymavlink's own flightmode lookup fails.
COPTER_MODE_MAP = {
    0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED",
    5: "LOITER", 6: "RTL", 7: "CIRCLE", 9: "LAND", 11: "DRIFT",
    13: "SPORT", 14: "FLIP", 15: "AUTOTUNE", 16: "POSHOLD", 17: "BRAKE",
    18: "THROW", 19: "AVOID_ADSB", 20: "GUIDED_NOGPS", 21: "SMART_RTL",
    22: "FLOWHOLD", 23: "FOLLOW", 24: "ZIGZAG", 25: "SYSTEMID", 26: "AUTOROTATE",
}


def parse_mavlink_message(msg, mav_conn=None):
    """
    Reads one MAVLink message and updates the shared vehicle_state.
    Called once per message by the connection manager's listener loop.

    :param msg: a decoded pymavlink message object
    :param mav_conn: the live connection (optional) — used for the
                      flightmode helper, which knows the vehicle type
    """
    msg_type = msg.get_type()

    if msg_type == "HEARTBEAT":
        # bit 128 in base_mode = MAV_MODE_FLAG_SAFETY_ARMED
        is_armed = bool(msg.base_mode & 128)

        flight_mode = "UNKNOWN"
        if mav_conn:
            try:
                flight_mode = mav_conn.flightmode
            except Exception:
                flight_mode = COPTER_MODE_MAP.get(msg.custom_mode, f"MODE_{msg.custom_mode}")
        else:
            flight_mode = COPTER_MODE_MAP.get(msg.custom_mode, f"MODE_{msg.custom_mode}")

        vehicle_state.update(
            armed=is_armed,
            flight_mode=flight_mode,
            connected=True,
            last_heartbeat=time.time(),
        )

    elif msg_type == "SYS_STATUS":
        voltage = msg.voltage_battery / 1000.0  # mV -> V
        current = msg.current_battery / 100.0 if msg.current_battery != -1 else -1.0  # cA -> A
        vehicle_state.update(
            battery_voltage=round(voltage, 2),
            battery_current=round(current, 2),
            battery_percentage=msg.battery_remaining,
        )

    elif msg_type == "GPS_RAW_INT":
        vehicle_state.update(
            gps_satellites=msg.satellites_visible,
            gps_fix_type=msg.fix_type,
        )

    elif msg_type == "GLOBAL_POSITION_INT":
        heading = msg.hdg / 100.0 if msg.hdg != 65535 else 0.0  # 65535 = "unknown" sentinel
        vehicle_state.update(
            latitude=msg.lat / 1e7,
            longitude=msg.lon / 1e7,
            relative_alt=round(msg.relative_alt / 1000.0, 2),  # mm -> m
            absolute_alt=round(msg.alt / 1000.0, 2),
            heading=round(heading, 1),
        )

    elif msg_type == "VFR_HUD":
        vehicle_state.update(
            groundspeed=round(msg.groundspeed, 2),
            airspeed=round(msg.airspeed, 2),
            climb_rate=round(msg.climb, 2),
        )

    elif msg_type == "ATTITUDE":
        roll = math.degrees(msg.roll)
        pitch = math.degrees(msg.pitch)
        yaw = math.degrees(msg.yaw)
        if yaw < 0:
            yaw += 360.0
        vehicle_state.update(roll=round(roll, 1), pitch=round(pitch, 1), yaw=round(yaw, 1))

    elif msg_type == "PARAM_VALUE":
        param_id = msg.param_id
        if isinstance(param_id, bytes):
            param_id = param_id.decode("utf-8", errors="ignore")
        param_id = param_id.strip()
        with vehicle_state.lock:
            vehicle_state.parameters[param_id] = msg.param_value
