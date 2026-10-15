#!/usr/bin/env python3
"""
RaspEcran - Backend Serveur Kiosque pour Raspberry Pi 4
DUCHISCREEN - Connecté directement à Home Assistant (ha.jokersecurity.com)
Gestionnaire de :
- Climat & Températures 6 pièces HA
- Pluie dans l'heure (Météo-France)
- Semaine A / B (basé sur le fichier Google Calendar Famille)
- Trafic temps réel (1 rue d'Arsonval ➔ Rue du Général Foy, Paris)
- Suivi Colis en Couleur (TRMNL)
- Gestion matérielle du rétroéclairage
"""

import http.server
import socketserver
import json
import os
import sys
import subprocess
import socket
import time
import datetime
import ssl
import urllib.request
import math
import gzip
from pathlib import Path
from threading import Thread, Lock
from scripts.trmnl_service import get_trmnl_status

PORT = 8080
BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
DATA_DIR = BASE_DIR / "data"
VERSION_FILE = BASE_DIR / "VERSION"
CALENDAR_FILE = DATA_DIR / "calendar.ics"

# Home Assistant Configuration
HA_URL = "https://ha.jokersecurity.com"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI0ZWZjOTJkNzM5NDM0OTBkODgwYzY3NzljNWY5OGVmNSIsImlhdCI6MTc5MTczMTI4OCwiZXhwIjoyMTA3MDkxMjg4fQ.M-k7WJQwLoclpEbxLhSb2s7dR8zp2uZrkVc4rLIUUyQ"

# Coordonnées pour Météo & Itinéraire
METEO_LAT = 48.8415
METEO_LON = 2.3117

# Trajet Domicile (1 rue d'Arsonval, 75015) ➔ Bureau (Rue du Général Foy, 75008)
TRAFFIC_FROM_LON, TRAFFIC_FROM_LAT = 2.3117, 48.8415
TRAFFIC_TO_LON, TRAFFIC_TO_LAT = 2.3168, 48.8795

# Cache mémoire thread-safe
cache_lock = Lock()
ha_cache = {
    "last_update": 0,
    "week_ab": "Semaine B",
    "temperatures": {},
    "colis": [],
    "weather": {},
    "rain_hour": {
        "status": "Temps sec la prochaine heure",
        "has_rain": False,
        "timeline": []
    },
    "traffic": {
        "duration": 18,
        "distance": "5.7 km",
        "status": "fluide",
        "label": "Trafic normal",
        "route": "Arsonval ➔ Gal Foy"
    },
    "route_alerts": {
        "has_incident": False,
        "count": 0,
        "alerts": []
    },
    "trmnl": {}
}

# Backlight paths sur Raspberry Pi OS
BACKLIGHT_POWER_PATHS = [
    Path("/sys/class/backlight/rpi_backlight/bl_power"),
    Path("/sys/class/backlight/10-0045/bl_power"),
    Path("/sys/class/backlight/soc:backlight/bl_power"),
]

BACKLIGHT_BRIGHTNESS_PATHS = [
    Path("/sys/class/backlight/rpi_backlight/brightness"),
    Path("/sys/class/backlight/10-0045/brightness"),
    Path("/sys/class/backlight/soc:backlight/brightness"),
]

def get_app_version():
    return "3.1.0"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def set_screen_brightness(level: int):
    val = f"{max(5, min(255, level))}\n"
    for path in BACKLIGHT_BRIGHTNESS_PATHS:
        if path.exists():
            try:
                path.write_text(val)
                return True
            except Exception as e:
                print(f"[Screen] Erreur luminosité sur {path}: {e}")
    return False

def set_screen_backlight(turn_off: bool):
    val = "1\n" if turn_off else "0\n"
    for path in BACKLIGHT_POWER_PATHS:
        if path.exists():
            try:
                path.write_text(val)
                return True
            except Exception as e:
                print(f"[Screen] Erreur d'écriture sur {path}: {e}")
    try:
        state = "--off" if turn_off else "--on"
        subprocess.run(["wlr-randr", "--output", "DSI-1", state], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        pass
    return False

def get_calendar_week_type():
    """Détermine si on est en Semaine A ou B à partir de l'agenda Google Famille."""
    if not CALENDAR_FILE.exists():
        # Fallback parité ISO si fichier absent
        iso_week = datetime.date.today().isocalendar()[1]
        return "Semaine A" if (iso_week % 2 == 0) else "Semaine B"
        
    try:
        events = []
        with open(CALENDAR_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            cur = {}
            for line in f:
                line = line.strip()
                if line == 'BEGIN:VEVENT':
                    cur = {}
                elif line == 'END:VEVENT':
                    summ = cur.get('SUMMARY', '')
                    if 'semaine a' in summ.lower():
                        dt = cur.get('DTSTART', '')[:8]
                        events.append((datetime.datetime.strptime(dt, '%Y%m%d').date(), 'Semaine A'))
                    elif 'semaine b' in summ.lower():
                        dt = cur.get('DTSTART', '')[:8]
                        events.append((datetime.datetime.strptime(dt, '%Y%m%d').date(), 'Semaine B'))
                elif ':' in line:
                    k, v = line.split(':', 1)
                    cur[k.split(';')[0]] = v
                    
        if not events:
            return "Semaine B"
            
        events.sort()
        today = datetime.date.today()
        current_monday = today - datetime.timedelta(days=today.weekday())
        
        # Vérifier si un événement correspond à cette semaine
        for dt, w_type in events:
            ev_monday = dt - datetime.timedelta(days=dt.weekday())
            if ev_monday == current_monday:
                return w_type
                
        # Sinon extrapoler depuis le dernier événement
        last_dt, last_type = events[-1]
        last_monday = last_dt - datetime.timedelta(days=last_dt.weekday())
        diff_weeks = (current_monday - last_monday).days // 7
        if diff_weeks % 2 == 0:
            return last_type
        else:
            return 'Semaine A' if last_type == 'Semaine B' else 'Semaine B'
    except Exception as e:
        print(f"[Calendar] Erreur analyse calendrier : {e}")
        return "Semaine B"

def calculate_traffic(by_id=None):
    """Calcule le temps de trajet réel entre 1 rue d'Arsonval et Rue du Général Foy."""
    # 1. Vérifier si Home Assistant possède déjà un capteur waze / travel_time
    if by_id:
        for eid in ["sensor.waze_travel_time", "sensor.trajet_travail", "sensor.temps_de_trajet"]:
            if eid in by_id:
                try:
                    val = round(float(by_id[eid]["state"]))
                    return {
                        "duration": val,
                        "distance": "5.7 km",
                        "status": "fluide" if val < 20 else ("ralenti" if val < 30 else "bouche"),
                        "label": "Trafic normal" if val < 20 else ("Ralentissements" if val < 30 else "Bouchons denses"),
                        "route": "Arsonval ➔ Gal Foy"
                    }
                except Exception:
                    pass

    # 2. Calcul d'itinéraire précis via OSRM + modélisation trafic heures de pointe parisiennes
    url = f"https://router.project-osrm.org/route/v1/driving/{TRAFFIC_FROM_LON},{TRAFFIC_FROM_LAT};{TRAFFIC_TO_LON},{TRAFFIC_TO_LAT}?overview=full&geometries=geojson"
    base_minutes = 16
    distance_str = "5.7 km"
    geometry = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RaspEcran/3.3"})
        with urllib.request.urlopen(req, timeout=4.0) as r:
            data = json.loads(r.read().decode())
            route = data["routes"][0]
            base_minutes = round(route["duration"] / 60)
            distance_str = f"{round(route['distance'] / 1000, 1)} km"
            raw_coords = route.get("geometry", {}).get("coordinates", [])
            geometry = [[c[1], c[0]] for c in raw_coords]
    except Exception as e:
        print(f"[Traffic] OSRM info: {e}")

    # Coefficient trafic selon l'heure à Paris (heures de pointe semaine)
    now = datetime.datetime.now()
    weekday = now.weekday() # 0 = Lundi, 6 = Dimanche
    hour = now.hour + now.minute / 60.0

    duration = base_minutes
    status = "fluide"
    label = "Circulation fluide"

    if weekday < 5: # Lundi à Vendredi
        if 7.5 <= hour <= 9.5: # 07h30 - 09h30 : Pointe matinée
            factor = 1.7 + (0.3 if 8.0 <= hour <= 9.0 else 0.1)
            duration = round(base_minutes * factor)
            status = "ralenti" if duration < 32 else "bouche"
            label = "Bouchons matinaux" if status == "bouche" else "Ralentissements matin"
        elif 17.5 <= hour <= 19.5: # 17h30 - 19h30 : Pointe soirée
            factor = 1.8
            duration = round(base_minutes * factor)
            status = "ralenti" if duration < 32 else "bouche"
            label = "Ralentissements soirée"
        elif 9.5 < hour < 17.5: # Journée
            duration = round(base_minutes * 1.25)
            status = "fluide"
            label = "Trafic modéré"
    else: # Week-end
        if 14.0 <= hour <= 19.0:
            duration = round(base_minutes * 1.2)
            status = "fluide"
            label = "Trafic week-end"

    return {
        "duration": duration,
        "distance": distance_str,
        "status": status,
        "label": label,
        "route": "Arsonval ➔ Gal Foy",
        "geometry": geometry
    }

def fetch_open_meteo():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={METEO_LAT}&longitude={METEO_LON}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m&timezone=Europe/Paris"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RaspEcran/3.1"})
        with urllib.request.urlopen(req, timeout=5.0) as r:
            data = json.loads(r.read().decode())
            cur = data.get("current", {})
            return {
                "temp": round(cur.get("temperature_2m", 18)),
                "feels": round(cur.get("apparent_temperature", 18)),
                "humidity": cur.get("relative_humidity_2m", 50),
                "wind": round(cur.get("wind_speed_10m", 10)),
                "code": cur.get("weather_code", 0)
            }
    except Exception as e:
        print(f"[Meteo] Erreur Open-Meteo: {e}")
        return None

def fetch_route_traffic_alerts(route_geometry=None):
    """
    Interroge l'API Open Data Ville de Paris (PC Lutèce - circulation_evenement)
    et filtre les perturbations ACTIVES situées sur le tracé réel du trajet
    1 rue d'Arsonval ➔ Rue du Général Foy (géométrie OSRM, couloir de 150 m).
    Repli : axe direct A➔B avec couloir de 750 m si la géométrie est absente.
    """
    from datetime import datetime, timezone, timedelta

    def point_to_segment_dist(plat, plon, lat1, lon1, lat2, lon2):
        px = (plon - lon1) * 73.0
        py = (plat - lat1) * 111.0
        dx = (lon2 - lon1) * 73.0
        dy = (lat2 - lat1) * 111.0
        seg_len_sq = dx*dx + dy*dy
        if seg_len_sq == 0:
            return math.sqrt(px*px + py*py)
        t = max(0.0, min(1.0, (px*dx + py*dy) / seg_len_sq))
        proj_x = t * dx
        proj_y = t * dy
        return math.sqrt((px - proj_x)**2 + (py - proj_y)**2)

    def point_to_polyline_dist(lat, lon, pts):
        if len(pts) == 1:
            return point_to_segment_dist(lat, lon, pts[0][0], pts[0][1], pts[0][0], pts[0][1])
        return min(point_to_segment_dist(lat, lon, pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
                   for i in range(len(pts) - 1))

    if route_geometry and len(route_geometry) >= 2:
        route_pts = [(float(p[0]), float(p[1])) for p in route_geometry]
        corridor_km = 0.15
    else:
        route_pts = [(TRAFFIC_FROM_LAT, TRAFFIC_FROM_LON), (TRAFFIC_TO_LAT, TRAFFIC_TO_LON)]
        corridor_km = 0.75

    def fetch_page(offset):
        url = ("https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
               f"circulation_evenement/records?limit=100&offset={offset}")
        req = urllib.request.Request(url, headers={"User-Agent": "RaspEcran/3.3"})
        with urllib.request.urlopen(req, timeout=8.0) as r:
            raw = r.read()
            if raw[:2] == b'\x1f\x8b':
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8", errors="ignore"))

    def is_active(rec, now):
        """Actif maintenant, ou démarrant dans les 7 prochains jours."""
        try:
            st = rec.get("starttime")
            et = rec.get("endtime")
            if st and datetime.fromisoformat(st) > now + timedelta(days=7):
                return False
            if et and datetime.fromisoformat(et) < now:
                return False
        except Exception:
            pass
        return True

    def is_upcoming(rec, now):
        try:
            st = rec.get("starttime")
            return bool(st) and datetime.fromisoformat(st) > now
        except Exception:
            return False

    try:
        first = fetch_page(0)
        results = list(first.get("results", []))
        total = int(first.get("total_count", len(results)) or 0)
        offset = 100
        while offset < total and offset < 1000:
            results.extend(fetch_page(offset).get("results", []))
            offset += 100

        now = datetime.now(timezone.utc)
        if True:
            alerts = []
            seen = set()
            for rec in results:
                if not is_active(rec, now):
                    continue
                poly = rec.get("polyline", "")
                if not poly:
                    continue
                coords = poly.split()
                ev_pts = []
                for i in range(0, len(coords)-1, 2):
                    try:
                        ev_pts.append((float(coords[i]), float(coords[i+1])))
                    except ValueError:
                        pass
                if not ev_pts:
                    continue
                # Distance minimale dans les deux sens (événement ➔ trajet, trajet ➔ événement)
                min_dist = min(point_to_polyline_dist(la, lo, route_pts) for la, lo in ev_pts)
                if len(ev_pts) >= 2 and min_dist > corridor_km:
                    min_dist = min(min_dist, min(point_to_polyline_dist(la, lo, ev_pts) for la, lo in route_pts))

                if min_dist <= corridor_km:
                    raw_type = rec.get("type", "EVENT")
                    street = rec.get("street", "Rue").replace("_", " ").strip()
                    desc = rec.get("description", "").strip()
                    key = f"{street}:{raw_type}"
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    if raw_type == "ROAD_CLOSED":
                        sev = "danger"
                        label = "Fermée"
                    elif raw_type == "CONSTRUCTION":
                        sev = "warning"
                        label = "Travaux"
                    else:
                        sev = "info"
                        label = "Manif"

                    until = ""
                    since = ""
                    try:
                        if rec.get("endtime"):
                            until = datetime.fromisoformat(rec["endtime"]).strftime("%d/%m/%Y %H:%M")
                        if rec.get("starttime"):
                            since = datetime.fromisoformat(rec["starttime"]).strftime("%d/%m")
                    except Exception:
                        pass

                    upcoming = is_upcoming(rec, now)
                    if upcoming:
                        sev = "info"
                        label = f"Dès {since}"

                    alerts.append({
                        "street": street,
                        "type": raw_type,
                        "label": label,
                        "severity": sev,
                        "desc": desc,
                        "until": until,
                        "upcoming": upcoming,
                        "dist_m": round(min_dist * 1000)
                    })

            # Actifs d'abord, puis sévérité, puis distance
            alerts.sort(key=lambda a: (1 if a["upcoming"] else 0, 0 if a["severity"] == "danger" else 1, a["dist_m"]))
            active_count = sum(1 for a in alerts if not a["upcoming"])
            return {
                "has_incident": active_count > 0,
                "count": len(alerts),
                "alerts": alerts[:12]
            }
    except Exception as e:
        print(f"[DUCHISCREEN] Erreur alertes voirie: {e}")
        return {
            "has_incident": False,
            "count": 0,
            "alerts": []
        }

def update_ha_data():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    url = f"{HA_URL}/api/states"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "HomeAssistant/RaspEcran"
    })
    
    try:
        with urllib.request.urlopen(req, timeout=8.0, context=ctx) as r:
            all_states = json.loads(r.read().decode())
            by_id = {s["entity_id"]: s for s in all_states}
            
            def get_val(eid, fallback=None):
                item = by_id.get(eid)
                if not item: return fallback
                try:
                    return float(item.get("state"))
                except (ValueError, TypeError):
                    return fallback

            # 1. Climat 6 pièces
            temps = {
                "salon": {
                    "name": "Salon",
                    "temp": get_val("sensor.bthome_sensor_b9d6_temperature", 21.8),
                    "hum": get_val("sensor.miaomiaoce_t2_b9d6_relative_humidity", 48)
                },
                "gab": {
                    "name": "Ch. Gab",
                    "temp": get_val("sensor.atc_gab_769f_temperature", 21.0),
                    "hum": get_val("sensor.atc_gab_769f_humidity", 52)
                },
                "cuisine": {
                    "name": "Cuisine",
                    "temp": get_val("sensor.atc_cuisine_b58d_temperature", 23.0),
                    "hum": get_val("sensor.atc_cuisine_b58d_humidity", 46)
                },
                "parents": {
                    "name": "Ch. Parents",
                    "temp": get_val("sensor.atc_parents_6ff6_temperature", 21.8),
                    "hum": get_val("sensor.atc_parents_6ff6_humidity", 46)
                },
                "sdb": {
                    "name": "Salle de Bain",
                    "temp": get_val("sensor.atc_sdb_8c1d_temperature", 22.0),
                    "hum": get_val("sensor.atc_sdb_8c1d_humidity", 52)
                },
                "exterieur": {
                    "name": "Extérieur",
                    "temp": get_val("sensor.outdoor_meter_95_temperature", 14.0),
                    "hum": get_val("sensor.outdoor_meter_95_humidite", 64)
                }
            }
            
            # 2. Pluie dans l'heure Météo-France
            rain_ent = by_id.get("sensor.paris_15eme_arrondissement_next_rain", {})
            forecast_raw = rain_ent.get("attributes", {}).get("1_hour_forecast", {})
            rain_timeline = []
            has_rain = False
            first_rain_min = None
            
            interval_keys = ["0 min", "5 min", "10 min", "15 min", "20 min", "25 min", "35 min", "45 min", "55 min"]
            for k in interval_keys:
                state_desc = forecast_raw.get(k, "Temps sec")
                level = 0
                desc_lower = state_desc.lower()
                if "faible" in desc_lower:
                    level = 1
                    has_rain = True
                elif "modérée" in desc_lower or "moderee" in desc_lower:
                    level = 2
                    has_rain = True
                elif "forte" in desc_lower:
                    level = 3
                    has_rain = True
                
                if level > 0 and first_rain_min is None:
                    first_rain_min = k.replace(" min", "")

                rain_timeline.append({
                    "min": k.replace(" min", ""),
                    "desc": state_desc,
                    "level": level
                })
            
            rain_status = "Temps sec la prochaine heure"
            if has_rain and first_rain_min:
                rain_status = f"Pluie prévue dans {first_rain_min} min" if first_rain_min != "0" else "Pluie en cours"

            # 3. Colis TRMNL
            colis_raw = by_id.get("sensor.trmnl_colis_tracking", {}).get("attributes", {}).get("colis", [])
            colis_cleaned = []
            for c in colis_raw:
                statut = c.get("statut", "Inconnu")
                badge = "transit"
                statut_lower = statut.lower()
                if "livraison" in statut_lower or "aujourd" in statut_lower or "out for delivery" in statut_lower:
                    badge = "delivery"
                elif "livré" in statut_lower or "delivered" in statut_lower:
                    badge = "delivered"
                elif "confirmé" in statut_lower or "ordered" in statut_lower:
                    badge = "ordered"
                else:
                    badge = "transit"

                colis_cleaned.append({
                    "nom": c.get("nom", c.get("contenu", "Colis")),
                    "contenu": c.get("contenu", ""),
                    "expediteur": c.get("expediteur", "Expéditeur"),
                    "transporteur": c.get("transporteur", "Transporteur"),
                    "numero": c.get("numero", ""),
                    "statut": statut,
                    "badge": badge,
                    "date": c.get("date_maj", ""),
                    "date_livre": c.get("date_livre", "")
                })

            # 4. Météo Open-Meteo
            meteo_cur = fetch_open_meteo()

            # 5. Semaine A / B depuis calendrier
            week_ab = get_calendar_week_type()

            # 6. Trafic temps réel (Arsonval ➔ Gal Foy)
            traffic_info = calculate_traffic(by_id)

            # 7. Alertes voirie & manifs filtrées sur l'itinéraire (OpenData Paris)
            route_alerts = fetch_route_traffic_alerts((traffic_info or {}).get("geometry"))

            # 8. Suivi Commande TRMNL Model X (#56352)
            try:
                trmnl_info = get_trmnl_status(force_refresh=False)
            except Exception as e:
                print(f"[TRMNL] Erreur statut: {e}")
                trmnl_info = {"visible": False, "error": str(e)}

            with cache_lock:
                ha_cache["last_update"] = time.time()
                ha_cache["week_ab"] = week_ab
                ha_cache["temperatures"] = temps
                ha_cache["colis"] = colis_cleaned
                ha_cache["traffic"] = traffic_info
                ha_cache["route_alerts"] = route_alerts
                ha_cache["trmnl"] = trmnl_info
                ha_cache["rain_hour"] = {
                    "status": rain_status,
                    "has_rain": has_rain,
                    "timeline": rain_timeline
                }
                if meteo_cur:
                    ha_cache["weather"] = meteo_cur

            print(f"[DUCHISCREEN] Mis à jour : {week_ab}, Trafic: {traffic_info['duration']} min ({traffic_info['status']}), Alertes trajet: {route_alerts['count']}, TRMNL EU: #{trmnl_info.get('pos_eu', '?')}.")
    except Exception as e:
        print(f"[DUCHISCREEN] Erreur Home Assistant : {e}")

def background_ha_worker():
    while True:
        update_ha_data()
        time.sleep(30)

class KioskHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/home":
            with cache_lock:
                data = dict(ha_cache)
            self.send_json(data)
        elif self.path == "/api/trmnl":
            with cache_lock:
                trmnl_data = ha_cache.get("trmnl", {})
            self.send_json(trmnl_data)
        elif self.path == "/api/version":
            self.send_json({"version": get_app_version()})
        elif self.path == "/api/system":
            self.send_json({
                "ip": get_local_ip(),
                "time": time.strftime("%H:%M:%S")
            })
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/screen/dim":
            success = set_screen_brightness(15)
            self.send_json({"status": "dimmed", "success": success})
        elif self.path == "/api/screen/sleep":
            success = set_screen_backlight(turn_off=True)
            self.send_json({"status": "sleeping", "success": success})
        elif self.path == "/api/screen/wake":
            set_screen_backlight(turn_off=False)
            success = set_screen_brightness(255)
            self.send_json({"status": "active", "success": success})
        elif self.path == "/api/refresh":
            def _full_refresh():
                update_ha_data()
                try:
                    t_data = get_trmnl_status(force_refresh=True)
                    with cache_lock:
                        ha_cache["trmnl"] = t_data
                except Exception:
                    pass
            Thread(target=_full_refresh, daemon=True).start()
            self.send_json({"status": "refreshing"})
        elif self.path == "/api/trmnl/refresh":
            def _refresh_trmnl():
                data = get_trmnl_status(force_refresh=True)
                with cache_lock:
                    ha_cache["trmnl"] = data
            Thread(target=_refresh_trmnl, daemon=True).start()
            self.send_json({"status": "refreshing_trmnl"})
        else:
            self.send_error(404, "Endpoint introuvable")

    def send_json(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        if args and len(args) >= 2 and isinstance(args[0], str) and "/api/" in args[0] and "200" in str(args[1]):
            return
        super().log_message(format, *args)

def main():
    os.chdir(str(DASHBOARD_DIR))
    DATA_DIR.mkdir(exist_ok=True)
    
    t = Thread(target=background_ha_worker, daemon=True)
    t.start()
    
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PORT), KioskHandler) as httpd:
        print(f"==================================================")
        print(f"  DUCHISCREEN v3.1 Serveur Actif !")
        print(f"  URL Locale: http://localhost:{PORT}")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nArrêt du serveur.")

if __name__ == "__main__":
    main()
