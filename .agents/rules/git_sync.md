# Règle de Synchronisation Git Synology

Dans ce projet, le dépôt central de vérité est hébergé sur le NAS Synology privé :
- Remote : origin (ssh://GitFranck@192.168.0.100/volume1/Git/RaspEcran.git)
- Branche principale : main

## Directive de synchronisation obligatoire :
1. **Au début de chaque session ou tâche :** Toujours vérifier et exécuter git pull origin main pour s'assurer de disposer des dernières modifications poussées depuis le PC ou d'autres sessions.
2. **À la fin de chaque tâche ou modification réussie :** Toujours commiter et exécuter git push origin main pour synchroniser le travail sur le NAS Synology.
