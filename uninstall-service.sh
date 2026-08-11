#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="network-usage-webui.service"
UNIT_DST="/etc/systemd/system/${UNIT_NAME}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-running as root..."
  exec sudo -E bash "$0" "$@"
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl disable --now "${UNIT_NAME}" || true
  systemctl daemon-reload || true
fi

rm -f "${UNIT_DST}" || true

echo "Removed ${UNIT_NAME}"
echo "Note: I did not delete process history files (e.g. process_usage.json)."
