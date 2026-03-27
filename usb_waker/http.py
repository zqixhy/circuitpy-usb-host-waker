import time

from adafruit_httpserver import GET, POST, Request, Response, Server

from usb_waker.common import html_escape, human_time_delta


class HttpServerService:
    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.server = None
        self.last_restart = 0

    def is_running(self):
        return self.server is not None

    def render_status_table_html(self):
        status = self.app.get_status_dict()
        error_html = "<p>None</p>"
        if status["last_error_text"]:
            error_html = "<pre>{}</pre>".format(html_escape(status["last_error_text"]))

        return """
<h2>Status</h2>
<table border='1' cellpadding='4' cellspacing='0'>
    <tr><th>Item</th><th>Value</th></tr>
    <tr><td>Wi-Fi connected</td><td>{wifi_connected}</td></tr>
    <tr><td>USB connected</td><td>{usb_connected}</td></tr>
    <tr><td>MQTT enabled</td><td>{mqtt_enabled}</td></tr>
    <tr><td>MQTT connected</td><td>{mqtt_connected}</td></tr>
    <tr><td>IP</td><td>{ip}</td></tr>
    <tr><td>HTTP URL</td><td>{http_url}</td></tr>
    <tr><td>Uptime</td><td>{uptime}</td></tr>
    <tr><td>Last HTTP restart</td><td>{last_http_restart}</td></tr>
    <tr><td>Last MQTT connect</td><td>{last_mqtt_connect}</td></tr>
    <tr><td>Free memory</td><td>{free_memory}</td></tr>
    <tr><td>Wake count</td><td>{wake_count}</td></tr>
    <tr><td>Last wake source</td><td>{last_wake_source}</td></tr>
    <tr><td>Reset reason</td><td>{reset_reason}</td></tr>
    <tr><td>MQTT wake topic</td><td>{wake_topic}</td></tr>
</table>
<h2>Last Error</h2>
{error_html}
""".format(
            wifi_connected=status["wifi_connected"],
            usb_connected=status["usb_connected"],
            mqtt_enabled=status["mqtt_enabled"],
            mqtt_connected=status["mqtt_connected"],
            ip=html_escape(status["ip"]),
            http_url=html_escape(status["http_url"]),
            uptime=human_time_delta(status["uptime_seconds"]),
            last_http_restart=human_time_delta(status["last_http_restart_seconds"]),
            last_mqtt_connect=human_time_delta(status["last_mqtt_connect_seconds"]),
            free_memory=status["free_memory"],
            wake_count=status["wake_count"],
            last_wake_source=html_escape(status["last_wake_source"]),
            reset_reason=html_escape(status["reset_reason"]),
            wake_topic=html_escape(self.app.mqtt.topics["command_wake"]),
            error_html=error_html,
        )

    def render_wake_form_html(self):
        return """
<h2>Wake Up Host</h2>
<p>Trigger a wake report over USB HID.</p>
<form id="wake-form" method="POST" action="/wake_up">
    <button id="wake-button" type="submit">Wake Up</button>
</form>
"""

    def render_client_script_html(self):
        return """
<script>
(function () {
    var form = document.getElementById("wake-form");
    var button = document.getElementById("wake-button");
    var notice = document.getElementById("notice");
    var statusPanel = document.getElementById("status-panel");

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function finishRequest() {
        button.disabled = false;
        button.textContent = "Wake Up";
    }

    if (!form || !button || !notice || !statusPanel || !window.fetch || !window.DOMParser) {
        return;
    }

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        button.disabled = true;
        button.textContent = "Sending...";
        notice.innerHTML = "<p>Sending wake request...</p>";

        fetch(form.action, { method: "POST" })
            .then(function (response) {
                return response.text();
            })
            .then(function (html) {
                var doc = new DOMParser().parseFromString(html, "text/html");
                var nextNotice = doc.getElementById("notice");
                var nextStatus = doc.getElementById("status-panel");

                if (nextNotice) {
                    notice.innerHTML = nextNotice.innerHTML;
                }
                if (nextStatus) {
                    statusPanel.innerHTML = nextStatus.innerHTML;
                }
            })
            .catch(function (error) {
                notice.innerHTML = "<h2>Error</h2><pre>" + escapeHtml(error) + "</pre>";
            })
            .then(finishRequest);
    });
})();
</script>
"""

    def html_page(self, title, body_html):
        return """\
<html>
    <head>
        <title>{}</title>
        <meta charset="utf-8">
    </head>
    <body>
        <h1>{}</h1>
        {}
    </body>
</html>
""".format(title, title, body_html)

    def render_home_page_html(self, notice_html=""):
        return self.html_page(
            self.config.device_name,
            "<div id='notice'>{}</div><div id='controls'>{}</div><div id='status-panel'>{}</div>{}".format(
                notice_html,
                self.render_wake_form_html(),
                self.render_status_table_html(),
                self.render_client_script_html(),
            ),
        )

    def start(self):
        if self.server is not None:
            return

        self.app.log("Starting HTTP server...")
        http_server = Server(self.app.get_socket_pool(), debug=self.config.http_debug)

        @http_server.route("/", GET)
        def root(request: Request):
            return Response(
                request,
                self.render_home_page_html(),
                content_type="text/html",
            )

        @http_server.route("/healthz", GET)
        def healthz(request: Request):
            return Response(request, "ok", content_type="text/plain")

        @http_server.route("/wake_up", POST)
        def wake_up(request: Request):
            try:
                self.app.wake_host("http")
                return Response(
                    request,
                    self.render_home_page_html(
                        "<h2>Wake request sent.</h2>"
                    ),
                    content_type="text/html",
                )
            except Exception as error:
                self.app.record_error("Wake request", error)
                return Response(
                    request,
                    self.render_home_page_html(
                        "<h2>Error</h2><pre>{}</pre>".format(
                            html_escape(self.app.last_error_text)
                        ),
                    ),
                    content_type="text/html",
                )

        http_server.start(self.app.current_ip(), self.config.http_port)
        self.server = http_server
        self.last_restart = time.monotonic()
        self.app.log("HTTP server started at {}".format(self.app.http_base_url()))

    def stop(self):
        if self.server is None:
            return

        try:
            self.app.log("Stopping HTTP server...")
            self.server.stop()
        except Exception as error:
            self.app.log("Error stopping HTTP server: {}".format(error))

        self.server = None

    def poll(self):
        if self.server is None:
            return

        try:
            self.server.poll()
        except Exception as error:
            self.app.record_error("HTTP server", error)
            self.app.log("HTTP server error: {}".format(error))
            self.stop()
            time.sleep(self.config.http_error_retry_delay_s)

    def restart(self):
        self.stop()
        self.start()
