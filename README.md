# Curb Update Server - Home Assistant Integration

This Home Assistant custom component serves firmware update files for Curb Energy Monitors so you can redirect their cloud endpoints to your local network and enable root access on the device. Once the device has been updated, the [`ha-energycurb`](https://github.com/pvanbaren/ha-energycurb) integration receives its measurements at `homeassistant.local:8989`.

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations** → **⋮** → **Custom repositories**.
2. Add `https://github.com/pvanbaren/ha-curb-update-server` as an **Integration**.
3. Install **Curb Update Server** from HACS and restart Home Assistant.

### Manual

Copy `custom_components/curb_update_server/` into your Home Assistant `custom_components/` directory and restart Home Assistant.

The required firmware files are bundled with the integration at:

```
custom_components/curb_update_server/curbed/
├── os.tar.gz.gpg
├── os.tar.gz.gpg.md5sum
├── update.tar.gz.gpg
└── update.tar.gz.gpg.md5sum
```

## Setup

1. Go to **Settings → Devices & services → Add integration** and search for **Curb Update Server**. The setup form asks for a bind address (default `0.0.0.0`) and a port (default `80`). On Container/Supervised installs, Home Assistant typically can't bind below port 1024 — pick a higher port (e.g. `8080`) and forward port 80 → that port at your router. See **Port Access** below.

2. **DNS Redirect**: Configure your DNS server (like Pi-hole) to redirect `updates.energycurb.com` to your Home Assistant instance's IP address.
   - In Pi-hole: Local DNS → DNS Records → `updates.energycurb.com` → `<your_home_assistant_ip>`
   - For receiving the readings after the update is applied, also ensure `homeassistant.local` → `<your_home_assistant_ip>`

3. **Port Access**: The Curb device hard-codes port 80, so the server must ultimately be reachable there. If Home Assistant can't bind port 80 directly (the typical case for Container/Supervised installs), pick a higher port in the integration's options and forward port 80 → that port at your router/firewall. Make sure port 80 is not exposed to the Internet — this server is for local access only.

## Usage

1. Once the integration is added, the server starts automatically on the configured address and port. As a safety, the server **auto-stops after one hour**; reload the integration from **Settings → Devices & services** if you need another window. To change the bind address or port later, open the integration's **Configure** screen — the server will reload with the new settings.

2. The integration serves the firmware files at:
   - `/api/firmware/os.tar.gz.gpg`
   - `/api/firmware/os.tar.gz.gpg.md5sum`
   - `/api/firmware/update.tar.gz.gpg`
   - `/api/firmware/update.tar.gz.gpg.md5sum`

3. When a Curb device downloads the payload, the integration creates a sticky **persistent notification** ("Curb device updated") with SSH instructions. A neutral info-level log line is also emitted for log-based automations.

4. Once the curb device has been updated, you can remove this integration from **Settings → Devices & services** — it is needed only to redirect the device output to Home Assistant. The auto-stop timer also covers this case if you forget.

5. Install https://github.com/pvanbaren/ha-energycurb to configure the Curb device and allow Home Assistant to receive the measurements.

## How It Works

1. The Curb device checks for updates hourly (plus 0-30 minute random delay)
2. Device downloads OS checksum → detects "new" version
3. Downloads dummy OS update → harmless reboot
4. Device downloads software checksum → detects "new" version
5. Downloads the payload → changes root password and enables SSH
6. Device reboots → SSH access available with `root` / `curb123`
7. Device starts sending readings to http://homeassistant.local:8989

## Logging

The integration logs at:
- **Info** — payload delivered to a device, plus API requests from devices
- **Debug** — local/health-check requests

Firmware-delivery details (SSH command, password reminder) are surfaced as a persistent UI notification rather than a log line.

## Troubleshooting

1. **"curbed directory not found"**: The firmware files should be included in the integration. If missing, ensure all files are present in `custom_components/curb_update_server/curbed/`.

2. **Permission denied / address in use on bind**: Open the integration's **Configure** screen and pick a higher port (e.g. 8080), then forward port 80 → that port at your router/firewall. Binding ports below 1024 typically requires root or `CAP_NET_BIND_SERVICE`, which most HA installs don't grant.

3. **Device not updating**:
   - Verify DNS redirection is working (`nslookup updates.energycurb.com`)
   - Check that port 80 is reachable from the device's network (and forwarded to your configured port if you changed it)
   - From a host on the device's network, try fetching `http://updates.energycurb.com/api/firmware/os.tar.gz.gpg.md5sum` (e.g. with `curl` or a browser). It's the first file the Curb requests, so a successful download confirms DNS, routing, and the server are all wired up correctly
   - Monitor Home Assistant logs for incoming requests

## Security Notes

- This integration serves firmware that modifies device security settings
- Only use on devices you own
- The payload enables SSH access with a known password. It is highly recommended that you log into the curb device and change the root password to a strong password of your choosing.
- Consider network isolation for modified devices

## Credits

The firmware payload bundled in `custom_components/curb_update_server/curbed/` originates from [codearranger/curbed](https://github.com/codearranger/curbed), which documents the update protocol and provides the source for the `update.tar.gz.gpg` script that runs on the device. Refer to that project for details on how the payload is built and signed.
