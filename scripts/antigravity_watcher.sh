#!/bin/bash
set -euo pipefail

SERVICE_NAME="antigravity-cli-daemon.service"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [antigravity-watcher] $*"
}

# 1. Vérification de la connectivité réseau (DNS / OAuth Google)
if ! getent hosts oauth2.googleapis.com >/dev/null 2>&1; then
    # Machine hors ligne ou DNS pas encore prêt, ne rien faire pour éviter des redémarrages inutiles
    exit 0
fi

# 2. Vérification que le service systemd est actif
IS_ACTIVE=$(systemctl --user is-active "$SERVICE_NAME" 2>/dev/null || true)
if [ "$IS_ACTIVE" != "active" ]; then
    log "Le service $SERVICE_NAME n'est pas actif (état: $IS_ACTIVE). Redémarrage..."
    systemctl --user restart "$SERVICE_NAME"
    exit 0
fi

# 3. Récupération du PID principal
PID=$(systemctl --user show "$SERVICE_NAME" --property=MainPID --value 2>/dev/null || echo 0)
if [ -z "$PID" ] || [ "$PID" -le 0 ]; then
    log "PID invalide ($PID) pour $SERVICE_NAME. Redémarrage..."
    systemctl --user restart "$SERVICE_NAME"
    exit 0
fi

# Calcul de la durée de fonctionnement du processus
ELAPSED=$(ps -o etimes= -p "$PID" 2>/dev/null || echo 0)
ELAPSED=$(echo "$ELAPSED" | tr -d ' ')

# Période de grâce de 45 secondes au lancement pour laisser le temps de négocier la connexion TLS
if [ "$ELAPSED" -lt 45 ]; then
    exit 0
fi

# 4. Vérification de la présence de connexions réseau actives (HTTPS / TURN)
HAS_CONN=0
if ss -tpn 2>/dev/null | grep -q "pid=$PID,"; then
    HAS_CONN=1
fi

# 5. Vérification dans les logs d'une perte d'authentification ou blocage interactif
AUTH_FAILED=0
if journalctl _SYSTEMD_USER_UNIT="$SERVICE_NAME" _PID="$PID" -n 25 --no-pager 2>/dev/null | grep -E -q "could not determine authenticated account|Enter the authorization code:"; then
    AUTH_FAILED=1
fi

if [ "$HAS_CONN" -eq 0 ] || [ "$AUTH_FAILED" -eq 1 ]; then
    log "Le daemon agy (PID $PID) n'est plus connecté (connexions=$HAS_CONN, auth_failed=$AUTH_FAILED, uptime=${ELAPSED}s). Relance..."
    systemctl --user restart "$SERVICE_NAME"
    exit 0
fi
