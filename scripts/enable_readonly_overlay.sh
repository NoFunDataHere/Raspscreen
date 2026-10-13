#!/usr/bin/env bash
# ==============================================================================
# Active l'OverlayFS natif de Raspberry Pi OS (Lecture seule intégrale)
# Les écritures se font uniquement en RAM volatile.
# Aucun risque de corruption de la carte microSD lors de coupures de courant.
# ==============================================================================

set -e

echo "[OverlayFS] Activation du système de fichiers en lecture seule..."
if command -v raspi-config > /dev/null 2>&1; then
    sudo raspi-config nonint enable_overlayfs 0
    echo "[OverlayFS] Succès ! La carte microSD sera en lecture seule au prochain démarrage."
    echo "[OverlayFS] Pour appliquer immédiatement : sudo reboot"
else
    echo "[Erreur] raspi-config introuvable."
    exit 1
fi
