# Règle de Synchronisation Git Synology

Dans ce projet, le dépôt central de référence est hébergé sur le NAS Synology privé :
- Synology Git Remote : `ssh://GitFranck@192.168.0.100/volume1/Git/RaspEcran.git`
- Branche principale : `main`

## Directive de synchronisation obligatoire pour Antigravity :
1. **Au début de chaque session ou tâche :**
   - Toujours exécuter `git pull` (ou `git pull syno main` / `git pull origin main`) pour s'assurer de disposer de la toute dernière version poussée depuis l'autre machine (PC ou Raspberry Pi).
2. **À la fin de chaque tâche ou modification réussie :**
   - Toujours commiter et exécuter `git push` pour renvoyer le travail sur le NAS Synology.

