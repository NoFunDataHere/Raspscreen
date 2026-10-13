# 🍓 RaspEcran - Kiosque & Dashboard pour Raspberry Pi 4 (Écran 7" DSI)

Projet complet pour transformer un **Raspberry Pi 4 Model B** équipé d'un écran tactile 7 pouces en un tableau de bord domestique autonome, avec :
- 📱 **Interface tactile fluide** spécialement calibrée pour la résolution 800x480 / 1024x600.
- 🌙 **Mise en veille automatique** du rétroéclairage matériel après inactivité et **réveil instantané au toucher**.
- 🔄 **Mise à jour automatique** (auto-update Git et rechargement sans coupure).
- 🌡️ **Métriques en direct** : Météo locale en temps réel, capteurs maison (domotique), santé du Raspberry Pi (CPU temp, RAM, uptime).

---

## 📁 Structure du Projet

```text
RaspEcran/
├── dashboard/               # Interface Web Kiosque (HTML5, CSS3, JS)
│   ├── index.html           # Page principale du dashboard
│   ├── style.css            # Styles sombres adaptés tactile 7"
│   └── app.js               # Logique horloge, météo, capteurs et veille
├── data/
│   └── home_data.json       # Données domotiques locales éditables
├── kiosk/
│   ├── kiosk.sh             # Script de lancement Chromium plein écran
│   └── autostart.desktop    # Autostart de la session graphique
├── scripts/
│   ├── screen_control.sh    # Contrôle marche/veille de l'écran DSI
│   └── autoupdate.sh        # Script de mise à jour automatique
├── systemd/
│   ├── raspecran-server.service      # Service d'arrière-plan de l'API
│   ├── raspecran-autoupdate.service  # Service de mise à jour
│   └── raspecran-autoupdate.timer    # Planification automatique (4h du matin)
├── install.sh               # Script d'installation clé en main en 1 commande
├── server.py                # Backend Python léger (zéro dépendance pip requise)
└── VERSION                  # Version actuelle
```

---

## 🚀 Étape 1 : Préparation & Flash propre de la carte SD (depuis votre PC)

Pour repartir de zéro sur des bases saines :

1. **Télécharger Raspberry Pi Imager** :
   - Rendez-vous sur [raspberrypi.com/software](https://www.raspberrypi.com/software/) ou lancez l'installateur téléchargé dans vos fichiers temporaires (`imager-v2.0.8.exe`).
2. **Dans Raspberry Pi Imager** :
   - **Modèle de Raspberry Pi** : Choisissez **Raspberry Pi 4**.
   - **Système d'exploitation** : Choisissez **Raspberry Pi OS (64-bit)** (Desktop recommandé pour Wayland/labwc et le support tactile natif).
   - **Stockage** : Choisissez votre carte SD (64 Go).
3. **Personnalisation de l'OS (Icône Engrenage / Modifier les paramètres)** :
   - Définir le nom d'hôte : `raspecran`
   - Définir l'utilisateur et le mot de passe : ex. `pi` / votre mot de passe
   - Configurer le Wi-Fi : Entrez votre SSID et clé Wi-Fi (Pays : `FR`)
   - Services : **Cocher « Activer SSH »** (avec mot de passe)
   - Fuseau horaire : `Europe/Paris`, Clavier : `fr`
4. **Cliquer sur « Écrire »** : Attendez la fin de la gravure et de la vérification.

---

## 🔌 Étape 2 : Câblage de l'écran DSI et premier démarrage

1. **Connexion de la nappe plate DSI** :
   - Branchez la nappe dans le port **DISPLAY** du Raspberry Pi 4 (le port DSI situé entre la prise jack et le port micro-HDMI, **pas** le port CAMERA).
   - Les pistes métalliques de la nappe font face aux contacts du connecteur.
   - Assurez-vous que l'alimentation de l'écran (si fils 5V/GND Dupont supplémentaires) est bien connectée aux broches GPIO 5V (broche 2 ou 4) et GND (broche 6) du Pi.
2. **Insérez la carte SD et branchez l'alimentation USB-C officielle du Pi.**
3. Le Raspberry Pi démarre, se connecte automatiquement à votre Wi-Fi et active SSH.

> 💡 **Précisions pour écran IPS 800x480 DSI** :
> - **Écran officiel Raspberry Pi 7"** (800x480) : reconnu automatiquement avec `display_auto_detect=1`.
> - **Écran Waveshare ou modèle tiers IPS 800x480 DSI** : si rien ne s'affiche, ajoutez dans `/boot/firmware/config.txt` :
>   `dtoverlay=vc4-kms-dsi-7inch`
> - **Si l'écran est monté à l'envers (rotation 180°)** :
>   Ajoutez à la fin de la ligne dans `/boot/firmware/cmdline.txt` :
>   `video=DSI-1:800x480@60,rotate=180`

---

## 🛠️ Étape 3 : Déploiement et Installation en 1 commande

Depuis votre PC (Invite de commande ou PowerShell) :

1. **Connectez-vous en SSH au Pi** :
   ```bash
   ssh pi@raspecran.local
   # ou avec son adresse IP, ex: ssh pi@192.168.x.x
   ```

2. **Transférez le dossier RaspEcran ou clonez-le** :
   ```bash
   # Depuis votre PC PowerShell :
   scp -r c:\Franck\Projets\Antigravity\RaspEcran pi@raspecran.local:/home/pi/RaspEcran
   ```

3. **Sur le Raspberry Pi, lancez l'installateur** :
   ```bash
   cd ~/RaspEcran
   chmod +x install.sh
   ./install.sh
   ```

4. **Redémarrez le Raspberry Pi** :
   ```bash
   sudo reboot
   ```

Au redémarrage, le Raspberry Pi lance automatiquement l'interface plein écran sur votre écran 7 pouces tactile !

---

## 🌙 Gestion de la veille et du réveil

- **Veille automatique** : Après 3 minutes sans contact sur l'écran, le rétroéclairage se coupe pour protéger la dalle et économiser l'énergie.
- **Réveil au toucher** : Touchez simplement l'écran tactile, il se rallume instantanément.
- **Bouton Lune** : Un bouton en haut à droite permet d'éteindre l'écran immédiatement sur demande.

---

## 🔄 Personnalisation des données de la maison

Les données de la carte maison sont lues dans `data/home_data.json`. Vous pouvez :
1. Modifier ce fichier via un script Python, Node.js ou cron.
2. Envoyer des données depuis **Home Assistant**, **Jeedom** ou **Node-RED** via une simple requête HTTP POST ou en modifiant ce fichier partagé.
