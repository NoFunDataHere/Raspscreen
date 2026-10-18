#!/usr/bin/env bash
# ==========================================================
# RaspEcran - Watchdog Wi-Fi & Reconnexion Automatique
# ==========================================================

GATEWAY="192.168.0.254"
LOG_FILE="/var/log/wifi_watchdog.log"

# Forcer la désactivation de l'économie d'énergie Wi-Fi
/sbin/iw dev wlan0 set power_save off > /dev/null 2>&1 || true

# Test de connectivité vers la passerelle locale
if ! ping -c 2 -W 3 "$GATEWAY" > /dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Perte de liaison avec la passerelle $GATEWAY. Reconnexion Wi-Fi..." >> "$LOG_FILE"
    nmcli device disconnect wlan0 > /dev/null 2>&1 || true
    sleep 2
    nmcli device connect wlan0 > /dev/null 2>&1 || true
    sleep 4
    /sbin/iw dev wlan0 set power_save off > /dev/null 2>&1 || true
    
    if ping -c 1 -W 3 "$GATEWAY" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Reconnexion Wi-Fi réussie !" >> "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Échec ping, relance de NetworkManager..." >> "$LOG_FILE"
        systemctl restart NetworkManager > /dev/null 2>&1 || true
    fi
fi
