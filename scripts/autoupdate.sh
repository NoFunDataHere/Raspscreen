#!/usr/bin/env bash
# ==========================================================
# RaspEcran - Script de mise à jour automatique
# ==========================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR" || exit 1

echo "[AutoUpdate] Vérification des mises à jour ($(date))..."

# 1. Mise à jour du code (si dépôt Git)
if [ -d ".git" ]; then
    git fetch origin
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "$LOCAL")
    
    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "[AutoUpdate] Nouvelle version trouvée sur Git. Application..."
        git pull origin main || git pull origin master
        date +%s > "$DIR/VERSION"
        sudo systemctl restart raspecran-server.service
        echo "[AutoUpdate] Code mis à jour avec succès !"
    else
        echo "[AutoUpdate] Le code est déjà à jour."
    fi
fi

# 2. Mise à jour automatique des paquets système de l'OS (Debian / Raspberry Pi OS)
# Exécutée de manière hebdomadaire (le vendredi à 14:00) pour ne jamais allumer l'écran la nuit
DAY_OF_WEEK=$(date +%u) # 5 = Vendredi
if [ "$DAY_OF_WEEK" -eq 5 ] || [ "$1" == "--system" ]; then
    echo "[AutoUpdate] Lancement de la mise à jour hebdomadaire de l'OS (Vendredi)..."
    
    # Vérification de l'accès en écriture (OverlayFS non actif)
    if [ -w "/etc" ]; then
        sudo apt-get update -qq
        sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq \
            -o Dpkg::Options::="--force-confdef" \
            -o Dpkg::Options::="--force-confold"
        sudo apt-get autoremove -y -qq
        sudo apt-get clean # Supprime les paquets téléchargés pour libérer l'espace et éviter les résidus
        echo "[AutoUpdate] Système d'exploitation et paquets mis à jour avec succès !"
        
        # Si un redémarrage est nécessaire suite à une mise à jour du noyau
        if [ -f "/var/run/reboot-required" ]; then
            echo "[AutoUpdate] Redémarrage requis suite à la mise à jour du noyau. Redémarrage dans 1 min..."
            sudo shutdown -r +1 "Mise à jour système terminée. Redémarrage programmé." &
        fi
    else
        echo "[AutoUpdate] Système en mode OverlayFS (lecture seule). Mise à jour système sautée."
    fi
fi
