#!/usr/bin/env python3
"""
Gestionnaire intelligent de synchronisation Synology Git Server (192.168.0.100).
- Détecte si le NAS Synology est en veille/éteint (programmation horaire).
- Enregistre l'état en attente dans ~/.gemini/antigravity/synology_pending_sync.json.
- Rattrape et pousse automatiquement tous les dépôts dès que le serveur redevient en ligne.
"""

import os
import sys
import json
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SYNOLOGY_IP = "192.168.0.100"
SYNOLOGY_PORT = 22
SOCKET_TIMEOUT = 1.5

def get_queue_file() -> Path:
    base_dir = Path.home() / ".gemini" / "antigravity"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "synology_pending_sync.json"

def is_synology_online(host: str = SYNOLOGY_IP, port: int = SYNOLOGY_PORT, timeout: float = SOCKET_TIMEOUT) -> bool:
    """Vérifie rapidement si le serveur SSH Synology est joignable (timeout non bloquant)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def load_pending_queue() -> dict:
    q_file = get_queue_file()
    if q_file.exists():
        try:
            with open(q_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"pending_repos": []}

def save_pending_queue(data: dict):
    q_file = get_queue_file()
    try:
        with open(q_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[SynologyQueue] Erreur sauvegarde: {e}")

def add_pending_repo(repo_path: str, remote: str = "syno", branch: str = "main", repo_type: str = "project"):
    """Ajoute ou met à jour un dépôt dans la file d'attente de synchronisation."""
    queue = load_pending_queue()
    abs_path = str(Path(repo_path).resolve())
    
    # Éviter les doublons : mettre à jour l'entrée si déjà présente
    found = False
    for item in queue.get("pending_repos", []):
        if str(Path(item.get("path", "")).resolve()) == abs_path:
            item["remote"] = remote
            item["branch"] = branch
            item["repo_type"] = repo_type
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
            item["pending"] = True
            found = True
            break
            
    if not found:
        queue.setdefault("pending_repos", []).append({
            "path": abs_path,
            "remote": remote,
            "branch": branch,
            "repo_type": repo_type,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "pending": True
        })
        
    save_pending_queue(queue)
    print(f"[PENDING] [Synology] Depot mis en attente : {abs_path} ({remote}/{branch})")

def flush_pending_repos():
    """Tente de synchroniser tous les dépôts enregistrés en attente."""
    online = is_synology_online()
    if not online:
        print(f"[INFO] [Synology] Le NAS ({SYNOLOGY_IP}) est toujours hors ligne (extinction programmee).")
        return False

    queue = load_pending_queue()
    pending = queue.get("pending_repos", [])
    if not pending:
        print("[OK] [Synology] Aucun depot en attente de synchronisation.")
        return True

    print(f"[RUN] [Synology] Le NAS est en ligne ! Traitement de {len(pending)} depot(s) en attente...")
    remaining = []

    for item in pending:
        r_path = item.get("path")
        remote = item.get("remote", "syno")
        branch = item.get("branch", "main")
        r_type = item.get("repo_type", "project")

        if not os.path.exists(r_path):
            print(f"[WARN] Depot introuvable : {r_path}, ignore.")
            continue

        print(f"  -> Synchronisation de : {r_path} vers {remote}/{branch}...")
        res = subprocess.run(["git", "push", remote, branch], cwd=r_path, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"    [OK] Succes pour {os.path.basename(r_path)}")
            # Si c'est le catalogue de skills, vérifier s'il faut déclencher sync_shared_skills_online
            if r_type == "skills":
                try:
                    script_path = Path(__file__).resolve().parent / "sync_shared_skills_online.py"
                    if script_path.exists():
                        subprocess.run([sys.executable, str(script_path)], capture_output=True)
                except Exception:
                    pass
        else:
            print(f"    [FAIL] Echec : {res.stderr.strip() or res.stdout.strip()}")
            remaining.append(item)

    queue["pending_repos"] = remaining
    queue["last_flush_attempt"] = datetime.now(timezone.utc).isoformat()
    save_pending_queue(queue)

    if not remaining:
        print("[SUCCESS] [Synology] Tous les depots en attente ont ete synchronises avec succes !")
        return True
    else:
        print(f"[WARN] [Synology] {len(remaining)} depot(s) restent en attente.")
        return False

def sync_or_queue(repo_path: str = ".", remote: str = "syno", branch: str = "main", repo_type: str = "project"):
    """
    Tente la synchronisation immédiate si le Synology est allumé.
    Sinon, met en attente sans provoquer d'erreur bloquante.
    """
    abs_path = str(Path(repo_path).resolve())
    online = is_synology_online()

    if online:
        # Purger la file d'attente d'abord
        flush_pending_repos()
        
        print(f"[SYNC] [Synology] Envoi en direct de {abs_path} vers {remote}/{branch}...")
        res = subprocess.run(["git", "push", remote, branch], cwd=abs_path, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[OK] [Synology] Synchronisation reussie pour {os.path.basename(abs_path)}.")
            return True
        else:
            print(f"[FAIL] [Synology] Erreur de push : {res.stderr.strip() or res.stdout.strip()}")
            add_pending_repo(abs_path, remote, branch, repo_type)
            return False
    else:
        print(f"[OFFLINE] [Synology] Le NAS ({SYNOLOGY_IP}) est indisponible ou eteint (extinction programmee).")
        print(f"[QUEUED] La synchronisation pour '{os.path.basename(abs_path)}' est stockee en attente.")
        print(f"         Elle se declenchera automatiquement des que le serveur sera de nouveau joignable.")
        add_pending_repo(abs_path, remote, branch, repo_type)
        return False

def print_status():
    online = is_synology_online()
    queue = load_pending_queue()
    pending = queue.get("pending_repos", [])

    print("=" * 60)
    print("  ETAT DU SERVEUR GIT SYNOLOGY (192.168.0.100)")
    print("=" * 60)
    print(f"Statut actuel : {'[EN LIGNE]' if online else '[HORS LIGNE] (Eteint ou en veille)'}")
    print(f"File d'attente : {len(pending)} depot(s) en attente")
    for idx, item in enumerate(pending, 1):
        print(f"  {idx}. {item.get('path')} -> {item.get('remote')}/{item.get('branch')} (depuis {item.get('added_at')[:19]})")
    print("=" * 60)

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    target_path = sys.argv[2] if len(sys.argv) > 2 else "."
    
    if action == "status":
        print_status()
    elif action == "flush":
        flush_pending_repos()
    elif action == "sync":
        sync_or_queue(target_path)
    elif action == "queue":
        add_pending_repo(target_path)
    else:
        print(f"Action inconnue: {action}. Utilisation: status | sync [path] | flush | queue [path]")
