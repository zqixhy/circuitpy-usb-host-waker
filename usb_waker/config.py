import os

from usb_waker.common import (
    APP_VERSION,
    clean_topic_path,
    env_bool,
    env_float,
    env_int,
    env_optional_int,
    get_default_device_id,
    get_default_model_name,
    sanitize_id,
)


class AppConfig:
    def __init__(self):
        self.wifi_ssid = os.getenv("CIRCUITPY_WIFI_SSID")
        self.wifi_password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

        self.wifi_max_retries = env_int("WIFI_MAX_RETRIES", 10)
        self.wifi_retry_delay_s = env_float("WIFI_RETRY_DELAY_S", 2)
        self.wifi_check_interval_s = env_float("WIFI_CHECK_INTERVAL_S", 5)

        self.main_loop_delay_s = env_float("MAIN_LOOP_DELAY_S", 0.05)
        self.service_restart_delay_s = env_float("SERVICE_RESTART_DELAY_S", 1)

        self.http_port = env_int("HTTP_PORT", 80)
        self.http_debug = env_bool("HTTP_DEBUG", False)
        self.http_restart_interval_s = env_float("HTTP_RESTART_INTERVAL_S", 3600)
        self.http_error_retry_delay_s = env_float("HTTP_ERROR_RETRY_DELAY_S", 1)

        self.mqtt_broker = os.getenv("MQTT_BROKER")
        self.mqtt_port = env_optional_int("MQTT_PORT")
        self.mqtt_username = os.getenv("MQTT_USERNAME")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")
        self.mqtt_client_id = os.getenv("MQTT_CLIENT_ID")
        self.mqtt_use_ssl = env_bool("MQTT_USE_SSL", False)
        self.mqtt_keep_alive = env_int("MQTT_KEEP_ALIVE", 60)
        self.mqtt_retry_delay_s = env_float("MQTT_RETRY_DELAY_S", 10)
        self.mqtt_status_publish_interval_s = env_float(
            "MQTT_STATUS_PUBLISH_INTERVAL_S", 30
        )
        self.mqtt_topic_prefix = clean_topic_path(
            os.getenv("MQTT_TOPIC_PREFIX"), "usb_host_waker"
        )
        self.mqtt_wake_payload = os.getenv("MQTT_WAKE_PAYLOAD") or "WAKE"

        self.ha_discovery_prefix = clean_topic_path(
            os.getenv("HA_DISCOVERY_PREFIX"), "homeassistant"
        )
        self.ha_status_topic = clean_topic_path(
            os.getenv("HA_STATUS_TOPIC"), "homeassistant/status"
        )
        self.ha_status_online_payload = (
            os.getenv("HA_STATUS_ONLINE_PAYLOAD") or "online"
        )

        self.device_id = sanitize_id(
            os.getenv("HA_DEVICE_ID") or get_default_device_id(),
            "usb_host_waker",
        )
        self.device_name = os.getenv("HA_DEVICE_NAME") or "USB Host Waker"
        self.device_manufacturer = (
            os.getenv("HA_DEVICE_MANUFACTURER") or "CircuitPython"
        )
        self.device_model = os.getenv("HA_DEVICE_MODEL") or get_default_model_name()
        self.device_hw_version = os.getenv("HA_DEVICE_HW_VERSION") or "unknown"
        self.device_sw_version = os.getenv("HA_DEVICE_SW_VERSION") or APP_VERSION
        self.device_suggested_area = os.getenv("HA_SUGGESTED_AREA")

    @property
    def mqtt_enabled(self):
        return bool(self.mqtt_broker)
