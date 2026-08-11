#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/elyar/Projects/network-usage-webui"
UNIT_NAME="network-usage-webui.service"
UNIT_SRC="${PROJECT_DIR}/${UNIT_NAME}"
UNIT_DST="/etc/systemd/system/${UNIT_NAME}"

if [[ ! -f "${UNIT_SRC}" ]]; then
  echo "Service file not found: ${UNIT_SRC}"
  exit 1
fi

cp "${UNIT_SRC}" "${UNIT_DST}"
systemctl daemon-reload
systemctl enable --now "${UNIT_NAME}"
systemctl status "${UNIT_NAME}" --no-pager

echo
echo "Installed and started ${UNIT_NAME}"
echo "Open: http://127.0.0.1:8765"
