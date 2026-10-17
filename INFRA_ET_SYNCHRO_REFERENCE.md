# 📘 Référence Technique : Infrastructure Kiosque Raspberry Pi, Palette UI & Synchronisation Multi-Dépôts

Ce document regroupe l'intégralité de l'architecture technique, des scripts, des configurations système et des règles de synchronisation développées pour le projet **DUCHISCREEN / RaspEcran**.

---

## 1. 🔌 Connexion & Administration du Raspberry Pi

### A. Paramètres Réseau & Identifiants
- **Adresse IP :** `192.168.0.17`
- **Port SSH :** `22`
- **Utilisateur :** `raspscreen`
- **Mot de passe :** `raspscreen#1234`
- **Emplacement du projet sur le Pi :** `/home/raspscreen/antigravity/RaspEcran`
- **Empreinte de clé SSH PuTTY (HostKey) :** `SHA256:6BVqRSxYkR39iYwa+RqCIQt5yCokahIWNB/Oo1pOeFU`

### B. Commandes d'Administration à distance depuis Windows (PowerShell)
Toutes les opérations d'administration et de transfert s'effectuent sans invite interactive grâce aux binaires PuTTY (`plink.exe` et `pscp.exe`).

#### 1. Exécuter une commande à distance (plink)
```powershell
$plink = "C:\Program Files\PuTTY\plink.exe"
$hostKey = "SHA256:6BVqRSxYkR39iYwa+RqCIQt5yCokahIWNB/Oo1pOeFU"
$pw = "raspscreen#1234"
$pi = "raspscreen@192.168.0.17"

# Exemple : Vérifier l'état du serveur backend
& $plink -ssh -batch -hostkey $hostKey -pw $pw $pi "systemctl status raspecran-server.service --no-pager"
```

#### 2. Transférer des fichiers vers le Raspberry Pi (pscp)
```powershell
$pscp = "C:\Program Files\PuTTY\pscp.exe"

# Déployer les fichiers du projet
& $pscp -batch -hostkey $hostKey -pw $pw "server.py" "$pi`:/home/raspscreen/antigravity/RaspEcran/server.py"
& $pscp -batch -hostkey $hostKey -pw $pw -r "dashboard\*" "$pi`:/home/raspscreen/antigravity/RaspEcran/dashboard/"
```

#### 3. Redémarrer le backend et recharger l'affichage en direct
```powershell
# Redémarrage du service systemd Python et relance immédiate de Chromium
& $plink -ssh -batch -hostkey $hostKey -pw $pw $pi "echo 'raspscreen#1234' | sudo -S systemctl restart raspecran-server.service && killall chromium"
```

#### 4. Capture d'écran réelle de l'affichage Kiosk (sans écran physique sous les yeux)
```powershell
# Déclenchement de grim dans le contexte Wayland actif et rapatriement de l'image
& $plink -ssh -batch -hostkey $hostKey -pw $pw $pi "XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 grim /tmp/kiosk_live.png"
& $pscp -batch -hostkey $hostKey -pw $pw "$pi`:/tmp/kiosk_live.png" ".\kiosk_live.png"
```

---

## 2. 🖥️ Configuration de l'OS Raspberry Pi (Kiosque & Matériel)

### A. Caractéristiques de l'Environnement Système
- **OS :** Debian GNU/Linux 13 (Trixie) / Raspberry Pi OS 64-bit.
- **Serveur d'Affichage :** Wayland avec le compositeur léger **`labwc`** (`/usr/bin/labwc -m`).
- **Variables d'environnement Wayland indispensables :**
  ```bash
  export XDG_RUNTIME_DIR="/run/user/1000"
  export WAYLAND_DISPLAY="wayland-0"
  ```
- **Écran :** Écran tactile officiel Raspberry Pi 7" capacitif (DSI), résolution native **800 x 480 pixels**.

### B. Contrôle Matériel du Rétroéclairage & Veille Électrique
Le pilotage se fait directement au niveau du noyau Linux (`/sys/class/backlight`) :
- **Luminosité (0 à 255) :**
  ```bash
  echo 255 | sudo tee /sys/class/backlight/10-0045/brightness  # 100%
  echo 15  | sudo tee /sys/class/backlight/10-0045/brightness  # Atténuation (Dim)
  ```
- **Extinction / Réveil de la dalle DSI :**
  ```bash
  # Via le pilote matériel :
  echo 1 | sudo tee /sys/class/backlight/10-0045/bl_power  # 1 = Éteint (Veille)
  echo 0 | sudo tee /sys/class/backlight/10-0045/bl_power  # 0 = Allumé

  # Via le compositeur Wayland :
  wlr-randr --output DSI-1 --off
  wlr-randr --output DSI-1 --on
  ```

### C. Script Kiosque et Lancement de Chromium (`kiosk/kiosk.sh`)
Chromium est exécuté dans une boucle infinie avec gestion des crashs, désactivation du pinch-to-zoom et stockage du cache en RAM volatile (`/dev/shm`) pour ne pas user la carte SD :

```bash
#!/usr/bin/env bash
LOCKFILE="/dev/shm/raspecran-kiosk.lock"
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    exit 0
fi

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

# Attente de disponibilité du backend local
until curl -s http://localhost:8080 > /dev/null; do
    sleep 1
done

# Nettoyage des flags d'arrêt inopiné pour supprimer la bannière "Restaurer les pages"
PREFS="$HOME/.config/chromium/Default/Preferences"
if [ -f "$PREFS" ]; then
    sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' "$PREFS" 2>/dev/null || true
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS" 2>/dev/null || true
fi

while true; do
    chromium \
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
    sleep 2
done
```

### D. Autostart Bureau Wayland (`~/.config/autostart/autostart.desktop`)
```ini
[Desktop Entry]
Type=Application
Name=RaspEcran Kiosk
Comment=Lancement automatique du kiosque tactile
Exec=/home/raspscreen/antigravity/RaspEcran/kiosk/kiosk.sh
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
```

### E. Service Systemd du Backend (`/etc/systemd/system/raspecran-server.service`)
```ini
[Unit]
Description=RaspEcran Serveur Web & API Kiosque
After=network.target

[Service]
Type=simple
User=raspscreen
WorkingDirectory=/home/raspscreen/antigravity/RaspEcran
ExecStart=/usr/bin/python3 /home/raspscreen/antigravity/RaspEcran/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### F. Protection Intégrale de la Carte MicroSD (OverlayFS Read-Only)
Pour rendre le système insensible aux coupures d'électricité brutales, la racine est basculée en lecture seule avec redirection des écritures en mémoire vive :
```bash
# Activation du système de fichiers en lecture seule (OverlayFS)
sudo raspi-config nonint enable_overlayfs 0
sudo reboot

# Désactivation temporaire pour maintenance ou mises à jour système
sudo raspi-config nonint disable_overlayfs 0
sudo reboot
```

---

## 3. 🎨 Charte Graphique & Palette de Couleurs (Dark Cyberpunk / Sleek)

Toutes les couleurs sont définies sous forme de variables CSS `:root` conçues spécifiquement pour le contraste élevé sur dalle LCD IPS / TN et l'esthétique "tableau de bord connecté" :

```css
:root {
    /* 1. Fonds et Structures */
    --bg-main:       #0b0f19;                    /* Fond d'écran sombre profond */
    --bg-card:       rgba(17, 24, 39, 0.85);     /* Fond des tuiles / cartes */
    --border-card:   rgba(255, 255, 255, 0.08);  /* Ligne de séparation discrète */
    --border-focus:  rgba(0, 242, 254, 0.4);     /* Contour illuminé lors de l'action */

    /* 2. Nuances Typographiques */
    --text-primary:   #f8fafc;  /* Blanc éclatant (titres, valeurs fortes) */
    --text-secondary: #94a3b8;  /* Gris ardoise clair (libellés, métadonnées) */
    --text-muted:     #64748b;  /* Gris atténué (sous-titres, unités) */

    /* 3. Accents Fonctionnels */
    --accent-cyan:    #00f2fe;  /* Cyan néon (Marque DUCHISCREEN, TRMNL Model X, tracé GPS) */
    --accent-blue:    #38bdf8;  /* Bleu ciel (Pluie Météo-France, humidité, badge info) */
    --accent-green:   #10b981;  /* Vert émeraude (En ligne, trafic fluide, colis livrés) */
    --accent-yellow:  #f59e0b;  /* Ambre / Jaune (Alertes voirie, travaux, veille auto) */
    --accent-orange:  #fb923c;  /* Orange vif (Trafic ralenti, livraison en cours, colis) */
    --accent-red:     #ef4444;  /* Rouge vif (Bouchons denses, fermetures de route) */
    --accent-purple:  #c084fc;  /* Violet pastel (Chambre Gab, capteurs secondaires) */

    /* 4. Rayons de courbure */
    --radius-lg: 12px;
    --radius-md: 8px;
    --radius-sm: 6px;
}
```

### Grille d'affichage 800 x 480 px :
- **Conteneur global :** `800px` x `480px`, `padding: 6px 10px`, `gap: 6px`.
- **Top bar (Header) :** Hauteur `44px`.
- **Grille 3 colonnes :**
  ```css
  .dashboard-grid {
      display: grid;
      grid-template-columns: 228px 1fr 248px;
      gap: 6px;
      min-height: 0;
  }
  ```
- **Colonne 1 (228px) :** Météo compacte + Pluie dans l'heure + Flipper Carte/Chat.
- **Colonne 2 (1fr / ~300px) :** Climat Maison (6 pièces en grille 2x3) + Alertes Trajet Voirie Paris.
- **Colonne 3 (248px) :** Carte ultra-compacte TRMNL Model X (~48px) + Suivi des Colis avec défilement tactile et boutons `▲`/`▼`.
- **Footer :** Hauteur `20px`.

---

## 4. 🔄 Architecture de Synchronisation Multi-Niveaux & GitHub Privé

Le workflow synchronise 4 environnements distincts tout en garantissant une étanchéité totale des données privées :

```
[ PC Franck (Windows) ]
       │
       ├── (1) Dépôt Privé Local / LAN ────────> [ Synology NAS (192.168.0.100) ]
       │                                           (ssh://GitFranck@192.168.0.100)
       │                                           * Avec file d'attente hors-ligne *
       │
       ├── (2) Déploiement Réseau Kiosk ───────> [ Raspberry Pi (192.168.0.17) ]
       │                                           (/home/raspscreen/antigravity/...)
       │
       ├── (3) Dépôt GitHub Kiosk Dédié ───────> [ GitHub Privé (Raspscreen) ]
       │                                           (https://github.com/NoFunDataHere/Raspscreen.git)
       │                                           * Remote : github / origin *
       │
       └── (4) Partage Équipe (Skills autorisés) ─> [ GitHub Privé (TeamRocket) ]
                                                   (https://github.com/NoFunDataHere/TeamRocket.git)
                                                   * 100% Anonymisé / Sanitized *
```

---

### A. Gestion de l'Extinction Programmée du Synology NAS
Le serveur Synology NAS (`192.168.0.100`) s'éteint automatiquement selon une programmation horaire (ex. extinction la nuit). 
Le script `scripts/synology_sync_manager.py` garantit que les sessions Antigravity ne sont **jamais bloquées** :

1. **Test rapide non-bloquant :** Sonde le port SSH 22 avec un timeout strict de `1.5s` via socket.
2. **File d'attente locale (`~/.gemini/antigravity/synology_pending_sync.json`) :**
   - Si le NAS est hors ligne, le commit local est validé et le dépôt est inscrit dans la file d'attente locale avec horodatage.
   - Message utilisateur propre : *"Le NAS est éteint. Synchronisation mise en attente."*
3. **Dépilement automatique (Flush) :**
   - Dès que le Synology redevient joignable (en journée), la commande `flush` ou le prochain commit dépile tous les dépôts en attente et les pousse en un éclair vers le NAS.

#### Commandes du gestionnaire Synology :
```bash
# Vérifier l'état actuel et afficher les dépôts en attente :
python scripts/synology_sync_manager.py status

# Synchroniser le projet (ou le mettre en file si le NAS est éteint) :
python scripts/synology_sync_manager.py sync . syno main

# Forcer la purge et l'envoi de tous les dépôts en attente :
python scripts/synology_sync_manager.py flush
```

---

### B. Synchronisation vers le GitHub Privé Partagé (`TeamRocket`)

Pour partager des compétences (Skills Antigravity) avec un collègue sur le dépôt GitHub privé [https://github.com/NoFunDataHere/TeamRocket.git](https://github.com/NoFunDataHere/TeamRocket.git), le système applique un filtre strict.

#### 1. Règle d'autorisation explicite (`shareable: true`)
Dans le fichier `SKILL.md` de chaque skill, un tag YAML frontmatter déclare son éligibilité au partage :
```markdown
---
name: mon-skill-partageable
description: Description de la compétence...
shareable: true
---
```
- Si `shareable: true` ➔ Le skill est automatiquement pris en compte pour GitHub.
- Si `shareable: false` ou absent ➔ Le skill reste **strictement privé** sur le NAS Synology et le PC local.

#### 2. Assainissement Automatique (Data Sanitization & Anonymisation)
Avant d'être poussé sur GitHub, le contenu des skills autorisés est dupliqué dans un dossier temporaire et nettoyé par regex via `scripts/sync_shared_skills_online.py` :
- `192.168.0.100` ➔ `<SYNOLOGY_NAS_IP>`
- `192.168.0.17` ➔ `<RASPBERRY_PI_IP>`
- `c:\Users\franc\` ➔ `C:\Users\<USERNAME>\`
- `/home/raspscreen/` ➔ `/home/<USERNAME>/`
- Mots de passe, tokens JWT Home Assistant et PAT ➔ Remplacés par des placeholders configurables (`<PASSWORD>`, `<TOKEN>`).

#### 3. Authentification GitHub Fine-Grained Personal Access Token (PAT)
- **Dépôt cible :** `https://github.com/NoFunDataHere/TeamRocket.git`
- **Permissions requises sur le token :**
  - Type : *Fine-grained personal access token*
  - Repository access : *Only select repositories* ➔ `NoFunDataHere/TeamRocket`
  - Permissions : **Repository permissions** ➔ **Contents: Read and Write**
- **Syntaxe de push sécurisé :**
  ```bash
  git remote set-url origin https://<GITHUB_PAT>@github.com/NoFunDataHere/TeamRocket.git
  git push -u origin main
  ```

#### 4. Déclenchement de la synchronisation complète :
```bash
python scripts/sync_skills.py
```
Cette commande unique enchaîne :
1. Le commit local des modifications de skills.
2. Le push vers le Synology NAS (ou la mise en file d'attente si le NAS est éteint).
3. La mise à jour à distance du catalogue de skills sur le Raspberry Pi (`192.168.0.17`).
4. L'assainissement et la publication des skills tagués `shareable: true` sur le dépôt GitHub partagé avec votre collègue.
