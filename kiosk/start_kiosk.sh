#!/usr/bin/env bash
# ==========================================================
# RaspEcran - Relance du Kiosque Tactile Plein Écran
# ==========================================================

rm -f /tmp/kiosk_exit
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Exécuter kiosk.sh en tâche de fond dans la session Wayland/X11 active
nohup "$SCRIPT_DIR/kiosk.sh" > /dev/shm/kiosk_start.log 2>&1 &
echo "[Kiosk] Mode Kiosque relancé avec succès !"
