# Règle de Synchronisation Git Synology & Raspscreen

Dans ce projet, le dépôt central de référence est hébergé sur le NAS Synology privé :
- Synology Git Remote : `ssh://GitFranck@192.168.0.100/volume1/Git/RaspEcran.git`
- GitHub Remote dédié : `https://github.com/NoFunDataHere/Raspscreen.git`
- Branche principale : `main`

## Gestion des Secrets & Sécurité :
- **Sur le Synology Git (Privé / Réseau local) :** Tous les secrets (tokens, mots de passe, configurations locales, adresses IP) sont **strictement CONSERVÉS intacts** sans censure ni caviardage afin de permettre une restauration 100% fonctionnelle.
- **Sur GitHub en ligne :** Seules des versions exemptes de secrets d'infrastructure ou de clés privées non autorisées sont poussées.

## Directive de synchronisation obligatoire pour Antigravity :
1. **Au début de chaque session ou tâche :**
   - Vérifier l'état du NAS avec `python scripts/synology_sync_manager.py flush`.
   - Si le NAS est en ligne, dépiler la file d'attente et exécuter `git pull` pour récupérer les dernières modifications.
2. **À la fin de chaque tâche ou modification réussie :**
   - Commiter localement le travail avec un message explicite.
   - Exécuter la synchronisation intelligente :
     ```bash
     python scripts/synology_sync_manager.py sync . syno main
     ```
   - **Gestion de l'extinction programmée du Synology :**
     - Si le NAS est allumé : le push direct est effectué et la file en attente est purgée.
     - Si le NAS est éteint (nuit / planification d'extinction) : la synchronisation est automatiquement stockée dans `~/.gemini/antigravity/synology_pending_sync.json` sans bloquer le travail. Elle sera purgée et poussée automatiquement dès que le serveur sera de nouveau joignable en journée.


