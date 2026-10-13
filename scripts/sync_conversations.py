import sqlite3
import os
import sys
import subprocess
import json
import glob
import tempfile

# Configuration
PI_HOST = "192.168.0.17"
PI_USER = "raspscreen"
PI_PASS = "raspscreen#1234"
PSCP = r"C:\Program Files\PuTTY\pscp.exe"
PLINK = r"C:\Program Files\PuTTY\plink.exe"

LOCAL_GEMINI = os.path.expanduser(r"~\.gemini\antigravity")
LOCAL_SUMMARIES_DB = os.path.join(LOCAL_GEMINI, "conversation_summaries.db")
LOCAL_CONVOS_DIR = os.path.join(LOCAL_GEMINI, "conversations")
LOCAL_BRAIN_DIR = os.path.join(LOCAL_GEMINI, "brain")

PI_GEMINI = "/home/raspscreen/.gemini/antigravity-cli"
PI_SUMMARIES_DB = f"{PI_GEMINI}/conversation_summaries.db"
PI_CONVOS_DIR = f"{PI_GEMINI}/conversations"
PI_BRAIN_DIR = f"{PI_GEMINI}/brain"
PI_PROJECT_ID = "6915afc2-eb6b-4c47-aca0-107999369f2c"
LOCAL_PROJECT_ID = "48102604-637d-48ed-b34b-69ce47c535a3"

def run_cmd(cmd_list):
    res = subprocess.run(cmd_list, capture_output=True, text=True)
    return res.stdout, res.stderr, res.returncode

def run_plink(remote_cmd):
    return run_cmd([PLINK, "-batch", "-pw", PI_PASS, f"{PI_USER}@{PI_HOST}", remote_cmd])

def sync_conversations(project_keyword="RaspEcran"):
    print(f"=== Synchronisation des conversations pour le projet '{project_keyword}' ===")
    
    # 1. Recuperer les discussions distantes depuis le Pi
    print("\n[1/3] Verification des conversations distantes sur Raspberry Pi...")
    dump_script = f"""
import sqlite3, json
con = sqlite3.connect('{PI_SUMMARIES_DB}')
cur = con.cursor()
rows = cur.execute('SELECT conversation_id, title, preview, step_count, last_modified_time, last_user_input_time, last_user_input_step_index FROM conversation_summaries WHERE workspace_uris LIKE \"%{project_keyword}%\" OR title LIKE \"%{project_keyword}%\"').fetchall()
print(json.dumps(rows))
"""
    out, _, _ = run_plink(f"python3 -c {json.dumps(dump_script)}")
    try:
        pi_convos = json.loads(out.strip())
    except Exception as e:
        print("Erreur:", e, out)
        pi_convos = []

    print(f"Trouve {len(pi_convos)} conversation(s) sur le Pi.")
    
    con_local = sqlite3.connect(LOCAL_SUMMARIES_DB)
    cur_local = con_local.cursor()
    
    for r in pi_convos:
        cid, title, prev, steps, mod_time, user_in_time, user_in_step = r
        local_db = os.path.join(LOCAL_CONVOS_DIR, f"{cid}.db")
        if not os.path.exists(local_db):
            print(f" -> Telechargement depuis Pi: '{title}' ({cid})")
            run_cmd([PSCP, "-batch", "-pw", PI_PASS, f"{PI_USER}@{PI_HOST}:{PI_CONVOS_DIR}/{cid}.db", local_db])
            local_brain = os.path.join(LOCAL_BRAIN_DIR, cid)
            os.makedirs(local_brain, exist_ok=True)
            run_cmd([PSCP, "-batch", "-pw", PI_PASS, "-r", f"{PI_USER}@{PI_HOST}:{PI_BRAIN_DIR}/{cid}/*", local_brain])
            
            cur_local.execute("""
                INSERT INTO conversation_summaries (
                    conversation_id, title, preview, step_count, last_modified_time,
                    workspace_uris, status, source, project_id, agent_name,
                    parent_conversation_id, nesting_depth, battle_id, winning_conversation_id,
                    not_fully_idle, killed, last_user_input_time, last_user_input_step_index,
                    app_data_dir, group_id
                ) VALUES (?, ?, ?, ?, ?, ?, 'CASCADE_RUN_STATUS_IDLE', '', ?, '', '', 0, '', '', 0, 0, ?, ?, 'antigravity', '')
                ON CONFLICT(conversation_id) DO UPDATE SET
                    title=excluded.title,
                    preview=excluded.preview,
                    step_count=excluded.step_count,
                    last_modified_time=excluded.last_modified_time,
                    last_user_input_time=excluded.last_user_input_time,
                    last_user_input_step_index=excluded.last_user_input_step_index
            """, (cid, title, prev, steps, mod_time, f'["file:///c%3A/Franck/Projets/Antigravity/{project_keyword}"]', LOCAL_PROJECT_ID, user_in_time, user_in_step))
            con_local.commit()
            print(f"    [OK] Importe en local: {title}")

    # 2. Synchroniser les conversations locales vers le Pi
    print("\n[2/3] Verification des conversations locales vers Raspberry Pi...")
    local_rows = cur_local.execute(f"""
        SELECT conversation_id, title, preview, step_count, last_modified_time,
               last_user_input_time, last_user_input_step_index
        FROM conversation_summaries
        WHERE workspace_uris LIKE '%{project_keyword}%' OR title LIKE '%{project_keyword}%'
    """).fetchall()
    
    # Verifier sur le Pi quelles conversations existent
    pi_cids = set(r[0] for r in pi_convos)
    
    for r in local_rows:
        cid, title, prev, steps, mod_time, user_in_time, user_in_step = r
        if cid not in pi_cids:
            print(f" -> Envoi vers le Pi: '{title}' ({cid})")
            # Snapshot propre pour eviter locked database
            local_src = os.path.join(LOCAL_CONVOS_DIR, f"{cid}.db")
            if os.path.exists(local_src):
                tmp_db = os.path.join(tempfile.gettempdir(), f"{cid}_snap.db")
                try:
                    c1 = sqlite3.connect(local_src)
                    c2 = sqlite3.connect(tmp_db)
                    c1.backup(c2)
                    c2.close()
                    c1.close()
                    run_cmd([PSCP, "-batch", "-pw", PI_PASS, tmp_db, f"{PI_USER}@{PI_HOST}:{PI_CONVOS_DIR}/{cid}.db"])
                finally:
                    if os.path.exists(tmp_db):
                        os.remove(tmp_db)
            
            # Copie brain
            local_brain = os.path.join(LOCAL_BRAIN_DIR, cid)
            if os.path.exists(local_brain):
                run_plink(f"mkdir -p {PI_BRAIN_DIR}/{cid}")
                run_cmd([PSCP, "-batch", "-pw", PI_PASS, "-r", f"{local_brain}/*", f"{PI_USER}@{PI_HOST}:{PI_BRAIN_DIR}/{cid}/"])
                
            # Inscription Pi db
            reg_script = f"""
import sqlite3
con = sqlite3.connect('{PI_SUMMARIES_DB}')
cur = con.cursor()
cur.execute('''
    INSERT INTO conversation_summaries (
        conversation_id, title, preview, step_count, last_modified_time,
        workspace_uris, status, source, project_id, agent_name,
        parent_conversation_id, nesting_depth, battle_id, winning_conversation_id,
        not_fully_idle, killed, last_user_input_time, last_user_input_step_index,
        app_data_dir, group_id
    ) VALUES (
        '{cid}', {json.dumps(title)}, {json.dumps(prev)}, {steps}, '{mod_time}',
        '["file:///home/raspscreen/antigravity/{project_keyword}"]', 'CASCADE_RUN_STATUS_IDLE', '',
        '{PI_PROJECT_ID}', '', '', 0, '', '', 0, 0, '{user_in_time}', {user_in_step}, 'antigravity-cli', ''
    )
    ON CONFLICT(conversation_id) DO UPDATE SET
        title=excluded.title,
        preview=excluded.preview,
        step_count=excluded.step_count,
        last_modified_time=excluded.last_modified_time,
        last_user_input_time=excluded.last_user_input_time,
        last_user_input_step_index=excluded.last_user_input_step_index
''')
con.commit()
con.close()
"""
            run_plink(f"python3 -c {json.dumps(reg_script)}")
            print(f"    [OK] Inscrit sur le Pi: {title}")

    con_local.close()
    print("\n[3/3] Synchronisation des discussions 100% terminee !")

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "RaspEcran"
    sync_conversations(kw)
