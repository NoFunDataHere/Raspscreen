#!/usr/bin/env bash
# ==============================================================================
# RaspEcran - Script d'installation automatique sur Raspberry Pi 4
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=====================================================${NC}"
echo -e "${GREEN}  Installation et Configuration de RaspEcran         ${NC}"
echo -e "${BLUE}=====================================================${NC}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${SUDO_USER:-$(whoami)}"
USER_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)

echo -e "${YELLOW}[1/6] Attribution des permissions d'exécution...${NC}"
chmod +x "$DIR/server.py"
chmod +x "$DIR/kiosk/kiosk.sh"
chmod +x "$DIR/scripts/screen_control.sh"
chmod +x "$DIR/scripts/autoupdate.sh"
chmod +x "$DIR/scripts/enable_readonly_overlay.sh"
chmod +x "$DIR/scripts/disable_readonly_overlay.sh"

echo -e "${YELLOW}[2/6] Installation des paquets nécessaires...${NC}"
sudo apt-get update -qq
sudo apt-get install -y -qq chromium-browser unclutter curl python3 || sudo apt-get install -y -qq chromium unclutter curl python3

echo -e "${YELLOW}[3/6] Configuration des règles d'accès au rétroéclairage (sans sudo)...${NC}"
sudo bash -c 'cat << "EOF" > /etc/udev/rules.d/99-backlight.rules
SUBSYSTEM=="backlight", ACTION=="add", RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"
EOF'
sudo udevadm control --reload-rules && sudo udevadm trigger

echo -e "${YELLOW}[4/6] Configuration de l'autostart graphique du Kiosque...${NC}"
mkdir -p "$USER_HOME/.config/autostart" "$USER_HOME/.config/labwc"
sed "s|/home/pi/RaspEcran|$DIR|g" "$DIR/kiosk/autostart.desktop" > "$USER_HOME/.config/autostart/raspecran-kiosk.desktop"
if ! grep -q "kiosk.sh" "$USER_HOME/.config/labwc/autostart" 2>/dev/null; then
    echo "bash $DIR/kiosk/kiosk.sh &" >> "$USER_HOME/.config/labwc/autostart"
fi
chown -R "$TARGET_USER:$TARGET_USER" "$USER_HOME/.config"

echo -e "${YELLOW}[5/6] Configuration des services d'arrière-plan (Serveur & Auto-Update)...${NC}"
# Adapter le nom d'utilisateur et le répertoire dans le service systemd
sudo sed -e "s|User=pi|User=$CURRENT_USER|g" -e "s|/home/pi/RaspEcran|$DIR|g" "$DIR/systemd/raspecran-server.service" | sudo tee /etc/systemd/system/raspecran-server.service > /dev/null
sudo sed -e "s|User=pi|User=$CURRENT_USER|g" -e "s|/home/pi/RaspEcran|$DIR|g" "$DIR/systemd/raspecran-autoupdate.service" | sudo tee /etc/systemd/system/raspecran-autoupdate.service > /dev/null
sudo cp "$DIR/systemd/raspecran-autoupdate.timer" /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable raspecran-server.service
sudo systemctl restart raspecran-server.service
sudo systemctl enable --now raspecran-autoupdate.timer

echo -e "${YELLOW}[6/6] Configuration de l'écran 800x480 DSI et de la veille...${NC}"
# Vérification et injection du pilote d'écran DSI 7" si absent
CONFIG_FILE="/boot/firmware/config.txt"
[ ! -f "$CONFIG_FILE" ] && CONFIG_FILE="/boot/config.txt"
if [ -f "$CONFIG_FILE" ] && ! grep -q "vc4-kms-dsi-7inch" "$CONFIG_FILE"; then
    echo "[Screen] Activation de l'overlay vc4-kms-dsi-7inch..."
    echo "dtoverlay=vc4-kms-dsi-7inch" | sudo tee -a "$CONFIG_FILE" > /dev/null
fi

CMDLINE_FILE="/boot/firmware/cmdline.txt"
[ ! -f "$CMDLINE_FILE" ] && CMDLINE_FILE="/boot/cmdline.txt"
if [ -f "$CMDLINE_FILE" ] && ! grep -q "video=DSI-1:800x480" "$CMDLINE_FILE"; then
    echo "[Screen] Forçage de la résolution 800x480@60..."
    sudo sed -i 's/$/ video=DSI-1:800x480@60/' "$CMDLINE_FILE"
fi

# Empêcher le verrouillage de session par mot de passe au réveil
gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null || true
gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true

# Active la gestion de veille DPMS gérée
if command -v raspi-config > /dev/null 2>&1; then
    sudo raspi-config nonint do_blanking 0 2>/dev/null || true
fi

echo -e "${YELLOW}[7/7] Protection et longévité de la carte microSD (réduction des écritures)...${NC}"
# 1. Désactivation totale du SWAP (préserve les cellules flash)
if command -v dphys-swapfile > /dev/null 2>&1; then
    echo "[SD-Protect] Désactivation complète du SWAP..."
    sudo dphys-swapfile swapoff 2>/dev/null || true
    sudo dphys-swapfile uninstall 2>/dev/null || true
    sudo systemctl disable --now dphys-swapfile 2>/dev/null || true
    sudo apt-get remove --purge -y dphys-swapfile 2>/dev/null || true
fi

# 2. Journal systemd en mémoire RAM volatile et suppression de rsyslog (évite les écritures continues sur disque)
if [ -f "/etc/systemd/journald.conf" ]; then
    echo "[SD-Protect] Redirection des logs système en mémoire RAM volatile..."
    sudo sed -i 's/^#*Storage=.*/Storage=volatile/' /etc/systemd/journald.conf 2>/dev/null || true
    sudo sed -i 's/^#*RuntimeMaxUse=.*/RuntimeMaxUse=30M/' /etc/systemd/journald.conf 2>/dev/null || true
    sudo systemctl restart systemd-journald 2>/dev/null || true
fi
sudo systemctl disable --now rsyslog 2>/dev/null || true
sudo apt-get remove --purge -y rsyslog logrotate triggerhappy 2>/dev/null || true

# 3. Désactivation des services inutiles qui écrivent en tâche de fond
echo "[SD-Protect] Désactivation des tâches d'arrière-plan inutiles..."
sudo systemctl disable --now apt-daily.timer apt-daily-upgrade.timer apt-daily.service apt-daily-upgrade.service 2>/dev/null || true

# 4. Optimisation des points de montage (/etc/fstab) avec noatime et commit=60 (EXT4 racine uniquement)
if [ -f "/etc/fstab" ]; then
    echo "[SD-Protect] Optimisation fstab (noatime, commit=60 sur ext4)..."
    # S'assurer que /boot/firmware (vfat) ne contient que defaults standard
    sudo sed -i '/vfat/ s/defaults,noatime,commit=60/defaults/g' /etc/fstab 2>/dev/null || true
    # Ajouter noatime et commit=60 UNIQUEMENT sur la partition ext4
    sudo sed -i '/ext4/ s/defaults,noatime/defaults,noatime,commit=60/g' /etc/fstab 2>/dev/null || true
    sudo sed -i '/ext4/ s/defaults\([[:blank:]]\)/defaults,noatime,commit=60\1/g' /etc/fstab 2>/dev/null || true
fi

# 5. Montage des dossiers temporaires (/tmp et /var/tmp) en RAM (tmpfs)
if ! grep -q "tmpfs /tmp" /etc/fstab; then
    echo "[SD-Protect] Montage de /tmp et /var/tmp en RAM (tmpfs)..."
    echo "tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=128m 0 0" | sudo tee -a /etc/fstab > /dev/null
    echo "tmpfs /var/tmp tmpfs defaults,noatime,nosuid,nodev,size=64m 0 0" | sudo tee -a /etc/fstab > /dev/null
fi

echo -e "${BLUE}=====================================================${NC}"
echo -e "${GREEN}  Installation terminée avec succès !                ${NC}"
echo -e "  - Serveur Kiosque démarré sur : http://localhost:8080"
echo -e "  - Mode Kiosque prêt à démarrer au prochain login"
echo -e "  - Carte microSD protégée contre l'usure prématurée"
echo -e "  - Pour lancer manuellement le kiosque maintenant :"
echo -e "      bash $DIR/kiosk/kiosk.sh"
echo -e "${BLUE}=====================================================${NC}"
