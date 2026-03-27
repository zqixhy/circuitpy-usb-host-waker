from usb_waker.app import UsbHostWakerApp
from usb_waker.config import AppConfig


def main():
    config = AppConfig()
    app = UsbHostWakerApp(config)
    app.run()


main()
