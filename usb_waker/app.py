import gc
import socketpool
import time
import traceback

import microcontroller
import supervisor
import usb_hid
import wifi

from usb_waker.common import ERROR_TEXT_LIMIT, truncate_text
from usb_waker.http import HttpServerService
from usb_waker.mqtt import HomeAssistantMqttService


class UsbHostWakerApp:
    def __init__(self, config):
        self.config = config

        self.socket_pool = None
        self.boot_time = time.monotonic()
        self.last_wifi_check = 0

        self.wake_count = 0
        self.last_error_text = ""
        self.last_wake_source = "none"
        self.pending_status_publish = False

        self.http = HttpServerService(self, config)
        self.mqtt = HomeAssistantMqttService(self, config)

    def log(self, message):
        print("[{:>8.1f}] {}".format(time.monotonic(), message))

    def is_wifi_connected(self):
        try:
            return bool(wifi.radio.connected)
        except Exception:
            return False

    def is_usb_connected(self):
        try:
            return bool(supervisor.runtime.usb_connected)
        except Exception:
            return False

    def current_ip(self):
        try:
            return str(wifi.radio.ipv4_address)
        except Exception:
            return "N/A"

    def http_base_url(self):
        ip_address = self.current_ip()
        if ip_address == "N/A":
            return None
        if self.config.http_port == 80:
            return "http://{}/".format(ip_address)
        return "http://{}:{}/".format(ip_address, self.config.http_port)

    def get_reset_reason(self):
        try:
            return str(microcontroller.cpu.reset_reason)
        except Exception:
            return "unknown"

    def get_free_memory(self):
        try:
            return gc.mem_free()
        except Exception:
            return -1

    def record_error(self, context, error):
        formatted = "{}: {}\n\n{}".format(context, error, traceback.format_exc())
        self.last_error_text = truncate_text(formatted, ERROR_TEXT_LIMIT)
        self.pending_status_publish = True

    def get_socket_pool(self):
        if self.socket_pool is None:
            self.socket_pool = socketpool.SocketPool(wifi.radio)
        return self.socket_pool

    def connect_wifi(self):
        if not self.config.wifi_ssid or not self.config.wifi_password:
            raise RuntimeError(
                "Missing CIRCUITPY_WIFI_SSID or CIRCUITPY_WIFI_PASSWORD"
            )

        self.log("Connecting to Wi-Fi...")

        for attempt in range(1, self.config.wifi_max_retries + 1):
            try:
                self.log(
                    "Wi-Fi attempt {}/{}".format(
                        attempt, self.config.wifi_max_retries
                    )
                )

                try:
                    if wifi.radio.connected:
                        wifi.radio.stop_station()
                        time.sleep(0.5)
                except Exception:
                    pass

                wifi.radio.connect(
                    ssid=self.config.wifi_ssid, password=self.config.wifi_password
                )
                time.sleep(0.5)

                self.log("Wi-Fi connected, IP={}".format(self.current_ip()))
                return
            except Exception as error:
                self.log("Wi-Fi connect failed: {}".format(error))
                if attempt < self.config.wifi_max_retries:
                    time.sleep(self.config.wifi_retry_delay_s)

        raise RuntimeError("Could not connect to Wi-Fi")

    def ensure_wifi(self):
        if not self.is_wifi_connected():
            self.connect_wifi()

    def send_wake_up_report(self):
        usb_hid.Device.KEYBOARD.send_report(b"\x00" * 8)

    def wake_host(self, source):
        self.send_wake_up_report()
        self.wake_count += 1
        self.last_wake_source = source
        self.pending_status_publish = True
        self.log("Wake request sent via {}".format(source))

    def get_status_dict(self):
        last_http_restart_delta = None
        if self.http.last_restart:
            last_http_restart_delta = int(time.monotonic() - self.http.last_restart)

        last_mqtt_connect_delta = None
        if self.mqtt.last_connect:
            last_mqtt_connect_delta = int(time.monotonic() - self.mqtt.last_connect)

        return {
            "device_id": self.config.device_id,
            "device_name": self.config.device_name,
            "wifi_connected": self.is_wifi_connected(),
            "usb_connected": self.is_usb_connected(),
            "mqtt_enabled": self.config.mqtt_enabled,
            "mqtt_connected": self.mqtt.is_connected(),
            "ip": self.current_ip(),
            "http_url": self.http_base_url() or "N/A",
            "uptime_seconds": int(time.monotonic() - self.boot_time),
            "last_http_restart_seconds": last_http_restart_delta,
            "last_mqtt_connect_seconds": last_mqtt_connect_delta,
            "free_memory": self.get_free_memory(),
            "wake_count": self.wake_count,
            "last_wake_source": self.last_wake_source,
            "last_error_text": self.last_error_text,
            "reset_reason": self.get_reset_reason(),
        }

    def clear_services(self):
        self.http.stop()
        self.mqtt.stop()

    def ensure_services(self):
        self.ensure_wifi()

        if not self.http.is_running():
            self.http.start()

        self.mqtt.ensure()

    def run(self):
        gc.collect()

        while True:
            try:
                self.ensure_services()
                now = time.monotonic()

                if now - self.last_wifi_check >= self.config.wifi_check_interval_s:
                    self.last_wifi_check = now
                    if not self.is_wifi_connected():
                        raise RuntimeError("Wi-Fi disconnected")

                if (
                    self.http.last_restart
                    and now - self.http.last_restart
                    >= self.config.http_restart_interval_s
                ):
                    self.log("Periodic HTTP server refresh")
                    self.http.restart()

                self.http.poll()

                if self.pending_status_publish and self.mqtt.is_connected():
                    self.mqtt.publish_status(force=True)

                self.mqtt.poll()
            except Exception as error:
                self.record_error("Runtime", error)
                self.log("Runtime error: {}".format(error))
                print(self.last_error_text)
                self.clear_services()
                time.sleep(self.config.service_restart_delay_s)

            time.sleep(self.config.main_loop_delay_s)
