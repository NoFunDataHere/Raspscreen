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

---

## Fonctionnalités & Optimisations futures

- [x] Affichage de la vitesse du ventilateur / statut thermique sur l'interface Kiosque
- [x] Surveillance proactive de l'état de la carte SD / santé système
