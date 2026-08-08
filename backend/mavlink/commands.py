import time
import queue

from pymavlink import mavutil

from backend.mavlink.connection import vehicle_connection, register_listener, unregister_listener
from backend.mavlink.vehicle import vehicle_state
from backend.utils.logger import logger

ACK_TIMEOUT_SEC = 3.0
STATE_CONFIRM_TIMEOUT_SEC = 5.0
STATE_POLL_INTERVAL_SEC = 0.2


def _wait_for_command_ack(command_id, timeout=ACK_TIMEOUT_SEC):
    """
    Waits for a COMMAND_ACK matching command_id. Returns (success, message).
    On rejection or timeout, appends the most recent STATUSTEXT (if any
    arrived after we sent this command) -- COMMAND_ACK alone only gives a
    numeric result code, not the human-readable pre-arm/rejection reason.
    """
    sent_time = time.time()
    q = queue.Queue(maxsize=20)
    register_listener("COMMAND_ACK", q)
    try:
        deadline = sent_time + timeout
        while time.time() < deadline:
            try:
                msg = q.get(timeout=max(0.01, deadline - time.time()))
            except queue.Empty:
                break
            if msg.command == command_id:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    return True, "Command accepted by vehicle."
                result_enum = mavutil.mavlink.enums["MAV_RESULT"].get(msg.result)
                reason = result_enum.name if result_enum else f"result_code_{msg.result}"
                return False, _with_statustext(f"Vehicle rejected command: {reason}", sent_time)
        return False, _with_statustext("Timed out waiting for command acknowledgement.", sent_time)
    finally:
        unregister_listener("COMMAND_ACK", q)


def _with_statustext(base_reason, sent_time):
    """Appends the latest STATUSTEXT to an error message, if one arrived after sent_time."""
    if vehicle_state.last_statustext and vehicle_state.last_statustext_time >= sent_time:
        return f"{base_reason} — {vehicle_state.last_statustext}"
    return base_reason


def _wait_for_state(check_fn, timeout=STATE_CONFIRM_TIMEOUT_SEC, poll_interval=STATE_POLL_INTERVAL_SEC):
    """
    Polls vehicle_state via check_fn() until it returns True or timeout elapses.
    Used for confirmations that COMMAND_ACK alone can't guarantee — an ACK
    means "accepted," not "already true."
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check_fn():
            return True
        time.sleep(poll_interval)
    return False


def arm_vehicle(arm=True):
    """
    Arms or disarms the vehicle. Only reports success once BOTH:
      1. COMMAND_ACK confirms the flight controller accepted the request
      2. vehicle_state.armed actually matches the requested value
         (read live from HEARTBEAT messages via telemetry.py)
    """
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."

    action = "Arm" if arm else "Disarm"

    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1 if arm else 0,
        0, 0, 0, 0, 0, 0,
    )

    ack_ok, ack_msg = _wait_for_command_ack(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM)
    if not ack_ok:
        logger.log_event("command_failed", {"command": action, "reason": ack_msg})
        return False, ack_msg

    confirmed = _wait_for_state(lambda: vehicle_state.armed == arm)
    if not confirmed:
        reason = f"{action} accepted, but vehicle state did not change within timeout."
        logger.log_event("command_failed", {"command": action, "reason": reason})
        return False, reason

    logger.log_event("command_sent", {"command": action, "confirmed": True})
    return True, f"{action} confirmed."


def change_flight_mode(mode_name):
    """
    Changes flight mode and waits for vehicle_state.flight_mode to actually
    reflect it. Mode changes use conn.set_mode(), which doesn't reliably
    send COMMAND_ACK on ArduPilot — so state readback is the only real check.
    """
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."

    mode_name = mode_name.upper()
    try:
        mode_mapping = conn.mode_mapping()
    except Exception as e:
        return False, f"Could not read vehicle mode mapping: {e}"

    if mode_name not in mode_mapping:
        return False, f"Flight mode '{mode_name}' is not supported by this vehicle."

    try:
        conn.set_mode(mode_name)
    except Exception as e:
        return False, f"Failed to send mode change: {e}"

    confirmed = _wait_for_state(lambda: vehicle_state.flight_mode == mode_name)
    if not confirmed:
        reason = f"Mode change to '{mode_name}' sent, but not confirmed within timeout."
        logger.log_event("command_failed", {"command": "Change Mode", "mode": mode_name, "reason": reason})
        return False, reason

    logger.log_event("command_sent", {"command": "Change Mode", "mode": mode_name, "confirmed": True})
    return True, f"Mode changed to '{mode_name}', confirmed."


def takeoff_vehicle(altitude):
    """
    Sends MAV_CMD_NAV_TAKEOFF and waits for COMMAND_ACK.
    Note: we deliberately do NOT wait for relative_alt to reach the target
    here — climbing is a gradual process, not an instant state flip, and
    belongs to ongoing telemetry monitoring, not command confirmation.
    """
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."

    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0, 0, 0, 0, 0, 0,
        float(altitude),
    )

    ack_ok, ack_msg = _wait_for_command_ack(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF)
    if not ack_ok:
        logger.log_event("command_failed", {"command": "Takeoff", "reason": ack_msg})
        return False, ack_msg

    logger.log_event("command_sent", {"command": "Takeoff", "altitude": altitude, "confirmed": True})
    return True, f"Takeoff to {altitude}m accepted by vehicle."


def goto_position(lat, lng, alt):
    """
    Sends MAV_CMD_DO_REPOSITION and waits for COMMAND_ACK.
    Requires the vehicle to already be in GUIDED mode.
    """
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."

    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_DO_REPOSITION,
        0,
        -1.0, 1.0, 0.0, 0.0,
        float(lat), float(lng), float(alt),
    )

    ack_ok, ack_msg = _wait_for_command_ack(mavutil.mavlink.MAV_CMD_DO_REPOSITION)
    if not ack_ok:
        logger.log_event("command_failed", {"command": "GoTo", "reason": ack_msg})
        return False, ack_msg

    logger.log_event("command_sent", {"command": "GoTo", "lat": lat, "lng": lng, "alt": alt, "confirmed": True})
    return True, f"GoTo ({lat}, {lng}, {alt}m) accepted by vehicle."
