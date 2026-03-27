[English](README.md) | [简体中文](README.zh-CN.md)

# CircuitPython USB Host Waker

把 CircuitPython 开发板暴露成 USB HID 键盘，并通过 HTTP 或 MQTT 触发一个空键盘报告，尝试唤醒正在休眠的主机。

## 功能

- 在带 Wi-Fi 的 CircuitPython 开发板上发送 USB HID 唤醒报告
- 提供本地 HTTP 控制页、JSON 状态接口和健康检查接口
- 通过 MQTT 发布状态，并接收 MQTT 唤醒命令
- 通过 MQTT Discovery 自动接入 Home Assistant
- 跟踪 Wi-Fi、USB、运行时长、唤醒次数和最近错误等状态
- 在主循环中自动处理 Wi-Fi、HTTP 和 MQTT 故障恢复

## 技术栈

- CircuitPython
- USB HID 键盘报告
- `adafruit_hid`
- `adafruit_httpserver`
- `adafruit_minimqtt`
- Home Assistant MQTT Discovery

## 前置条件

部署到开发板前，请先确认：

- 你的 CircuitPython 开发板支持 Wi-Fi
- 板子启用了 USB Device，且 `KEYBOARD` HID 设备可用
- 目标主机在 BIOS/UEFI 和操作系统层面允许 USB 唤醒
- 开发板 `/lib` 中包含 `adafruit_hid`
- 开发板 `/lib` 中包含 `adafruit_httpserver`
- 如果要启用 MQTT 或 Home Assistant，开发板 `/lib` 中还需要 `adafruit_minimqtt`

说明：

- 这个项目不是 Wake-on-LAN，而是发送 USB HID 键盘报告。
- 能否真正唤醒主机，高度依赖主机硬件、固件、电源策略，以及休眠时 USB 口是否持续供电。

## 快速开始

这个项目的部署方式是把文件复制到挂载出来的 `CIRCUITPY` 盘符。

1. 把应用文件复制到开发板。

```bash
export CIRCUITPY=/path/to/CIRCUITPY
cp code.py "$CIRCUITPY/"
cp -R usb_waker "$CIRCUITPY/"
cp settings.toml.example "$CIRCUITPY/settings.toml"
```

2. 安装依赖库。

如果你使用 `circup`，最直接的方式是：

```bash
circup install adafruit_hid adafruit_httpserver adafruit_minimqtt
```

如果不用 `circup`，请从 Adafruit CircuitPython 库包中把下面这些目录复制到 `"$CIRCUITPY/lib"`：

- `adafruit_hid`
- `adafruit_httpserver`
- 启用 MQTT 时再额外复制 `adafruit_minimqtt`

3. 编辑开发板上的 `settings.toml`。

只使用 HTTP 时的最小配置：

```toml
CIRCUITPY_WIFI_SSID="your-ssid"
CIRCUITPY_WIFI_PASSWORD="your-password"
```

MQTT / Home Assistant 配置示例：

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

4. 重启开发板。设置了 `MQTT_BROKER` 时，程序会先连 Wi-Fi，再启动 HTTP，随后连接 MQTT。

## 使用方式

### HTTP 控制

开发板连上 Wi-Fi 后，在浏览器中打开串口日志里打印出来的地址：

```text
http://<board-ip>/
```

页面里会显示唤醒按钮和实时状态表。

可用接口如下：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 主控制页和状态页 |
| `GET` | `/status` | 同样的 HTML 状态页 |
| `GET` | `/status.json` | JSON 状态数据 |
| `GET` | `/healthz` | 纯文本 `ok` |
| `GET` | `/wake_up` | 唤醒表单页面 |
| `POST` | `/wake_up` | 触发一次 USB HID 唤醒报告 |

示例：

```bash
curl http://<board-ip>/status.json
curl -X POST http://<board-ip>/wake_up
```

### MQTT 与 Home Assistant

设置 `MQTT_BROKER` 后，设备会：

- 连接到 MQTT broker
- 发布 retained 的在线状态和运行状态
- 发布 Home Assistant Discovery 配置
- 订阅唤醒命令主题
- 收到 Home Assistant birth message 后重新发布 discovery

默认主题结构：

```text
usb_host_waker/<device_id>/availability
usb_host_waker/<device_id>/command/wake
usb_host_waker/<device_id>/status/json
usb_host_waker/<device_id>/state/wifi_connected
usb_host_waker/<device_id>/state/usb_connected
usb_host_waker/<device_id>/state/wake_count
```

`<device_id>` 来自 `HA_DEVICE_ID`。如果没有设置，程序会自动从 CPU UID 或 MAC 地址生成，并做 MQTT 安全化处理。

示例唤醒命令：

```bash
mosquitto_pub -h <broker> -t usb_host_waker/<device_id>/command/wake -m WAKE
```

当前实现说明：程序会记录收到的 payload，但只要这个 topic 上收到任意消息，就会触发一次唤醒尝试。

### Home Assistant 中创建的实体

通过 MQTT Discovery 会创建这些实体：

- `button`：`Wake Host`
- `binary_sensor`：`Wi-Fi Connected`
- `binary_sensor`：`USB Connected`
- `sensor`：`Wake Count`

`/status.json` 还会包含 `ip`、`http_url`、`uptime_seconds`、`last_wake_source`、`last_error_text`、`reset_reason` 等字段。

## 配置说明

所有配置都从 `settings.toml` 读取。

### Wi-Fi 与运行时参数

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CIRCUITPY_WIFI_SSID` | 无 | Wi-Fi SSID，必填。 |
| `CIRCUITPY_WIFI_PASSWORD` | 无 | Wi-Fi 密码，必填。 |
| `WIFI_MAX_RETRIES` | `10` | 单次 Wi-Fi 连接流程的最大重试次数。 |
| `WIFI_RETRY_DELAY_S` | `2` | Wi-Fi 重试间隔秒数。 |
| `WIFI_CHECK_INTERVAL_S` | `5` | 主循环中检查 Wi-Fi 状态的间隔。 |
| `MAIN_LOOP_DELAY_S` | `0.05` | 主循环每次迭代之间的等待时间。同时也作为 MiniMQTT 建连后的轮询超时。 |
| `SERVICE_RESTART_DELAY_S` | `1` | 运行时异常后重建服务前的等待时间。 |

### HTTP

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HTTP_PORT` | `80` | HTTP 监听端口。 |
| `HTTP_DEBUG` | `false` | 是否启用 `adafruit_httpserver` 调试模式。 |
| `HTTP_RESTART_INTERVAL_S` | `3600` | 定时重建 HTTP 服务的时间间隔。 |
| `HTTP_ERROR_RETRY_DELAY_S` | `1` | HTTP 轮询出错后的重试等待时间。 |

### MQTT 与 Home Assistant

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MQTT_BROKER` | 无 | MQTT broker 地址。设置后才会启用 MQTT。 |
| `MQTT_PORT` | 库默认值 | 传给 MiniMQTT 的端口。 |
| `MQTT_USERNAME` | 无 | MQTT 用户名。 |
| `MQTT_PASSWORD` | 无 | MQTT 密码。 |
| `MQTT_CLIENT_ID` | `device_id` | MQTT client ID。 |
| `MQTT_USE_SSL` | `false` | 是否启用 TLS。要求开发板提供 `ssl` 支持。 |
| `MQTT_KEEP_ALIVE` | `60` | MQTT keepalive 秒数。 |
| `MQTT_RETRY_DELAY_S` | `10` | MQTT 连接失败后的重试等待时间。 |
| `MQTT_STATUS_PUBLISH_INTERVAL_S` | `30` | 状态发布周期，单位秒。 |
| `MQTT_TOPIC_PREFIX` | `usb_host_waker` | 设备主题前缀。 |
| `MQTT_WAKE_PAYLOAD` | `WAKE` | Home Assistant 按钮按下时发布的 payload。 |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | Home Assistant discovery 前缀。 |
| `HA_STATUS_TOPIC` | `homeassistant/status` | Home Assistant birth message topic。 |
| `HA_STATUS_ONLINE_PAYLOAD` | `online` | 用来触发重新发布 discovery 的 birth payload。 |
| `HA_DEVICE_ID` | 由 CPU UID 或 MAC 推导 | 设备稳定 ID，用于 MQTT 主题和 discovery。 |
| `HA_DEVICE_NAME` | `USB Host Waker` | 在 HTTP 页面和 Home Assistant 中展示的设备名。 |
| `HA_DEVICE_MANUFACTURER` | `CircuitPython` | Home Assistant 设备 manufacturer。 |
| `HA_DEVICE_MODEL` | `os.uname().machine` | Home Assistant 设备 model。 |
| `HA_DEVICE_HW_VERSION` | `unknown` | 上报的硬件版本。 |
| `HA_DEVICE_SW_VERSION` | `2.0.0` | 上报的软件版本。 |
| `HA_SUGGESTED_AREA` | 无 | 可选的 Home Assistant suggested area。 |

完整配置示例见 [`settings.toml.example`](settings.toml.example)。

## 项目结构

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

- `code.py`：入口文件，创建 `AppConfig` 并启动 `UsbHostWakerApp`
- `usb_waker/app.py`：负责 Wi-Fi、HTTP、MQTT、唤醒动作和故障恢复的主编排循环
- `usb_waker/http.py`：HTTP 路由、HTML 页面和 JSON 状态接口
- `usb_waker/mqtt.py`：MQTT 连接、Home Assistant discovery 和 retained 状态发布
- `usb_waker/config.py`：基于环境变量的配置加载
- `usb_waker/common.py`：ID、格式化和环境变量解析等通用辅助函数

## 故障排查

### 开发板一直打不开 HTTP 页面

- 检查 `CIRCUITPY_WIFI_SSID` 和 `CIRCUITPY_WIFI_PASSWORD`
- 查看串口日志中的连接尝试和分配到的 IP
- 确认浏览器所在网络和开发板在同一个局域网
- 如果改了 `HTTP_PORT`，访问时记得带上端口

### Home Assistant 没有自动发现设备

- 确认 Home Assistant 已正确启用 MQTT integration
- 检查 broker 地址、账号密码、端口和 TLS 设置
- 确认 `/lib` 中存在 `adafruit_minimqtt`
- 检查 broker 是否已经收到了 `homeassistant/.../config` discovery 主题

### HTTP 能用，但主机没有被唤醒

- 确认 BIOS/UEFI 已启用 USB wake
- 检查操作系统对该 USB 设备或 Hub 的电源管理设置
- 确认目标 USB 口在主机休眠时仍然供电

### 配了 MQTT，但程序提示缺少库

如果报错 `MQTT_BROKER is set but adafruit_minimqtt is missing from /lib`，说明你需要把 `adafruit_minimqtt` 复制到开发板的 `/lib`，或者移除 MQTT 相关配置。

## 开发

这个仓库目前还没有自动化测试。至少可以先做一次本地语法检查：

```bash
python3 -m py_compile code.py usb_waker/*.py
```

修改后的硬件冒烟验证建议：

- 确认开发板重启后能重新连上 Wi-Fi
- 打开 `/` 和 `/status.json`
- 触发 `POST /wake_up`
- 启用 MQTT 时确认 broker 连接成功
- 确认 Home Assistant 实体出现并能更新

## 许可证

本项目采用 MIT License，详见 [`LICENSE`](LICENSE)。
