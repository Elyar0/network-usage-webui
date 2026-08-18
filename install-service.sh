#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="network-usage-webui.service"

# Project directory is wherever this script lives.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PY="${PROJECT_DIR}/app.py"

if [[ ! -f "${APP_PY}" ]]; then
  echo "Cannot find ${APP_PY}"
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-running as root (needed for systemd + package install)..."
  exec sudo -E bash "$0" "$@"
fi

ensure_nethogs() {
  if command -v nethogs >/dev/null 2>&1; then
    return 0
  fi

  echo "nethogs not found; installing..."
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
  fi

  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y nethogs
    return 0
  fi

  if command -v dnf >/dev/null 2>&1; then
    dnf install -y nethogs
    return 0
  fi

  if command -v yum >/dev/null 2>&1; then
    yum install -y nethogs
    return 0
  fi

  if command -v pacman >/dev/null 2>&1; then
    pacman -Sy --noconfirm nethogs
    return 0
  fi

  echo "Unsupported distro (could not auto-install nethogs). Install it manually then re-run."
  exit 1
}

ensure_python3() {
  if command -v python3 >/dev/null 2>&1; then
    return 0
  fi
  echo "python3 not found; please install python3 and re-run."
  exit 1
}

ensure_systemctl() {
  if command -v systemctl >/dev/null 2>&1; then
    return 0
  fi
  echo "systemctl not found (systemd required)."
  exit 1
}

ensure_systemctl
ensure_python3
ensure_nethogs

echo "Installing systemd unit for ${APP_PY}"

cat >"/etc/systemd/system/${UNIT_NAME}" <<EOF
[Unit]
Description=Network Usage Web UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
ExecStart=/usr/bin/python3 "${APP_PY}"
Restart=always
RestartSec=3
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${UNIT_NAME}"
systemctl restart "${UNIT_NAME}"

echo
echo "Installed and started: ${UNIT_NAME}"
echo "Open from this machine:   http://127.0.0.1:8765"
echo "Open from LAN (example):   http://192.168.50.163:8765"
