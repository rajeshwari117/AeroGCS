import time
import queue

from pymavlink import mavutil

from backend.mavlink.connection import vehicle_connection, register_listener, unregister_listener
from backend.utils.logger import logger

PARAM_TIMEOUT_SEC = 5.0


def request_all_parameters():
    """
    Triggers a full parameter dump. Values arrive asynchronously as
    PARAM_VALUE messages and are cached into vehicle_state.parameters
    by telemetry.py — this function doesn't block waiting for all of them.
    """
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."

    conn.mav.param_request_list_send(conn.target_system, conn.target_component)
    logger.log_event("parameter_list_requested", {})
    return True, "Requested full parameter list from vehicle."


def get_parameter(param_id, timeout=PARAM_TIMEOUT_SEC):
    """
    Reads a single parameter, waiting for its PARAM_VALUE reply.
    Always asks the vehicle fresh rather than trusting a cached value,
    since a cached value could be stale if it was changed outside this GCS.
    """
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."

    q = queue.Queue(maxsize=10)
    register_listener("PARAM_VALUE", q)

    try:
        conn.mav.param_request_read_send(
            conn.target_system, conn.target_component, param_id.encode("utf-8"), -1
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = q.get(timeout=max(0.01, deadline - time.time()))
            except queue.Empty:
                break

            received_id = msg.param_id
            if isinstance(received_id, bytes):
                received_id = received_id.decode("utf-8", errors="ignore")
            received_id = received_id.strip()

            if received_id == param_id:
                return True, msg.param_value

        return False, f"Timed out waiting for parameter '{param_id}'."
    finally:
        unregister_listener("PARAM_VALUE", q)


def set_parameter(param_id, param_value, timeout=PARAM_TIMEOUT_SEC):
    """
    Writes a parameter and waits for the vehicle's PARAM_VALUE confirmation
    before reporting success — same confirm-before-success principle as
    commands.py. Sending param_set with no readback would be exactly the
    "assumed success" mistake we fixed there.
    """
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."

    q = queue.Queue(maxsize=10)
    register_listener("PARAM_VALUE", q)

    try:
        conn.mav.param_set_send(
            conn.target_system, conn.target_component,
            param_id.encode("utf-8"),
            float(param_value),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = q.get(timeout=max(0.01, deadline - time.time()))
            except queue.Empty:
                break

            received_id = msg.param_id
            if isinstance(received_id, bytes):
                received_id = received_id.decode("utf-8", errors="ignore")
            received_id = received_id.strip()

            if received_id == param_id:
                if abs(msg.param_value - float(param_value)) < 1e-4:
                    logger.log_event("parameter_set", {"param": param_id, "value": msg.param_value})
                    return True, msg.param_value
                reason = f"Vehicle confirmed '{param_id}' but with value {msg.param_value}, not {param_value}."
                logger.log_event("command_failed", {"command": "SetParameter", "reason": reason})
                return False, reason

        return False, f"Timed out waiting for confirmation of '{param_id}'."
    finally:
        unregister_listener("PARAM_VALUE", q)
