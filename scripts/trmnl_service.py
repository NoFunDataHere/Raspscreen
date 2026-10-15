#!/usr/bin/env python3
"""
Module de suivi automatique de commande TRMNL Model X pour DUCHISCREEN.
- Commande #56352 (Europe / Atelier de Berlin)
- Scraping Rails Hotwire/Turbo avec CookieJar (standard library 100%)
- Correction de rang selon le ratio d'assemblage Europe
- Règle d'expiration : disparition de la carte 5 jours après le passage en 'shipped'
"""

import os
import re
import json
import time
import math
import http.cookiejar
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATUS_FILE = DATA_DIR / "trmnl_status.json"

ORDER_NUMBER = "56352"
RATIO_EU = 334.0 / 684.0  # Ratio snapshot officiel Berlin vs Total
CACHE_TTL_SECONDS = 3600  # Mise à jour toutes les heures
MAX_EXPIRY_DAYS = 5.0     # 5 jours après expédition

def _get_utc_now():
    return datetime.now(timezone.utc)

def _parse_iso(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def fetch_berlin_status():
    """Scrape la dernière mise à jour de l'atelier de Berlin sur le blog TRMNL."""
    try:
        req = urllib.request.Request(
            "https://trmnl.com/blog/model-x-progress",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DUCHISCREEN/3.3"}
        )
        html = urllib.request.urlopen(req, timeout=10.0).read().decode("utf-8", errors="ignore")
        entries = re.findall(r"([A-Z][a-z]+ \d{1,2}\s*-\s*[^<\n]+)", html)
        berlin_updates = [re.sub(r"\s+", " ", e).strip() for e in entries if "Berlin" in e or "Germany" in e]
        return berlin_updates[-1] if berlin_updates else "Statut récent en attente"
    except Exception as e:
        return f"Indisponible ({e})"

def fetch_queue_data(order_number: str = ORDER_NUMBER):
    """Interroge le formulaire Rails Turbo de TRMNL."""
    try:
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

        init_url = f"https://trmnl.com/order-tracker?order_number={order_number}"
        req = urllib.request.Request(
            init_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DUCHISCREEN/3.3"}
        )
        html = opener.open(req, timeout=10.0).read().decode("utf-8", errors="ignore")

        m_csrf = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
        if not m_csrf:
            return None, "Jeton CSRF introuvable"

        csrf_token = m_csrf.group(1)
        post_data = urllib.parse.urlencode({
            "authenticity_token": csrf_token,
            "order_trackers[order_number]": order_number
        }).encode("utf-8")

        req2 = urllib.request.Request(
            "https://trmnl.com/order_trackers",
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DUCHISCREEN/3.3",
                "Referer": init_url
            }
        )
        res_html = opener.open(req2, timeout=10.0).read().decode("utf-8", errors="ignore")

        m_src = re.search(r'src="(/order_trackers/status\?token=[^"]+)"', res_html)
        if not m_src:
            return None, "URL de statut absente"

        status_url = "https://trmnl.com" + m_src.group(1)
        for _ in range(6):
            time.sleep(1.2)
            req_status = urllib.request.Request(
                status_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DUCHISCREEN/3.3",
                    "Referer": init_url
                }
            )
            res = opener.open(req_status, timeout=10.0).read().decode("utf-8", errors="ignore")
            if "Checking your order" not in res:
                m_text = re.search(r'<div class="ml-1 text-sm font-medium">(.*?)</div>', res, re.DOTALL)
                clean = re.sub(r"<[^>]+>", "", m_text.group(1)).strip() if m_text else res
                return " ".join(clean.split()), None

        return None, "Délai d'attente dépassé (Turbo status)"
    except Exception as e:
        return None, str(e)

def load_persisted_status():
    """Charge l'état TRMNL enregistré sur disque."""
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[TRMNL] Erreur lecture cache {STATUS_FILE}: {e}")
    return None

def save_persisted_status(data):
    """Enregistre l'état TRMNL sur disque."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[TRMNL] Erreur écriture cache {STATUS_FILE}: {e}")

def get_trmnl_status(force_refresh: bool = False):
    """
    Récupère le statut TRMNL avec mise en cache locale.
    Applique la règle de suppression automatique 5 jours après expédition.
    """
    cached = load_persisted_status()
    now = _get_utc_now()
    now_ts = now.timestamp()

    # Vérification si un rafraîchissement est nécessaire
    need_refresh = force_refresh
    if cached is None:
        need_refresh = True
    else:
        last_check_dt = _parse_iso(cached.get("last_check"))
        if last_check_dt is None or (now - last_check_dt).total_seconds() > CACHE_TTL_SECONDS:
            need_refresh = True

    if need_refresh:
        raw_text, err = fetch_queue_data(ORDER_NUMBER)
        berlin_update = fetch_berlin_status()

        if err and cached:
            # Fallback sur les données en cache
            data = cached
            data["last_error"] = err
        else:
            raw_text = raw_text or (cached.get("raw_text") if cached else "")
            is_shipped = "shipped" in (raw_text or "").lower()

            shipped_at = cached.get("shipped_at") if cached else None
            if is_shipped and not shipped_at:
                shipped_at = now.isoformat()

            pos_global = 0
            total_global = 0
            m = re.search(r"#(\d+)\s+in a queue of\s+(\d+)", raw_text or "")
            if m:
                pos_global = int(m.group(1))
                total_global = int(m.group(2))
            elif cached:
                pos_global = cached.get("pos_global", 0)
                total_global = cached.get("total_global", 0)

            pos_eu = round(pos_global * RATIO_EU) if pos_global else 0
            total_eu = round(total_global * RATIO_EU) if total_global else 0
            ahead_eu = max(0, pos_eu - 1) if pos_eu else 0
            progress_pct = round(((total_eu - pos_eu) / total_eu * 100.0), 1) if total_eu > 0 else 0.0

            history = cached.get("history", []) if cached else []
            # Enregistrer dans l'historique si nouveau ou changé
            if not history or history[-1].get("pos_global") != pos_global:
                history.append({
                    "timestamp": now.isoformat(),
                    "pos_global": pos_global,
                    "total_global": total_global,
                    "pos_eu": pos_eu
                })
                # Garder les 50 dernières entrées max
                if len(history) > 50:
                    history = history[-50:]

            data = {
                "order_number": ORDER_NUMBER,
                "is_shipped": is_shipped,
                "shipped_at": shipped_at,
                "raw_text": raw_text,
                "pos_global": pos_global,
                "total_global": total_global,
                "pos_eu": pos_eu,
                "total_eu": total_eu,
                "ahead_eu": ahead_eu,
                "progress_percent": progress_pct,
                "berlin_status": berlin_update or (cached.get("berlin_status") if cached else ""),
                "last_check": now.isoformat(),
                "history": history
            }
            save_persisted_status(data)
    else:
        data = cached

    # Application de la règle d'expiration (5 jours après expédition)
    is_shipped = data.get("is_shipped", False)
    shipped_at_dt = _parse_iso(data.get("shipped_at"))
    
    if is_shipped and shipped_at_dt:
        elapsed_days = (now - shipped_at_dt).total_seconds() / 86400.0
        if elapsed_days >= MAX_EXPIRY_DAYS:
            data["visible"] = False
            data["expired"] = True
            data["days_remaining"] = 0
        else:
            data["visible"] = True
            data["expired"] = False
            rem_days = max(1, math.ceil(MAX_EXPIRY_DAYS - elapsed_days))
            data["days_remaining"] = rem_days
    else:
        data["visible"] = True
        data["expired"] = False
        data["days_remaining"] = None

    return data

if __name__ == "__main__":
    status = get_trmnl_status(force_refresh=True)
    print(json.dumps(status, indent=2, ensure_ascii=False))
