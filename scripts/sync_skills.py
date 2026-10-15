import os
import sys
import subprocess

PSCP = r"C:\Program Files\PuTTY\pscp.exe"
PLINK = r"C:\Program Files\PuTTY\plink.exe"
PI_HOST = "192.168.0.17"
PI_USER = "raspscreen"
PI_PASS = "raspscreen#1234"

def run_cmd(cmd_list, cwd=None):
    res = subprocess.run(cmd_list, cwd=cwd, capture_output=True, text=True)
    return res.stdout, res.stderr, res.returncode

def sync_skills():
    local_skills_dir = os.path.expanduser(r"~\.gemini\config\skills")
    print(f"=== Synchronisation du repertoire central des skills Antigravity ===")
    print(f"Repertoire local: {local_skills_dir}")
    
    # 1. Verification et commit local sur Windows
    print("\n[1/3] Verification de l'etat des skills locaux (Windows)...")
    out, _, _ = run_cmd(["git", "status", "--porcelain"], cwd=local_skills_dir)
    if out.strip():
        print("  Modifications detectees dans les skills locaux. Commit en cours...")
        run_cmd(["git", "add", "."], cwd=local_skills_dir)
        run_cmd(["git", "commit", "-m", "Mise a jour automatique du catalogue de skills"], cwd=local_skills_dir)
    else:
        print("  Aucune modification locale non commitee.")

    # 2. Pousser / Tirer avec le Synology
    print("\n[2/4] Synchronisation avec le NAS Synology (antigravity-skills.git)...")
    try:
        from synology_sync_manager import sync_or_queue, is_synology_online
        if is_synology_online():
            out, err, code = run_cmd(["git", "pull", "--rebase", "syno", "main"], cwd=local_skills_dir)
            if code == 0:
                print("  Pull depuis Synology: OK")
            else:
                print(f"  Note Pull: {err.strip() or out.strip()}")
        sync_or_queue(local_skills_dir, remote="syno", branch="main", repo_type="skills")
    except Exception as e:
        print(f"  Note Synology: {e}")

    # 3. Mettre a jour le Raspberry Pi
    print("\n[3/4] Mise a jour du catalogue de skills sur le Raspberry Pi...")
    pi_cmd = "cd /home/raspscreen/.gemini/config/skills && git pull origin main"
    res = subprocess.run([PLINK, "-batch", "-pw", PI_PASS, f"{PI_USER}@{PI_HOST}", pi_cmd], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"  Raspberry Pi mis a jour avec succes:\n  {res.stdout.strip()}")
    else:
        print(f"  Erreur mise a jour Pi: {res.stderr.strip()}")

    # 4. Publication automatique des skills autorises vers le GitHub partage en ligne
    print("\n[4/4] Synchronisation des skills autorises vers GitHub (TeamRocket)...")
    shared_script = os.path.join(os.path.dirname(__file__), "sync_shared_skills_online.py")
    if os.path.exists(shared_script):
        run_cmd([sys.executable, shared_script])
    else:
        print("  Script sync_shared_skills_online non trouve, etape ignoree.")

    print("\n=== Synchronisation des skills terminee avec succes ! ===")

if __name__ == "__main__":
    sync_skills()
