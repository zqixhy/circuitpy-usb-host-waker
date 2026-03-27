import microcontroller
import os
import wifi


APP_NAME = "circuitpython-usb-host-waker"
APP_VERSION = "2.0.0"
ERROR_TEXT_LIMIT = 1200


def env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def env_optional_int(name):
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return int(value)


def env_float(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def sanitize_id(value, fallback):
    if not value:
        return fallback

    result = []
    for char in str(value):
        if char.isalnum() or char in "_-":
            result.append(char.lower())
        else:
            result.append("_")

    sanitized = "".join(result).strip("_")
    return sanitized or fallback


def clean_topic_path(value, fallback):
    topic = (value or fallback or "").strip()
    while "//" in topic:
        topic = topic.replace("//", "/")
    return topic.strip("/")


def bool_to_on_off(value):
    return "ON" if value else "OFF"


def truncate_text(text, limit):
    if len(text) <= limit:
        return text
    return text[: limit - 14] + "\n\n...[trimmed]"


def html_escape(text):
    if text is None:
        return ""
    escaped = str(text)
    escaped = escaped.replace("&", "&amp;")
    escaped = escaped.replace("<", "&lt;")
    escaped = escaped.replace(">", "&gt;")
    return escaped


def human_time_delta(seconds):
    if seconds is None:
        return "N/A"

    remaining = float(seconds)
    parts = []

    if remaining >= 86_400:
        parts.append("{} d".format(int(remaining // 86_400)))
        remaining = remaining % 86_400
    if remaining >= 3_600:
        parts.append("{} h".format(int(remaining // 3_600)))
        remaining = remaining % 3_600
    if remaining >= 60:
        parts.append("{} m".format(int(remaining // 60)))
        remaining = remaining % 60

    parts.append("{:.1f} s".format(remaining))
    return " ".join(parts)


def get_cpu_uid_hex():
    try:
        return bytes(microcontroller.cpu.uid).hex()
    except Exception:
        return None


def get_mac_address():
    try:
        raw = bytes(wifi.radio.mac_address)
        return ":".join("{:02x}".format(part) for part in raw)
    except Exception:
        return None


def get_default_device_id():
    cpu_uid = get_cpu_uid_hex()
    if cpu_uid:
        return "usb_host_waker_{}".format(cpu_uid)

    mac_address = get_mac_address()
    if mac_address:
        return "usb_host_waker_{}".format(mac_address.replace(":", ""))

    return "usb_host_waker"


def get_default_model_name():
    try:
        return os.uname().machine
    except Exception:
        return "CircuitPython device"
