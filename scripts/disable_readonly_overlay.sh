#!/usr/bin/env bash
# ==============================================================================
# Désactive l'OverlayFS pour permettre l'écriture sur la carte microSD
# Utile lors de mises à jour majeures du système.
# ==============================================================================

set -e

echo "[OverlayFS] Désactivation du mode lecture seule pour maintenance..."
if command -v raspi-config > /dev/null 2>&1; then
    sudo raspi-config nonint disable_overlayfs 0
    echo "[OverlayFS] Mode lecture seule désactivé. Redémarrage requis pour appliquer :"
    echo "  sudo reboot"
else
    echo "[Erreur] raspi-config introuvable."
    exit 1
fi
