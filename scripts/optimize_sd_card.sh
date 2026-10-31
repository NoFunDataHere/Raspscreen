#!/usr/bin/env bash
# ==========================================================
# Optimisation de la carte MicroSD pour réduire l'usure
# ==========================================================
set -e

echo "[1/4] Configuration du journal en RAM volatile..."
mkdir -p /etc/systemd/journald.conf.d
cat << 'EOF' > /etc/systemd/journald.conf.d/00-volatile.conf
[Journal]
Storage=volatile
RuntimeMaxUse=30M
ForwardToSyslog=no
EOF
systemctl restart systemd-journald || true

echo "[2/4] Configuration du fstab (commit=60 et tmpfs)..."
if ! grep -q "commit=60" /etc/fstab; then
    sed -i 's/defaults,noatime/defaults,noatime,nodiratime,commit=60/g' /etc/fstab
fi

if ! grep -q "tmpfs /tmp" /etc/fstab; then
    cat << 'EOF' >> /etc/fstab
tmpfs /tmp tmpfs defaults,noatime,nosuid,size=512m 0 0
tmpfs /var/tmp tmpfs defaults,noatime,nosuid,size=128m 0 0
EOF
fi

echo "[3/4] Désactivation des services d'écriture de logs superflus..."
systemctl disable --now rsyslog 2>/dev/null || true

echo "[4/4] Maintien du Wi-Fi en mode actif permanent..."
mkdir -p /etc/NetworkManager/conf.d
printf "[connection]\nwifi.powersave = 2\n" > /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf
iw dev wlan0 set power_save off 2>/dev/null || true

echo "=== Optimisations de la carte SD appliquées avec succès ! ==="
