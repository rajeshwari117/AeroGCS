import time
import threading
import queue

from pymavlink import mavutil

from backend.config import MAVLINK_CONNECTION_STRING
from backend.mavlink.vehicle import vehicle_state
from backend.mavlink.telemetry import parse_mavlink_message
from backend.utils.logger import logger

# ---------------------------------------------------------------------------
# Listener registry — lets other modules (parameters.py, missions.py) wait
# for a specific message type without touching the socket directly.
# ---------------------------------------------------------------------------
_message_listeners = {}
_listeners_lock = threading.Lock()


def register_listener(msg_type, q):
    """Registers a queue to receive a copy of every incoming message of msg_type."""
    with _listeners_lock:
        _message_listeners.setdefault(msg_type, []).append(q)


def unregister_listener(msg_type, q):
    """Removes a queue registered with register_listener."""
    with _listeners_lock:
        if msg_type in _message_listeners:
            try:
                _message_listeners[msg_type].remove(q)
            except ValueError:
                pass


def _dispatch_message(msg):
    """Hands a copy of msg to every queue subscribed to its message type."""
    msg_type = msg.get_type()
    with _listeners_lock:
        for q in _message_listeners.get(msg_type, []):
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass


class MavlinkConnectionManager:
    """
    Owns the single MAVLink connection for the whole backend.

    Runs one background daemon thread (_run) that:
      1. connects (and reconnects automatically if the link drops)
      2. reads messages in a loop
      3. updates vehicle_state via parse_mavlink_message
      4. checks failsafe conditions via check_failsafes
      5. dispatches messages to any registered listeners
      6. periodically logs a telemetry snapshot to disk

    Every other module talks to the vehicle THROUGH this class —
    nothing else is allowed to open its own mavutil.mavlink_connection().
    """

    def __init__(self):
        self.connection_string = MAVLINK_CONNECTION_STRING
        self.mav_conn = None
        self.running = False
        self.listener_thread = None
        self.lock = threading.Lock()

        self.last_log_time = 0.0
        self.log_interval_sec = 1.0  # write one telemetry snapshot per second, not per message

    def connect(self):
        """Attempts a single connection. Returns True/False. Safe to call repeatedly."""
        with self.lock:
            if self.mav_conn is not None:
                return True
            try:
                print(f"Connecting to vehicle at: {self.connection_string}")
                self.mav_conn = mavutil.mavlink_connection(self.connection_string)
                print("Waiting for initial heartbeat...")
                self.mav_conn.wait_heartbeat(timeout=5)
                print(f"Connected. target_system={self.mav_conn.target_system} "
                      f"target_component={self.mav_conn.target_component}")
                vehicle_state.update(connected=True, last_heartbeat=time.time())
                logger.log_event("connection_established", {
                    "connection_string": self.connection_string,
                    "target_system": self.mav_conn.target_system,
                    "target_component": self.mav_conn.target_component,
                })
                return True
            except Exception as e:
                print(f"Connection failed: {e}")
                self.mav_conn = None
                vehicle_state.update(connected=False)
                return False

    def disconnect(self):
        """Closes the connection cleanly, if open."""
        with self.lock:
            if self.mav_conn:
                try:
                    self.mav_conn.close()
                    print("MAVLink connection closed.")
                except Exception as e:
                    print(f"Error closing connection: {e}")
                self.mav_conn = None
            vehicle_state.update(connected=False)
            logger.log_event("connection_lost", {"reason": "Disconnected"})

    def start(self):
        """Starts the background listener thread. Safe to call once at app startup."""
        if self.running:
            return
        self.running = True
        self.listener_thread = threading.Thread(target=self._run, daemon=True)
        self.listener_thread.start()
        print("MAVLink background listener started.")

    def stop(self):
        """Stops the listener thread and closes the connection. Call on app shutdown."""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2.0)
        self.disconnect()

    def send_mavlink(self, msg):
        """Thread-safe send of a pre-built MAVLink message object."""
        with self.lock:
            if self.mav_conn:
                try:
                    self.mav_conn.mav.send(msg)
                    return True
                except Exception as e:
                    print(f"Error sending message: {e}")
            return False

    def get_connection(self):
        """Returns the raw pymavlink connection object, or None if not connected."""
        with self.lock:
            return self.mav_conn

    def _run(self):
        # Imported here, not at module top, to avoid a circular import:
        # failsafe.py doesn't import connection.py, but conceptually this
        # keeps the dependency direction one-way (connection -> failsafe).
        from backend.mavlink.failsafe import check_failsafes

        while self.running:
            if not self.mav_conn:
                if not self.connect():
                    time.sleep(2.0)
                    continue

            try:
                msg = self.mav_conn.recv_match(blocking=True, timeout=0.1)
                if msg:
                    parse_mavlink_message(msg, self.mav_conn)
                    _dispatch_message(msg)
            except Exception as e:
                print(f"Error reading message: {e}")
                self.disconnect()
                time.sleep(1.0)
                continue

            check_failsafes()

            now = time.time()
            if vehicle_state.connected and (now - self.last_log_time >= self.log_interval_sec):
                logger.log_telemetry(vehicle_state.to_dict())
                self.last_log_time = now


# Single shared instance — the only MavlinkConnectionManager that should ever exist.
vehicle_connection = MavlinkConnectionManager()
