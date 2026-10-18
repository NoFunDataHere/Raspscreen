#!/usr/bin/env bash
# ==========================================================
# RaspEcran - Script de lancement Kiosque Plein Écran
# ==========================================================

# Empêcher le lancement en doublon
LOCKFILE="/dev/shm/raspecran-kiosk.lock"
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "[Kiosk] Une instance est déjà en cours d'exécution. Sortie."
    exit 0
fi

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

# Attendre que le serveur backend soit prêt
echo "[Kiosk] En attente du serveur web..."
until curl -s http://localhost:8080 > /dev/null; do
    sleep 1
done
echo "[Kiosk] Serveur web détecté !"

# Masquer le curseur de souris après 0.5s d'inactivité (si X11)
if command -v unclutter > /dev/null 2>&1; then
    unclutter -idle 0.5 -root &
fi

# Nettoyage des flags de crash de Chromium pour éviter le message "Restaurer les pages ?"
PREFS="$HOME/.config/chromium/Default/Preferences"
if [ -f "$PREFS" ]; then
    sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' "$PREFS" 2>/dev/null || true
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS" 2>/dev/null || true
fi

# Détection de la commande Chromium (chromium ou chromium-browser)
BROWSER="chromium-browser"
if ! command -v "$BROWSER" > /dev/null 2>&1; then
    BROWSER="chromium"
fi

echo "[Kiosk] Lancement de Chromium en mode kiosque tactile..."

# Lancement en boucle infinie (si le navigateur est fermé par mégarde, il redémarre)
while true; do
    if [ -f "/tmp/kiosk_exit" ]; then
        echo "[Kiosk] Arrêt demandé (/tmp/kiosk_exit détecté). Sortie de la boucle."
        exit 0
    fi

    "$BROWSER" \
        --password-store=basic \
        --lang=fr-FR \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --no-first-run \
        --fast \
        --fast-start \
        --disable-pinch \
        --overscroll-history-navigation=0 \
        --disable-features=Translate,OptimizationHints,MediaRouter \
        --disable-extensions \
        --disable-component-update \
        --disable-background-networking \
        --disable-session-crashed-bubble \
        --hide-scrollbars \
        --enable-gpu-rasterization \
        --check-for-update-interval=31536000 \
        --touch-events=enabled \
        --autoplay-policy=no-user-gesture-required \
        --window-size=800,480 \
        --window-position=0,0 \
        --disk-cache-dir=/dev/shm/chromium-cache \
        --disk-cache-size=104857600 \
        http://localhost:8080 200>&-
    
    if [ -f "/tmp/kiosk_exit" ]; then
        echo "[Kiosk] Sortie demandée après fermeture de Chromium. Arrêt du script."
        exit 0
    fi

    echo "[Kiosk] Navigateur fermé, redémarrage dans 2 secondes..."
    sleep 2
done
