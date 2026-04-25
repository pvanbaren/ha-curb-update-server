"""Constants for Curb Update Server integration."""

DOMAIN = "curb_update_server"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 80

# Maximum time the update server stays running before the integration
# stops it automatically as a safety. Curb devices poll roughly hourly, so
# one window is enough to deliver the payload to a device on the LAN.
AUTO_STOP_SECONDS = 3600

# Required firmware files
REQUIRED_FILES = [
    "os.tar.gz.gpg",
    "os.tar.gz.gpg.md5sum",
    "update.tar.gz.gpg",
    "update.tar.gz.gpg.md5sum"
]