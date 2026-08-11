# Network Usage Web UI

Real-time network usage dashboard (download/upload speed + top processes) with a tiny Python backend and a simple web UI.

## Install (copy/paste)

```bash
git clone git@github.com:Elyar0/network-usage-webui.git
cd network-usage-webui

chmod +x install-service.sh uninstall-service.sh
sudo ./install-service.sh
```

Open the dashboard:

`http://127.0.0.1:8765`

From another device on your LAN (same network):

`http://<your-lan-ip>:8765`

## Uninstall (copy/paste)

```bash
cd network-usage-webui
sudo ./uninstall-service.sh
```

## Notes

- Works on Linux.
- Process-level stats use `nethogs` (the installer script attempts to auto-install it when missing).
- If you want to run without the systemd service, use `python3 app.py`.
