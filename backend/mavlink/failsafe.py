import time

from backend.mavlink.vehicle import vehicle_state
from backend.config import HEARTBEAT_TIMEOUT_SEC, LOW_BATTERY_THRESHOLD_V, LOW_BATTERY_THRESHOLD_PCT
from backend.utils.logger import logger

# Tracks the last logged failsafe state so we only log on state CHANGES,
# not on every single loop iteration (which would flood the log file).
_last_failsafe_state = False
_last_reason = ""


def check_failsafes():
    """
    Evaluates connection, battery, and GPS safety conditions and updates
    vehicle_state.failsafe_triggered / failsafe_reason accordingly.
    Called once per message by the connection manager's listener loop.
    """
    global _last_failsafe_state, _last_reason
    now = time.time()

    # 1. Connection heartbeat timeout — checked first because if we've lost
    #    the link entirely, checking battery/GPS off stale data is misleading.
    if vehicle_state.connected and (now - vehicle_state.last_heartbeat > HEARTBEAT_TIMEOUT_SEC):
        vehicle_state.update(
            connected=False,
            failsafe_triggered=True,
            failsafe_reason="Telemetry Connection Lost",
        )
        if not _last_failsafe_state or _last_reason != "Telemetry Connection Lost":
            logger.log_event("failsafe_trigger", {"reason": "Telemetry Connection Lost"})
            _last_failsafe_state = True
            _last_reason = "Telemetry Connection Lost"
        return

    if not vehicle_state.connected:
        return  # nothing else is meaningful to check while disconnected

    # 2. Battery — voltage and percentage checked independently; either can trip it
    is_low_battery = False
    battery_reason = ""
    if 0 < vehicle_state.battery_voltage < LOW_BATTERY_THRESHOLD_V:
        is_low_battery = True
        battery_reason = f"Low Battery: {vehicle_state.battery_voltage}V"
    elif 0 < vehicle_state.battery_percentage < LOW_BATTERY_THRESHOLD_PCT:
        is_low_battery = True
        battery_reason = f"Low Battery: {vehicle_state.battery_percentage}%"

    # 3. GPS — only a critical failsafe if the vehicle is ARMED. A GPS-less
    #    vehicle sitting disarmed on a bench is not a safety event.
    is_gps_lost = vehicle_state.armed and vehicle_state.gps_fix_type < 2
    gps_reason = "Critical: GPS Fix Lost while armed" if is_gps_lost else ""

    # Battery takes priority over GPS if both are true at once — losing power
    # is generally more urgent to surface than a degraded fix.
    if is_low_battery:
        triggered, reason = True, battery_reason
    elif is_gps_lost:
        triggered, reason = True, gps_reason
    else:
        triggered, reason = False, ""

    vehicle_state.update(failsafe_triggered=triggered, failsafe_reason=reason)

    if triggered:
        if not _last_failsafe_state or _last_reason != reason:
            logger.log_event("failsafe_trigger", {"reason": reason})
            _last_failsafe_state = True
            _last_reason = reason
    elif _last_failsafe_state:
        logger.log_event("failsafe_cleared", {"message": "All safety flags normal"})
        _last_failsafe_state = False
        _last_reason = ""
