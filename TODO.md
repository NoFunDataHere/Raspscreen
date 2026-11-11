# TODO - RaspEcran

## Matériel & Ventilateur Noctua

- [ ] **Correction : Arrêt du ventilateur lors de l'extinction du Raspberry Pi**
  - **Symptôme constaté :** Lorsque le Raspberry Pi est éteint (shutdown / halt), le ventilateur Noctua continue de tourner à pleine vitesse tant que l'alimentation secteur reste branchée.
  - **Cause racine identifiée :**
    1. *Rail 5V permanent :* Sur le Raspberry Pi 4, les broches Pin 2 et Pin 4 sont connectées directement au bus 5V d'entrée (USB-C). Par défaut (`POWER_OFF_ON_HALT=0`), le PMIC laisse les lignes sous tension lors d'un arrêt logiciel.
    2. *Signal PWM flottant (Tri-state) :* Lorsque le SoC s'éteint, le GPIO 18 passe en haute impédance. Le ventilateur Noctua possède une résistance de pull-up interne sur sa broche PWM (fil bleu). Un signal PWM non alimenté ou flottant est interprété par le ventilateur comme une consigne à 100%.
  - **Pistes de résolution à implémenter plus tard :**
    - *Option A (Logicielle EEPROM Pi 4) :* Configurer l'EEPROM de démarrage (`sudo rpi-eeprom-config --edit`) avec `POWER_OFF_ON_HALT=1` et `WAKE_ON_GPIO=0` pour ordonner au PMIC de couper l'alimentation au shutdown.
    - *Option B (Pull-down matériel) :* Installer une résistance de pull-down (ex: 4.7kΩ à 10kΩ) entre GPIO 18 (PWM) et GND pour forcer la ligne PWM à l'état bas (0%) quand le SoC est éteint.
    - *Option C (Coupure de l'alimentation 5V) :* Relais ou MOSFET piloté par une ligne 3.3V (coupée au shutdown) si le modèle de ventilateur ne coupe pas totalement le moteur à 0% PWM.

---

## Fonctionnalités & Optimisations futures

- [ ] Affichage de la vitesse du ventilateur / statut thermique sur l'interface Kiosque
- [ ] Surveillance proactive de l'état de la carte SD / santé système
