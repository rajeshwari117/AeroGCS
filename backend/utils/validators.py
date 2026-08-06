def validate_coordinates(lat, lng):
    """Validates GPS latitude/longitude are numeric and within real-world bounds."""
    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return False, "Coordinates must be numeric values."

    if not (-90.0 <= lat <= 90.0):
        return False, f"Latitude {lat} is out of bounds (-90 to 90)."
    if not (-180.0 <= lng <= 180.0):
        return False, f"Longitude {lng} is out of bounds (-180 to 180)."

    return True, ""


def validate_altitude(alt, max_alt=122.0):
    """
    Validates altitude is numeric, non-negative, and under a safety ceiling.
    Default ceiling of 122m matches the common 400ft recreational drone limit —
    change max_alt per-call if a specific mission needs to go higher.
    """
    try:
        alt = float(alt)
    except (ValueError, TypeError):
        return False, "Altitude must be a numeric value."

    if alt < 0:
        return False, "Altitude cannot be negative."
    if alt > max_alt:
        return False, f"Altitude {alt}m exceeds safety ceiling of {max_alt}m."

    return True, ""


def validate_parameter(param_id, param_value):
    """Validates a parameter name/value pair before attempting to set it on the vehicle."""
    if not isinstance(param_id, str):
        return False, "Parameter ID must be a string."
    if len(param_id) > 16:
        return False, "Parameter ID must be 16 characters or less (MAVLink limit)."

    try:
        float(param_value)
    except (ValueError, TypeError):
        return False, "Parameter value must be numeric."

    return True, ""
