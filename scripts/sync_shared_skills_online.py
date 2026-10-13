import os
import sys
import subprocess
import shutil
import tempfile
import re

SHARED_GIT_URL = "https://github.com/NoFunDataHere/TeamRocket.git"
LOCAL_SKILLS_DIR = os.path.expanduser(r"~\.gemini\config\skills")

# Mots-cles et expressions sensibles a anonymiser
SANITIZE_RULES = [
    # Paths avec nom d'utilisateur
    (re.compile(r'c:\\Users\\franc\\', re.IGNORECASE), r'C:\\Users\\<USERNAME>\\'),
    (re.compile(r'/home/raspscreen/', re.IGNORECASE), r'/home/<USERNAME>/'),
    (re.compile(r'c:\\Franck\\Projets\\', re.IGNORECASE), r'C:\\Projects\\'),
    # Identifiants et IP prives
    (re.compile(r'192\.168\.0\.100', re.IGNORECASE), r'<SYNOLOGY_NAS_IP>'),
    (re.compile(r'192\.168\.0\.17', re.IGNORECASE), r'<RASPBERRY_PI_IP>'),
    (re.compile(r'GitFranck', re.IGNORECASE), r'<GIT_USER>'),
    (re.compile(r'raspscreen', re.IGNORECASE), r'<USER>'),
    (re.compile(r'SkatoPoustaki!2026', re.IGNORECASE), r'<PASSWORD>'),
]

def sanitize_content(text):
    for pattern, replacement in SANITIZE_RULES:
        text = pattern.sub(replacement, text)
    return text

def is_skill_shareable(skill_dir):
    skill_file = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_file):
        return False
    try:
        content = open(skill_file, "r", encoding="utf-8").read()
        # Verifier frontmatter YAML
        if "shareable: true" in content.lower():
            return True
        if "shareable: false" in content.lower():
            return False
        # Si non specifie, verifier par securite
        return False
    except Exception:
        return False

def sync_shared_online():
    print(f"=== Publication des Skills Partageables vers GitHub ({SHARED_GIT_URL}) ===")
    
    # 1. Identifier les skills autorises
    shareable_skills = []
    for item in os.listdir(LOCAL_SKILLS_DIR):
        full_path = os.path.join(LOCAL_SKILLS_DIR, item)
        if os.path.isdir(full_path) and item != ".git":
            if is_skill_shareable(full_path):
                shareable_skills.append(item)
            else:
                print(f"[-] Skill non partageable (ignore): {item}")

    print(f"\nSkills autorises pour le partage en ligne: {shareable_skills}")
    if not shareable_skills:
        print("Aucun skill marque comme partageable ('shareable: true'). Rien a publier.")
        return

    # 2. Creer un dossier temporaire pour preparer la version assainie (sanitized)
    temp_dir = tempfile.mkdtemp(prefix="shared_skills_")
    try:
        print(f"\n[1/3] Preparation et assainissement des donnees privees...")
        for sname in shareable_skills:
            src = os.path.join(LOCAL_SKILLS_DIR, sname)
            dst = os.path.join(temp_dir, sname)
            shutil.copytree(src, dst)
            
            # Assainir tous les fichiers texte du skill
            for root, _, files in os.walk(dst):
                for f in files:
                    fpath = os.path.join(root, f)
                    try:
                        content = open(fpath, "r", encoding="utf-8").read()
                        clean_content = sanitize_content(content)
                        if clean_content != content:
                            print(f"  [Sanitized] Info privee remplacee dans: {os.path.relpath(fpath, temp_dir)}")
                        open(fpath, "w", encoding="utf-8").write(clean_content)
                    except Exception:
                        pass

        # Ajouter un README d'accueil pour le collegue
        readme_path = os.path.join(temp_dir, "README.md")
        open(readme_path, "w", encoding="utf-8").write(f"""# Antigravity Shared Skills Repository

Ce repertoire contient les skills Antigravity partages par l'equipe.

## Skills disponibles :
{chr(10).join(f"- **{s}**" for s in shareable_skills)}

## Installation chez un collaborateur :
Copiez simplement le dossier d'un skill dans votre repertoire personnel Antigravity :
- Sous Windows : `%USERPROFILE%\\.gemini\\config\\skills\\<nom-du-skill>`
- Sous Linux / macOS : `~/.gemini/config/skills/<nom-du-skill>`
""")

        # 3. Initialiser Git et pousser vers le remote GitHub
        print(f"\n[2/3] Verification et commit du depot partage...")
        subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
        subprocess.run(["git", "branch", "-m", "main"], cwd=temp_dir, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Mise a jour des skills partages de l'equipe"], cwd=temp_dir, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", SHARED_GIT_URL], cwd=temp_dir, capture_output=True)

        print(f"\n[3/3] Publication vers {SHARED_GIT_URL}...")
        res = subprocess.run(["git", "push", "-u", "--force", "origin", "main"], cwd=temp_dir, capture_output=True, text=True)
        if res.returncode == 0:
            print("  [SUCCES] Les skills partages ont ete publies sur GitHub avec succes !")
        else:
            print(f"  Note de transmission: {res.stderr.strip() or res.stdout.strip()}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    sync_shared_online()
