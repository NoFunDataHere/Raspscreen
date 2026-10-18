#!/usr/bin/env bash
# ==========================================================
# RaspEcran - Watchdog Wi-Fi & Reconnexion Automatique
# Exécuté toutes les 60 secondes par systemd timer
# ==========================================================

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

TARGET_SSID="Joker_IoT"
GATEWAY="192.168.0.254"
LOG_TAG="raspecran-wifi-watchdog"

# 1. Vérifier et forcer l'extinction du mode économie d'énergie
if command -v iw > /dev/null 2>&1; then
    iw dev wlan0 set power_save off 2>/dev/null || true
fi

# 2. Test 1 : Vérification de l'état de l'interface wlan0
IS_CONNECTED=false
if nmcli -t -f DEVICE,STATE dev | grep -q "^wlan0:connected"; then
    IS_CONNECTED=true
fi

# 3. Test 2 : Ping de la passerelle locale (Freebox)
PING_OK=false
if [ "$IS_CONNECTED" = true ] && ping -c 2 -W 3 "$GATEWAY" > /dev/null 2>&1; then
    PING_OK=true
fi

# 4. Si tout va bien, sortie silencieuse
if [ "$IS_CONNECTED" = true ] && [ "$PING_OK" = true ]; then
    exit 0
fi

# 5. Décrochage détecté -> Procédure de reconnexion
logger -t "$LOG_TAG" "[Alerte] Décrochage Wi-Fi détecté (wlan0 connected: $IS_CONNECTED, ping gateway: $PING_OK). Tentative de reconnexion à $TARGET_SSID..."

# Étape A : Tentative de connexion directe au SSID prioritaire
nmcli dev wifi connect "$TARGET_SSID" 2>/dev/null || true
sleep 3

# Étape B : Si toujours non joignable, réinitialisation de l'interface wlan0
if ! ping -c 1 -W 3 "$GATEWAY" > /dev/null 2>&1; then
    logger -t "$LOG_TAG" "[Alerte] Reconnexion directe échouée. Réinitialisation de l'interface wlan0..."
    nmcli device disconnect wlan0 2>/dev/null || true
    sleep 2
    nmcli device connect wlan0 2>/dev/null || true
    sleep 4
fi

# Étape C : Vérification finale et secours NetworkManager si besoin
if ping -c 2 -W 3 "$GATEWAY" > /dev/null 2>&1; then
    logger -t "$LOG_TAG" "[Succès] Reconnexion Wi-Fi à $TARGET_SSID rétablie avec succès !"
    iw dev wlan0 set power_save off 2>/dev/null || true
else
    logger -t "$LOG_TAG" "[Critique] Échec de reconnexion locale. Relance complète du service NetworkManager..."
    systemctl restart NetworkManager 2>/dev/null || true
    sleep 5
    iw dev wlan0 set power_save off 2>/dev/null || true
fi
