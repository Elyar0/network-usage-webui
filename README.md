# Network Usage Web UI

A tiny local web app that shows your device's real-time network usage (download/upload) in the browser.

## Features

- Live download/upload speed (bytes per second)
- Total downloaded/uploaded bytes
- Lightweight line chart that updates every second
- Live per-process network usage (top active processes)
- Daily top processes by total network usage
- All-time top processes by total network usage
- Process names are normalized to app names only (example: `chrome`)
- No external Python dependencies (uses `/proc/net/dev`)

## Run

```bash
cd /home/elyar/Projects/network-usage-webui
python3 app.py
```

Then open:

`http://127.0.0.1:8765`

## Install as always-on service (system startup)

```bash
cd /home/elyar/Projects/network-usage-webui
chmod +x install-service.sh uninstall-service.sh
sudo ./install-service.sh
```

Useful service commands:

```bash
sudo systemctl status network-usage-webui.service
sudo journalctl -u network-usage-webui.service -f
sudo systemctl restart network-usage-webui.service
```

Uninstall service:

```bash
cd /home/elyar/Projects/network-usage-webui
sudo ./uninstall-service.sh
```

## Requirements

- Linux
- `nethogs` installed for per-process stats:

```bash
sudo apt install nethogs
```

Run as root (service does this) or grant capabilities to nethogs:

```bash
sudo setcap cap_net_admin,cap_net_raw+ep /usr/sbin/nethogs
```

## Notes

- Works on Linux (reads network stats from `/proc/net/dev`)
- Loopback traffic (`lo`) is excluded
- Process usage is estimated from `nethogs` live rates and accumulated in `process_usage.json`
- Stop the server with `Ctrl+C`
