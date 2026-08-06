import time
import queue

from pymavlink import mavutil

from backend.mavlink.connection import vehicle_connection, register_listener, unregister_listener
from backend.utils.logger import logger

MISSION_TIMEOUT_SEC = 5.0
FRAME = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT
CMD_WAYPOINT = mavutil.mavlink.MAV_CMD_NAV_WAYPOINT


def upload_mission(waypoints):
    """
    Uploads a full waypoint mission via the standard MAVLink handshake:
      1. Announce item count (MISSION_COUNT)
      2. Vehicle requests each item by index (MISSION_REQUEST_INT)
      3. We send each requested item (MISSION_ITEM_INT)
      4. Vehicle sends a final MISSION_ACK

    :param waypoints: list of {"lat": .., "lng": .., "alt": ..} dicts
    """
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."
    if not waypoints:
        return False, "Waypoint list is empty."

    request_q = queue.Queue(maxsize=50)
    ack_q = queue.Queue(maxsize=5)
    register_listener("MISSION_REQUEST_INT", request_q)
    register_listener("MISSION_REQUEST", request_q)  # some dialects use the older message
    register_listener("MISSION_ACK", ack_q)

    try:
        conn.mav.mission_count_send(conn.target_system, conn.target_component, len(waypoints))

        sent_count = 0
        deadline = time.time() + MISSION_TIMEOUT_SEC

        while sent_count < len(waypoints) and time.time() < deadline:
            try:
                req = request_q.get(timeout=max(0.01, deadline - time.time()))
            except queue.Empty:
                return False, f"Timed out: vehicle stopped requesting waypoints after {sent_count} items."

            seq = req.seq
            if seq >= len(waypoints):
                continue

            wp = waypoints[seq]
            conn.mav.mission_item_int_send(
                conn.target_system, conn.target_component, seq,
                FRAME, CMD_WAYPOINT,
                0, 1,           # current, autocontinue
                0, 0, 0, 0,     # param1-4: hold time, accept radius, pass radius, yaw
                int(wp["lat"] * 1e7),
                int(wp["lng"] * 1e7),
                float(wp["alt"]),
            )
            sent_count += 1
            deadline = time.time() + MISSION_TIMEOUT_SEC  # extend deadline on real progress

        try:
            final_ack = ack_q.get(timeout=MISSION_TIMEOUT_SEC)
        except queue.Empty:
            return False, "Vehicle never sent a final MISSION_ACK."

        if final_ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
            logger.log_event("mission_uploaded", {"waypoint_count": len(waypoints)})
            return True, f"Mission uploaded and accepted ({len(waypoints)} waypoints)."

        result_enum = mavutil.mavlink.enums["MAV_MISSION_RESULT"].get(final_ack.type)
        reason = result_enum.name if result_enum else f"result_code_{final_ack.type}"
        return False, f"Vehicle rejected mission: {reason}"

    finally:
        unregister_listener("MISSION_REQUEST_INT", request_q)
        unregister_listener("MISSION_REQUEST", request_q)
        unregister_listener("MISSION_ACK", ack_q)


def download_mission():
    """
    Downloads the current mission:
      1. Request the list (MISSION_REQUEST_LIST)
      2. Vehicle replies with MISSION_COUNT
      3. We request each item by index, vehicle replies with MISSION_ITEM_INT
    """
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."

    count_q = queue.Queue(maxsize=5)
    item_q = queue.Queue(maxsize=50)
    register_listener("MISSION_COUNT", count_q)
    register_listener("MISSION_ITEM_INT", item_q)

    try:
        conn.mav.mission_request_list_send(conn.target_system, conn.target_component)

        try:
            count_msg = count_q.get(timeout=MISSION_TIMEOUT_SEC)
        except queue.Empty:
            return False, "Vehicle did not respond with a mission count."

        total = count_msg.count
        if total == 0:
            return True, []

        waypoints = []
        for seq in range(total):
            conn.mav.mission_request_int_send(conn.target_system, conn.target_component, seq)
            try:
                item = item_q.get(timeout=MISSION_TIMEOUT_SEC)
            except queue.Empty:
                return False, f"Timed out downloading waypoint {seq} of {total}."

            waypoints.append({"seq": item.seq, "lat": item.x / 1e7, "lng": item.y / 1e7, "alt": item.z})

        logger.log_event("mission_downloaded", {"waypoint_count": len(waypoints)})
        return True, waypoints

    finally:
        unregister_listener("MISSION_COUNT", count_q)
        unregister_listener("MISSION_ITEM_INT", item_q)


def clear_mission():
    """Clears the entire mission on the vehicle and waits for MISSION_ACK confirmation."""
    conn = vehicle_connection.get_connection()
    if not conn:
        return False, "Vehicle not connected."

    ack_q = queue.Queue(maxsize=5)
    register_listener("MISSION_ACK", ack_q)

    try:
        conn.mav.mission_clear_all_send(conn.target_system, conn.target_component)
        try:
            ack = ack_q.get(timeout=MISSION_TIMEOUT_SEC)
        except queue.Empty:
            return False, "Vehicle did not confirm mission clear."

        if ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
            logger.log_event("mission_cleared", {})
            return True, "Mission cleared."
        return False, f"Vehicle rejected mission clear (code {ack.type})."
    finally:
        unregister_listener("MISSION_ACK", ack_q)
