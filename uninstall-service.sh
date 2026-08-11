#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="network-usage-webui.service"
UNIT_DST="/etc/systemd/system/${UNIT_NAME}"

systemctl disable --now "${UNIT_NAME}" || true
rm -f "${UNIT_DST}"
systemctl daemon-reload

echo "Removed ${UNIT_NAME}"
