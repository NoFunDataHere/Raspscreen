#!/usr/bin/env bash
set -e

# Masquer les autostarts utilisateur
mkdir -p "$HOME/.config/autostart"
for f in gnome-keyring-secrets.desktop gnome-keyring-pkcs11.desktop gnome-keyring-ssh.desktop; do
    printf "[Desktop Entry]\nHidden=true\n" > "$HOME/.config/autostart/$f"
done

# Neutraliser l'activation D-Bus
mkdir -p "$HOME/.local/share/dbus-1/services"
for s in org.freedesktop.secrets.service org.gnome.keyring.PrivatePrompter.service org.gnome.keyring.service org.gnome.keyring.SystemPrompter.service; do
    name="${s%.service}"
    printf "[D-BUS Service]\nName=%s\nExec=/usr/bin/true\n" "$name" > "$HOME/.local/share/dbus-1/services/$s"
done

# Masquer les services systemd utilisateur
systemctl --user mask gnome-keyring-daemon.service gnome-keyring-daemon.socket 2>/dev/null || true

# Tuer les processus en cours
pkill -9 -f gnome-keyring 2>/dev/null || true
echo "[Keyring] GNOME Keyring prompts completely disabled."
