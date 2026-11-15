# TODO - RaspEcran

## Matériel & Ventilateur Noctua

- [x] **Correction logicielle : Résolution du bug de dépassement de ligne config.txt**
  - **Problème résolu :** La ligne `dtoverlay=pwm-fan` dépassait 80 caractères et corrompait le seuil `cpu-hot` à `0 °C`, ce qui forçait le ventilateur en continu à 69% même à basse température.
  - **Correction appliquée :** Remplacement par la directive officielle propre `dtoverlay=pwm-fan`.
  - **Résultat vérifié en direct :** 
    - Seuil 50 °C rétabli.
    - À 47,7 °C : Ventilateur en état `0` (0% PWM, 0 RPM).
    - Vitesse progressive de 50 °C à 75 °C.

- [x] **Configuration logicielle : Coupure d'alimentation EEPROM à l'extinction**
  - **Correction appliquée :** Flash de l'EEPROM bootloader avec `POWER_OFF_ON_HALT=1` et `WAKE_ON_GPIO=0`.
  - **Action physique utilisateur :** Déplacer le fil jaune (+ alimentation) de la Broche 2 (5V permanent) vers la Broche 1 (3,3V commutable par le PMIC). Le ventilateur s'éteint ainsi à 100% dès l'extinction du Raspberry Pi.

- [ ] **Écran CX101 : Contrôle matériel complet du rétroéclairage (On/Off + Luminosité PWM)**
  - **Constat vérifié :** L'écran CX101 (HDMI-A-1) ne supporte ni la coupure DPMS (`wlopm` / `wlr-randr`), ni le contrôle DDC/CI (`0x37 unresponsive`), et maintient son rétroéclairage allumé en veille.
  - **Action matérielle (3 câbles DuPont Femelle-Femelle + switch `BL` vers la droite) :**
    - `GND` (broche du haut sur carte écran) &rarr; **Broche 9 (`GND`)** du Raspberry Pi
    - `EN` (broche du bas sur carte écran, On/Off) &rarr; **Broche 11 (`GPIO 17`)** du Raspberry Pi (3,3V = On, 0V = Off)
    - `PWM` (broche du milieu sur carte écran, Luminosité) &rarr; **Broche 33 (`GPIO 13` / `PWM1`)** du Raspberry Pi *(sans conflit avec `PWM0` utilisé par le Noctua sur GPIO 18)*
  - **Actions logicielles à implémenter après câblage :**
    - Activer le canal matériel `PWM1` sur GPIO 13 dans `/boot/firmware/config.txt` (ex: `dtoverlay=pwm,pin=13,func=4`).
    - Mettre à jour `server.py` (`set_screen_backlight` / `set_screen_brightness`) et `scripts/screen_control.sh` pour piloter `GPIO 17` (veille/réveil réel à 0%) et `pwmchip0/pwm1` (variation de luminosité jour/nuit).

---

## Fonctionnalités & Optimisations futures

- [x] Affichage de la vitesse du ventilateur / statut thermique sur l'interface Kiosque
- [x] Surveillance proactive de l'état de la carte SD / santé système
