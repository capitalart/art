#!/usr/bin/env bash

# ================================================================
# setup_systemd_services.sh - Install or update Gunicorn systemd
# services for ART Narrator and EzyGallery. This script copies the
# service unit files from the project `systemd/` folder to
# `/etc/systemd/system`, reloads systemd and restarts the units.
# Requires sudo privileges.
# ================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_SRC_DIR="$PROJECT_DIR/systemd"

install_service() {
  local name="$1"
  local src="$SERVICE_SRC_DIR/$name.service"
  local dest="/etc/systemd/system/$name.service"

  echo "[INFO] Installing $name.service"
  sudo cp "$src" "$dest"
  sudo chmod 644 "$dest"
}

reload_and_restart() {
  local name="$1"
  sudo systemctl daemon-reload
  sudo systemctl enable "$name"
  sudo systemctl restart "$name"
  sudo systemctl status "$name" --no-pager -l
}

main() {
  install_service artnarrator
  install_service ezygallery

  reload_and_restart artnarrator
  reload_and_restart ezygallery

  echo "\n[INFO] Tail of artnarrator logs:" 
  sudo journalctl -u artnarrator -n 40 --no-pager || true
  echo "\n[INFO] Tail of ezygallery logs:" 
  sudo journalctl -u ezygallery -n 40 --no-pager || true
}

main "$@"
