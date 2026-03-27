[English](README.md) | [简体中文](README.zh-CN.md)

# CircuitPython USB Host Waker

Wake a sleeping host from a CircuitPython board by exposing the board as a USB HID keyboard and triggering an empty keyboard report over HTTP or MQTT.

## Features

- Sends a USB HID wake-up report from a Wi-Fi-enabled CircuitPython board
- Exposes a local HTTP control page, JSON status endpoint, and health check
- Publishes MQTT state and accepts wake commands over MQTT
- Announces itself to Home Assistant through MQTT Discovery
- Tracks runtime state such as Wi-Fi, USB, uptime, wake count, and last error
- Recovers from Wi-Fi, HTTP, and MQTT failures in the main loop

## Tech Stack

- CircuitPython
- USB HID keyboard reports
- `adafruit_hid`
- `adafruit_httpserver`
- `adafruit_minimqtt`
- `adafruit_connection_manager`
- `adafruit_ticks`
- Home Assistant MQTT Discovery

## Prerequisites

Before deploying to a board, make sure you have:

- A CircuitPython board with Wi-Fi support
- USB device support with the `KEYBOARD` HID device enabled
- A host whose BIOS/UEFI and OS allow USB wake from sleep
- `adafruit_hid` in the board's `/lib`
- `adafruit_httpserver` in the board's `/lib`
- `adafruit_minimqtt`, `adafruit_connection_manager`, and `adafruit_ticks` in the board's `/lib` if you want MQTT or Home Assistant integration

Notes:

- This project is not Wake-on-LAN. It sends a USB HID keyboard report.
- Whether wake-up works depends heavily on host hardware, firmware, power settings, and whether the USB port stays powered during sleep.

## Quickstart

This project is deployed by copying files to the mounted `CIRCUITPY` drive.

1. Copy the application files to the board.

```bash
export CIRCUITPY=/path/to/CIRCUITPY
cp code.py "$CIRCUITPY/"
cp -R usb_waker "$CIRCUITPY/"
cp settings.toml.example "$CIRCUITPY/settings.toml"
```

2. Install the required libraries.

If you use `circup`, this is the simplest path:

```bash
circup install adafruit_hid adafruit_httpserver adafruit_minimqtt adafruit_connection_manager adafruit_ticks
```

If you do not use `circup`, copy these libraries from the Adafruit CircuitPython library bundle into `"$CIRCUITPY/lib"`:

- `adafruit_hid`
- `adafruit_httpserver`
- `adafruit_minimqtt` when MQTT is enabled
- `adafruit_connection_manager` when MQTT is enabled
- `adafruit_ticks` when MQTT is enabled

3. Edit `settings.toml` on the board.

Minimum HTTP-only configuration:

```toml
CIRCUITPY_WIFI_SSID="your-ssid"
CIRCUITPY_WIFI_PASSWORD="your-password"
```

Example MQTT and Home Assistant configuration:

```toml
CIRCUITPY_WIFI_SSID="your-ssid"
CIRCUITPY_WIFI_PASSWORD="your-password"

MQTT_BROKER="192.168.1.10"
MQTT_PORT="1883"
MQTT_USERNAME="mqtt-user"
MQTT_PASSWORD="mqtt-password"
HA_DEVICE_ID="usb_host_waker_01"
HA_DEVICE_NAME="USB Host Waker"
```

4. Reset the board. It will connect to Wi-Fi, start the HTTP server, and connect to MQTT when `MQTT_BROKER` is set.

## Usage

### HTTP Control

After the board joins Wi-Fi, open the reported URL in a browser:

```text
http://<board-ip>/
```

The page includes a wake button and a status table.

Useful endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Main control and status page |
| `GET` | `/healthz` | Plain-text `ok` |
| `POST` | `/wake_up` | Trigger one USB HID wake report without leaving the page |

Example API calls:

```bash
curl -X POST http://<board-ip>/wake_up
```

### MQTT and Home Assistant

When `MQTT_BROKER` is configured, the device:

- Connects to the broker
- Publishes retained availability and runtime status
- Publishes Home Assistant discovery payloads
- Subscribes to the wake command topic
- Re-publishes discovery after the Home Assistant birth message

Default topic layout:

```text
usb_host_waker/<device_id>/availability
usb_host_waker/<device_id>/command/wake
usb_host_waker/<device_id>/status/json
usb_host_waker/<device_id>/state/wifi_connected
usb_host_waker/<device_id>/state/usb_connected
usb_host_waker/<device_id>/state/wake_count
```

`<device_id>` comes from `HA_DEVICE_ID`. If it is not set, the app derives one from the CPU UID or MAC address and sanitizes it for MQTT use.

Example wake command:

```bash
mosquitto_pub -h <broker> -t usb_host_waker/<device_id>/command/wake -m WAKE
```

Current behavior note: the implementation logs the incoming payload, but any message received on the wake topic triggers a wake attempt.

### Home Assistant Entities

The MQTT discovery payload creates these entities:

- `button`: `Wake Host`
- `binary_sensor`: `Wi-Fi Connected`
- `binary_sensor`: `USB Connected`
- `sensor`: `Wake Count`

The MQTT JSON status payload also includes fields such as `ip`, `http_url`, `uptime_seconds`, `last_wake_source`, `last_error_text`, and `reset_reason`.

## Configuration

All configuration is read from `settings.toml`.

### Wi-Fi and Runtime

| Variable | Default | Description |
| --- | --- | --- |
| `CIRCUITPY_WIFI_SSID` | none | Wi-Fi SSID. Required. |
| `CIRCUITPY_WIFI_PASSWORD` | none | Wi-Fi password. Required. |
| `WIFI_MAX_RETRIES` | `10` | Maximum retries per Wi-Fi connect cycle. |
| `WIFI_RETRY_DELAY_S` | `2` | Delay between Wi-Fi retry attempts. |
| `WIFI_CHECK_INTERVAL_S` | `5` | Interval between connectivity checks in the main loop. |
| `MAIN_LOOP_DELAY_S` | `0.05` | Delay between iterations of the main loop. Also reused as the post-connect MiniMQTT polling timeout. |
| `SERVICE_RESTART_DELAY_S` | `1` | Delay before rebuilding services after a runtime failure. |

### HTTP

| Variable | Default | Description |
| --- | --- | --- |
| `HTTP_PORT` | `80` | HTTP listen port. |
| `HTTP_DEBUG` | `false` | Enables `adafruit_httpserver` debug mode. |
| `HTTP_RESTART_INTERVAL_S` | `3600` | Periodic HTTP server refresh interval. |
| `HTTP_ERROR_RETRY_DELAY_S` | `1` | Delay after an HTTP poll failure before trying again. |

### MQTT and Home Assistant

| Variable | Default | Description |
| --- | --- | --- |
| `MQTT_BROKER` | none | MQTT broker hostname or IP. Enables MQTT when set. |
| `MQTT_PORT` | library default | Broker port passed to MiniMQTT. |
| `MQTT_USERNAME` | none | MQTT username. |
| `MQTT_PASSWORD` | none | MQTT password. |
| `MQTT_CLIENT_ID` | `device_id` | MQTT client ID. |
| `MQTT_USE_SSL` | `false` | Enables TLS. Requires `ssl` support on the board. |
| `MQTT_KEEP_ALIVE` | `60` | MQTT keepalive in seconds. |
| `MQTT_RETRY_DELAY_S` | `10` | Delay before retrying MQTT after a failure. |
| `MQTT_STATUS_PUBLISH_INTERVAL_S` | `30` | Status publish interval in seconds. |
| `MQTT_TOPIC_PREFIX` | `usb_host_waker` | Base topic prefix for device topics. |
| `MQTT_WAKE_PAYLOAD` | `WAKE` | Payload published by the Home Assistant button. |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | Home Assistant discovery prefix. |
| `HA_STATUS_TOPIC` | `homeassistant/status` | Home Assistant birth-message topic. |
| `HA_STATUS_ONLINE_PAYLOAD` | `online` | Birth-message payload that triggers discovery republish. |
| `HA_DEVICE_ID` | derived from CPU UID or MAC | Stable device identifier used in MQTT topics and discovery. |
| `HA_DEVICE_NAME` | `USB Host Waker` | Display name exposed in HTTP and Home Assistant. |
| `HA_DEVICE_MANUFACTURER` | `CircuitPython` | Home Assistant device manufacturer. |
| `HA_DEVICE_MODEL` | `os.uname().machine` | Home Assistant device model. |
| `HA_DEVICE_HW_VERSION` | `unknown` | Reported hardware revision. |
| `HA_DEVICE_SW_VERSION` | `2.0.0` | Reported software version. |
| `HA_SUGGESTED_AREA` | none | Optional Home Assistant suggested area. |

The full example configuration is available in [`settings.toml.example`](settings.toml.example).

## Project Structure

```text
.
├── code.py
├── README.md
├── README.zh-CN.md
├── settings.toml.example
└── usb_waker
    ├── __init__.py
    ├── app.py
    ├── common.py
    ├── config.py
    ├── http.py
    └── mqtt.py
```

- `code.py`: entry point that constructs `AppConfig` and starts `UsbHostWakerApp`
- `usb_waker/app.py`: orchestration loop for Wi-Fi, HTTP, MQTT, wake actions, and recovery
- `usb_waker/http.py`: HTTP routes, HTML pages, and JSON status endpoint
- `usb_waker/mqtt.py`: MQTT connectivity, Home Assistant discovery, and retained state publishing
- `usb_waker/config.py`: environment-backed configuration loader
- `usb_waker/common.py`: shared helpers for IDs, formatting, and environment parsing

## Troubleshooting

### The board never reaches the HTTP page

- Verify `CIRCUITPY_WIFI_SSID` and `CIRCUITPY_WIFI_PASSWORD`
- Check the serial console for connection attempts and the assigned IP
- Confirm the browser is on the same network as the board
- If you changed `HTTP_PORT`, include that port in the URL

### Home Assistant does not discover the device

- Confirm the MQTT integration is configured in Home Assistant
- Verify broker address, credentials, port, and TLS settings
- Confirm `adafruit_minimqtt`, `adafruit_connection_manager`, and `adafruit_ticks` are present in `/lib`
- Check whether `homeassistant/.../config` discovery topics are reaching the broker

### HTTP works but the host does not wake

- Make sure USB wake is enabled in BIOS/UEFI
- Check the OS power-management settings for that USB device or hub
- Confirm the target USB port remains powered while the host sleeps

### MQTT is configured but the app reports a missing library

If you see `MQTT_BROKER is set but MQTT libraries are missing from /lib`, copy `adafruit_minimqtt`, `adafruit_connection_manager`, and `adafruit_ticks` to the board's `/lib` directory or remove the MQTT settings.

## Development

There is no automated test suite in this repository yet. A minimal host-side syntax check is:

```bash
python3 -m py_compile code.py usb_waker/*.py
```

Recommended hardware smoke test after changes:

- Confirm the board reconnects to Wi-Fi after reset
- Open `/`
- Trigger `POST /wake_up`
- Verify MQTT connects when enabled
- Confirm Home Assistant entities appear and update

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
