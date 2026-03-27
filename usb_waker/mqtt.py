import gc
import json
import time

from usb_waker.common import APP_NAME, APP_VERSION, bool_to_on_off, get_mac_address

try:
    import ssl
except ImportError:
    ssl = None

try:
    import adafruit_minimqtt.adafruit_minimqtt as MQTT
except ImportError:
    MQTT = None


class HomeAssistantMqttService:
    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.connect_timeout_s = 1.0
        self.poll_timeout_s = max(0.01, float(self.config.main_loop_delay_s))

        self.client = None
        self.ssl_context = None
        self.last_connect = 0
        self.last_status_publish = 0
        self.next_retry_at = 0
        self.pending_discovery_publish = False

        base_topic = "{}/{}".format(
            self.config.mqtt_topic_prefix, self.config.device_id
        )
        self.topics = {
            "availability": "{}/availability".format(base_topic),
            "command_wake": "{}/command/wake".format(base_topic),
            "status_json": "{}/status/json".format(base_topic),
            "state_wifi": "{}/state/wifi_connected".format(base_topic),
            "state_usb": "{}/state/usb_connected".format(base_topic),
            "state_wake_count": "{}/state/wake_count".format(base_topic),
        }

    def apply_poll_timeout(self):
        if self.client is None:
            return

        try:
            self.client._socket_timeout = self.poll_timeout_s
        except Exception:
            pass

        try:
            if self.client._sock is not None:
                self.client._sock.settimeout(self.poll_timeout_s)
        except Exception:
            pass

    def is_connected(self):
        if self.client is None:
            return False
        try:
            return bool(self.client.is_connected())
        except Exception:
            return False

    def get_ssl_context(self):
        if not self.config.mqtt_use_ssl:
            return None

        if ssl is None:
            raise RuntimeError("MQTT_USE_SSL is true but ssl is unavailable")

        if self.ssl_context is None:
            self.ssl_context = ssl.create_default_context()

        return self.ssl_context

    def discovery_topic(self, component, object_id):
        return "{}/{}/{}/config".format(
            self.config.ha_discovery_prefix, component, object_id
        )

    def build_device_info(self):
        device = {
            "identifiers": [self.config.device_id],
            "name": self.config.device_name,
            "manufacturer": self.config.device_manufacturer,
            "model": self.config.device_model,
            "sw_version": self.config.device_sw_version,
            "hw_version": self.config.device_hw_version,
        }

        configuration_url = self.app.http_base_url()
        if configuration_url:
            device["configuration_url"] = configuration_url

        if self.config.device_suggested_area:
            device["suggested_area"] = self.config.device_suggested_area

        mac_address = get_mac_address()
        if mac_address:
            device["connections"] = [["mac", mac_address]]

        return device

    def build_origin_info(self):
        return {
            "name": APP_NAME,
            "sw_version": APP_VERSION,
        }

    def get_discovery_messages(self):
        device_info = self.build_device_info()
        origin_info = self.build_origin_info()
        device_id = self.config.device_id

        return [
            (
                self.discovery_topic("button", "{}_wake".format(device_id)),
                {
                    "name": "Wake Host",
                    "unique_id": "{}_wake".format(device_id),
                    "command_topic": self.topics["command_wake"],
                    "payload_press": self.config.mqtt_wake_payload,
                    "availability_topic": self.topics["availability"],
                    "json_attributes_topic": self.topics["status_json"],
                    "icon": "mdi:power-sleep",
                    "device": device_info,
                    "origin": origin_info,
                },
            ),
            (
                self.discovery_topic(
                    "binary_sensor", "{}_wifi_connected".format(device_id)
                ),
                {
                    "name": "Wi-Fi Connected",
                    "unique_id": "{}_wifi_connected".format(device_id),
                    "state_topic": self.topics["state_wifi"],
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "availability_topic": self.topics["availability"],
                    "device_class": "connectivity",
                    "entity_category": "diagnostic",
                    "device": device_info,
                    "origin": origin_info,
                },
            ),
            (
                self.discovery_topic(
                    "binary_sensor", "{}_usb_connected".format(device_id)
                ),
                {
                    "name": "USB Connected",
                    "unique_id": "{}_usb_connected".format(device_id),
                    "state_topic": self.topics["state_usb"],
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "availability_topic": self.topics["availability"],
                    "entity_category": "diagnostic",
                    "icon": "mdi:usb-port",
                    "device": device_info,
                    "origin": origin_info,
                },
            ),
            (
                self.discovery_topic("sensor", "{}_wake_count".format(device_id)),
                {
                    "name": "Wake Count",
                    "unique_id": "{}_wake_count".format(device_id),
                    "state_topic": self.topics["state_wake_count"],
                    "availability_topic": self.topics["availability"],
                    "icon": "mdi:counter",
                    "device": device_info,
                    "origin": origin_info,
                },
            ),
        ]

    def publish_discovery(self):
        if not self.is_connected():
            return

        gc.collect()
        self.app.log("Publishing Home Assistant discovery...")

        for topic, payload in self.get_discovery_messages():
            self.client.publish(
                topic,
                json.dumps(payload, separators=(",", ":")),
                retain=True,
            )

    def publish_availability(self, online):
        if not self.is_connected():
            return

        self.client.publish(
            self.topics["availability"],
            "online" if online else "offline",
            retain=True,
        )

    def publish_status(self, force=False):
        if not self.is_connected():
            return

        now = time.monotonic()
        if not force and (
            now - self.last_status_publish < self.config.mqtt_status_publish_interval_s
        ):
            return

        gc.collect()
        status = self.app.get_status_dict()
        self.client.publish(
            self.topics["status_json"],
            json.dumps(status, separators=(",", ":")),
            retain=True,
        )
        self.client.publish(
            self.topics["state_wifi"],
            bool_to_on_off(status["wifi_connected"]),
            retain=True,
        )
        self.client.publish(
            self.topics["state_usb"],
            bool_to_on_off(status["usb_connected"]),
            retain=True,
        )
        self.client.publish(
            self.topics["state_wake_count"],
            str(status["wake_count"]),
            retain=True,
        )
        self.last_status_publish = now
        self.app.pending_status_publish = False

    def on_wake_command(self, client, topic, message):
        payload = str(message).strip()
        self.app.log("MQTT wake command received: {}".format(payload))

        try:
            self.app.wake_host("mqtt")
        except Exception as error:
            self.app.record_error("MQTT wake command", error)
            self.app.log("MQTT wake command failed: {}".format(error))

    def on_home_assistant_status(self, client, topic, message):
        payload = str(message).strip()
        if payload == self.config.ha_status_online_payload:
            self.app.log("Home Assistant birth message received")
            self.pending_discovery_publish = True

    def build_client(self):
        if MQTT is None:
            raise RuntimeError(
                "MQTT_BROKER is set but adafruit_minimqtt is missing from /lib"
            )

        client = MQTT.MQTT(
            broker=self.config.mqtt_broker,
            port=self.config.mqtt_port,
            username=self.config.mqtt_username,
            password=self.config.mqtt_password,
            client_id=self.config.mqtt_client_id or self.config.device_id,
            is_ssl=self.config.mqtt_use_ssl,
            keep_alive=self.config.mqtt_keep_alive,
            socket_pool=self.app.get_socket_pool(),
            ssl_context=self.get_ssl_context(),
            socket_timeout=self.connect_timeout_s,
        )
        client.will_set(self.topics["availability"], "offline", retain=True)
        client.add_topic_callback(self.topics["command_wake"], self.on_wake_command)
        client.add_topic_callback(
            self.config.ha_status_topic, self.on_home_assistant_status
        )
        return client

    def start(self):
        if not self.config.mqtt_enabled or self.is_connected():
            return

        if self.client is None:
            self.client = self.build_client()

        self.app.log("Connecting to MQTT broker {}...".format(self.config.mqtt_broker))
        self.client.connect()
        self.apply_poll_timeout()
        self.client.subscribe(self.topics["command_wake"])
        self.client.subscribe(self.config.ha_status_topic)
        self.last_connect = time.monotonic()
        self.next_retry_at = 0

        self.app.log("MQTT connected")
        self.publish_availability(True)
        self.publish_discovery()
        self.publish_status(force=True)

    def stop(self):
        if self.client is None:
            return

        client = self.client
        self.client = None

        try:
            if client.is_connected():
                try:
                    client.publish(self.topics["availability"], "offline", retain=True)
                except Exception:
                    pass
                client.disconnect()
        except Exception as error:
            self.app.log("Error disconnecting MQTT: {}".format(error))

        try:
            client.deinit()
        except Exception:
            pass

    def ensure(self):
        if not self.config.mqtt_enabled or self.is_connected():
            return

        now = time.monotonic()
        if now < self.next_retry_at:
            return

        try:
            self.start()
        except Exception as error:
            self.app.record_error("MQTT connect", error)
            self.app.log("MQTT unavailable: {}".format(error))
            self.stop()
            self.next_retry_at = now + self.config.mqtt_retry_delay_s

    def poll(self):
        if not self.is_connected():
            return

        try:
            self.client.loop(timeout=self.poll_timeout_s)
        except Exception as error:
            self.app.record_error("MQTT loop", error)
            self.app.log("MQTT loop error: {}".format(error))
            self.stop()
            self.next_retry_at = time.monotonic() + self.config.mqtt_retry_delay_s
            return

        if self.pending_discovery_publish:
            self.pending_discovery_publish = False
            try:
                self.publish_discovery()
                self.publish_status(force=True)
            except Exception as error:
                self.app.record_error("MQTT discovery publish", error)
                self.app.log("MQTT discovery publish failed: {}".format(error))
                self.stop()
                self.next_retry_at = time.monotonic() + self.config.mqtt_retry_delay_s
                return

        try:
            self.publish_status(force=False)
        except Exception as error:
            self.app.record_error("MQTT status publish", error)
            self.app.log("MQTT status publish failed: {}".format(error))
            self.stop()
            self.next_retry_at = time.monotonic() + self.config.mqtt_retry_delay_s
