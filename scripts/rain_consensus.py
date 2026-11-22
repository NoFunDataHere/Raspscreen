#!/usr/bin/env python3
"""
Moteur de consensus multi-sources pour la pluie dans l'heure (porté de WeatherAggregator.java).
Combine en parallèle avec cache TTL différencié :
- Météo-France v3 (Pivot prioritaire 60%)
- Open-Meteo Multi-Modèles (AROME 1.3km, ICON-D2 2.2km, ECMWF 9km, ARPEGE, GFS, GEM)
- AccuWeather MinuteCast (via Home Assistant sensor.accuweather_minutecast)
- Tomorrow.io Minutely (avec filtre anti-aberrations médian)
- WeatherAPI.com
- Pirate Weather Minutely
- Meteoblue (TTL 30 min pour préserver le quota annuel)
"""

import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# Clés API issues de WeatherRainRadar (AppPreferences.java)
TOMORROW_KEY = "GdbmogWaDFbt6PCaJe9AQFNL96VjLaDu"
PIRATE_KEY = "TWBgYnwOeslWtFPGh1g3Z7Fsh9Ygnc5t"
METEOBLUE_KEY = "1fQuvF92pPNK3Db8"
WEATHERAPI_KEY = "aa3fd7990ad845af82a64711260311"

MF_TOKENS = [
    "__Wj7dVSTjV9YGu1guveLyDq0g7S7TfTjaHBTPTpO0kj8__",
    "__W3y2t--W3AjKm--W3y2t-z-sL7Sw--W3y2t__",
]

SLOT_MINUTES = [0, 5, 10, 15, 20, 25, 35, 45, 55]

_cache_lock = Lock()
_api_cache = {}


def _get_cached(key, ttl_seconds):
    with _cache_lock:
        entry = _api_cache.get(key)
        if entry and (time.time() - entry["ts"]) < ttl_seconds:
            return entry["data"]
    return None


def _set_cached(key, data):
    with _cache_lock:
        _api_cache[key] = {"ts": time.time(), "data": data}


def _http_get_json(url, headers=None, timeout=6.0):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "RaspEcran-WeatherConsensus/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _fetch_meteofrance(lat, lon):
    cached = _get_cached("mf", 300)
    if cached is not None:
        return cached
    for token in MF_TOKENS:
        try:
            url = f"https://webservice.meteofrance.com/v3/rain?lat={lat:.4f}&lon={lon:.4f}&token={token}"
            data = _http_get_json(url, {"User-Agent": "MeteoFrance/1.0 (Android)", "Accept": "application/json"})
            forecast = data.get("properties", {}).get("forecast", [])
            if not forecast:
                continue
            slots = []
            for idx, item in enumerate(forecast[:9]):
                intensity = int(item.get("rain_intensity", 1) or 1)
                desc = (item.get("rain_intensity_description") or "Temps sec").strip()
                level = max(0, min(3, intensity - 1))
                slots.append({"level": level, "desc": desc})
            res = {"ok": True, "slots": slots}
            _set_cached("mf", res)
            return res
        except Exception:
            continue
    return {"ok": False, "slots": []}


def _fetch_open_meteo(lat, lon):
    cached = _get_cached("om", 300)
    if cached is not None:
        return cached
    try:
        models = "meteofrance_arome_france_hd,meteofrance_arpege_europe,dwd_icon_d2,ecmwf_ifs025,gfs_seamless,gem_seamless"
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}"
            f"&minutely_15=precipitation&models={models}&forecast_minutely_15=6"
            f"&current=weather_code,relative_humidity_2m"
        )
        data = _http_get_json(url, {"User-Agent": "WeatherRainRadar/2.1"})
        current = data.get("current", {})
        wmo = int(current.get("weather_code", -1) or -1)
        hum = float(current.get("relative_humidity_2m", 0) or 0)
        minutely = data.get("minutely_15", {})
        res = {
            "ok": True,
            "is_drizzle": 51 <= wmo <= 57,
            "humidity": hum,
            "arome": minutely.get("precipitation_meteofrance_arome_france_hd") or [],
            "arpege": minutely.get("precipitation_meteofrance_arpege_europe") or [],
            "icon": minutely.get("precipitation_dwd_icon_d2") or [],
            "ecmwf": minutely.get("precipitation_ecmwf_ifs025") or [],
            "gfs": minutely.get("precipitation_gfs_seamless") or [],
            "gem": minutely.get("precipitation_gem_seamless") or [],
        }
        _set_cached("om", res)
        return res
    except Exception:
        return {"ok": False}


def _fetch_tomorrow(lat, lon):
    cached = _get_cached("tm", 600)
    if cached is not None:
        return cached
    try:
        url = (
            f"https://api.tomorrow.io/v4/weather/forecast?location={lat:.4f},{lon:.4f}"
            f"&timesteps=1m&units=metric&apikey={TOMORROW_KEY}"
        )
        data = _http_get_json(url, {"User-Agent": "WeatherRainRadar/2.1", "Accept": "application/json"})
        intervals = data.get("timelines", {}).get("minutely", [])
        vals = [float(it.get("values", {}).get("rainIntensity", 0) or 0) for it in intervals[:60]]
        res = {"ok": bool(vals), "minutely": vals}
        _set_cached("tm", res)
        return res
    except Exception:
        return {"ok": False, "minutely": []}


def _fetch_pirate(lat, lon):
    cached = _get_cached("pw", 480)
    if cached is not None:
        return cached
    try:
        url = f"https://api.pirateweather.net/forecast/{PIRATE_KEY}/{lat:.4f},{lon:.4f}?units=si&exclude=daily,alerts"
        data = _http_get_json(url, {"User-Agent": "WeatherRainRadar/2.1"})
        items = data.get("minutely", {}).get("data", [])
        vals = [float(it.get("precipIntensity", 0) or 0) for it in items[:60]]
        res = {"ok": bool(vals), "minutely": vals}
        _set_cached("pw", res)
        return res
    except Exception:
        return {"ok": False, "minutely": []}


def _fetch_weatherapi(lat, lon):
    cached = _get_cached("wapi", 600)
    if cached is not None:
        return cached
    try:
        url = f"https://api.weatherapi.com/v1/forecast.json?key={WEATHERAPI_KEY}&q={lat:.4f},{lon:.4f}&days=1&aqi=no&alerts=no"
        data = _http_get_json(url, {"User-Agent": "WeatherRainRadar/2.1"})
        cur = data.get("current", {})
        mm = float(cur.get("precip_mm", 0) or 0)
        cond = (cur.get("condition", {}).get("text") or "").lower()
        res = {"ok": True, "mm": mm, "is_drizzle": "drizzle" in cond or "bruine" in cond}
        _set_cached("wapi", res)
        return res
    except Exception:
        return {"ok": False, "mm": 0.0, "is_drizzle": False}


def _fetch_meteoblue(lat, lon):
    cached = _get_cached("mb", 1800)  # 30 min TTL (quota annuel 1250/an)
    if cached is not None:
        return cached
    try:
        url = f"https://my.meteoblue.com/packages/basic-1h?apikey={METEOBLUE_KEY}&lat={lat:.4f}&lon={lon:.4f}&format=json"
        data = _http_get_json(url, {"User-Agent": "WeatherRainRadar/2.1"})
        d1h = data.get("data_1h", {})
        prec = d1h.get("precipitation") or [0.0]
        prob = d1h.get("precipitation_probability") or [0]
        res = {
            "ok": True,
            "mm": float(prec[0] or 0),
            "prob": int(prob[0] or 0),
        }
        _set_cached("mb", res)
        return res
    except Exception:
        return {"ok": False, "mm": 0.0, "prob": 0}


def _avg_window(series, start_m, end_m):
    if not series:
        return 0.0
    s = max(0, start_m)
    e = min(len(series), max(s + 1, end_m))
    chunk = [float(x) for x in series[s:e] if x is not None]
    return sum(chunk) / len(chunk) if chunk else 0.0


def _sanitize_outlier(val, median_val):
    if val > 5.0 and median_val < 0.2:
        return median_val
    return val


def compute_rain_consensus(lat, lon, by_id=None):
    """Calcule le consensus pondéré multi-sources pour les 9 créneaux (0 à 55 min)."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        f_mf = pool.submit(_fetch_meteofrance, lat, lon)
        f_om = pool.submit(_fetch_open_meteo, lat, lon)
        f_tm = pool.submit(_fetch_tomorrow, lat, lon)
        f_pw = pool.submit(_fetch_pirate, lat, lon)
        f_wapi = pool.submit(_fetch_weatherapi, lat, lon)
        f_mb = pool.submit(_fetch_meteoblue, lat, lon)

        mf = f_mf.result()
        om = f_om.result()
        tm = f_tm.result()
        pw = f_pw.result()
        wapi = f_wapi.result()
        mb = f_mb.result()

    # AccuWeather MinuteCast depuis Home Assistant (si présent)
    accu_slots = []
    if by_id and "sensor.accuweather_minutecast" in by_id:
        accu_slots = by_id["sensor.accuweather_minutecast"].get("attributes", {}).get("slots", []) or []

    # Détection globale de bruine
    drizzle_signals = 0
    if om.get("ok") and om.get("is_drizzle"):
        drizzle_signals += 1
    if wapi.get("ok") and wapi.get("is_drizzle"):
        drizzle_signals += 1
    saturated_air = om.get("ok") and om.get("humidity", 0) > 92.0
    has_drizzle = drizzle_signals >= 2 or (drizzle_signals >= 1 and saturated_air)
    rain_threshold = 0.02 if has_drizzle else 0.05

    timeline = []
    has_any_rain = False
    first_rain_min = None
    first_rain_desc = None
    max_other_proba = 0.0
    active_families_max = 0

    for idx, minute_offset in enumerate(SLOT_MINUTES):
        om_idx = min(minute_offset // 15, 5)
        tranche_h = (5.0 / 60.0) if idx < 6 else (10.0 / 60.0)

        # Météo-France slot
        mf_slot = mf["slots"][idx] if (mf.get("ok") and idx < len(mf["slots"])) else None
        mf_level = mf_slot["level"] if mf_slot else 0
        mf_desc = mf_slot["desc"] if mf_slot else "Temps sec"

        # Valeurs individuelles pour filtre médian
        candidates = []
        om_arome = om["arome"][om_idx] if (om.get("ok") and om_idx < len(om.get("arome", []))) else None
        om_arpege = om["arpege"][om_idx] if (om.get("ok") and om_idx < len(om.get("arpege", []))) else None
        om_icon = om["icon"][om_idx] if (om.get("ok") and om_idx < len(om.get("icon", []))) else None
        om_ecmwf = om["ecmwf"][om_idx] if (om.get("ok") and om_idx < len(om.get("ecmwf", []))) else None
        om_gfs = om["gfs"][om_idx] if (om.get("ok") and om_idx < len(om.get("gfs", []))) else None
        om_gem = om["gem"][om_idx] if (om.get("ok") and om_idx < len(om.get("gem", []))) else None

        tm_avg = _avg_window(tm["minutely"], minute_offset - 5, minute_offset) if tm.get("ok") else None
        pw_avg = _avg_window(pw["minutely"], minute_offset - 5, minute_offset) if pw.get("ok") else None
        accu_val = None
        if accu_slots and minute_offset < len(accu_slots):
            accu_val = float(accu_slots[minute_offset].get("rain_mm", 0) or 0)

        for v in (om_arome, om_icon, om_ecmwf, om_gfs, om_gem, tm_avg, accu_val):
            if v is not None:
                candidates.append(float(v))
        if mb.get("ok"):
            candidates.append(mb["mm"])
        if wapi.get("ok"):
            candidates.append(wapi["mm"])
        slot_median = statistics.median(candidates) if candidates else 0.0

        # Pondération par familles (identique à WeatherAggregator.java)
        total_weight = 0.0
        weighted_rain = 0.0
        weighted_mm = 0.0
        families = 0

        # 1. Famille AROME / ARPEGE (Poids 2.0)
        arome_vals = [float(x) for x in (om_arome, om_arpege) if x is not None]
        if arome_vals:
            avg_a = sum(arome_vals) / len(arome_vals)
            w = 2.0
            weighted_mm += avg_a * w
            if avg_a > rain_threshold:
                weighted_rain += w
            total_weight += w
            families += 1

        # 2. Famille ICON-D2 (Poids 2.0)
        if om_icon is not None:
            v = float(om_icon)
            w = 2.0
            weighted_mm += v * w
            if v > rain_threshold:
                weighted_rain += w
            total_weight += w
            families += 1

        # 3. Famille ECMWF (Poids 1.0)
        if om_ecmwf is not None:
            v = float(om_ecmwf)
            w = 1.0
            weighted_mm += v * w
            if v > rain_threshold:
                weighted_rain += w
            total_weight += w
            families += 1

        # 4. Famille GFS + PirateWeather (Poids 0.5)
        gfs_vals = [float(x) for x in (om_gfs, pw_avg) if x is not None]
        if gfs_vals:
            avg_g = sum(gfs_vals) / len(gfs_vals)
            w = 0.5
            weighted_mm += avg_g * w
            if avg_g > rain_threshold:
                weighted_rain += w
            total_weight += w
            families += 1

        # 5. Famille GEM (Poids 0.5)
        if om_gem is not None:
            v = float(om_gem)
            w = 0.5
            weighted_mm += v * w
            if v > rain_threshold:
                weighted_rain += w
            total_weight += w
            families += 1

        # 6. AccuWeather MinuteCast (Poids 1.5)
        if accu_val is not None:
            w = 1.5
            weighted_mm += accu_val * w
            if accu_val > rain_threshold:
                weighted_rain += w
            total_weight += w
            families += 1

        # 7. Tomorrow.io (Poids 1.5 + filtre anti-aberration)
        if tm_avg is not None:
            clean_tm = _sanitize_outlier(tm_avg, slot_median)
            w = 1.5
            weighted_mm += clean_tm * w
            if clean_tm > rain_threshold:
                weighted_rain += w
            total_weight += w
            families += 1

        # 8. Meteoblue (Poids 1.0)
        if mb.get("ok"):
            w = 1.0
            weighted_mm += mb["mm"] * w
            if mb["mm"] > rain_threshold or mb["prob"] >= 40:
                weighted_rain += w
            total_weight += w
            families += 1

        # 9. WeatherAPI (Poids 1.0)
        if wapi.get("ok"):
            w = 1.0
            weighted_mm += wapi["mm"] * w
            if wapi["mm"] > rain_threshold:
                weighted_rain += w
            total_weight += w
            families += 1

        active_families_max = max(active_families_max, families)
        conf_proba = (weighted_rain / total_weight) if total_weight > 0 else 0.0
        avg_mm = (weighted_mm / total_weight) if total_weight > 0 else 0.0
        max_other_proba = max(max_other_proba, conf_proba)

        # Pondération finale : 60% Météo-France + 40% Modèles si MF dispo, sinon 100% Modèles
        mf_rate = {0: 0.0, 1: 1.5, 2: 5.0, 3: 14.0}.get(mf_level, 0.0)
        if mf.get("ok"):
            combined_rate = (mf_rate * 0.6) + (avg_mm * 0.4)
            is_slot_rain = (mf_level > 0 and conf_proba >= 0.15) or (mf_level > 0 and mf_rate >= 1.5) or (conf_proba >= 0.45 and avg_mm >= 0.08)
        else:
            combined_rate = avg_mm
            is_slot_rain = (conf_proba >= 0.35 and avg_mm >= 0.05)

        if not is_slot_rain:
            slot_level = 0
            slot_desc = "Temps sec"
        else:
            if combined_rate >= 7.0 or mf_level == 3:
                slot_level = 3
                slot_desc = "Pluie forte"
            elif combined_rate >= 2.5 or mf_level == 2:
                slot_level = 2
                slot_desc = "Pluie modérée"
            else:
                slot_level = 1
                slot_desc = mf_desc if mf_level > 0 else "Pluie faible"

            has_any_rain = True
            if first_rain_min is None:
                first_rain_min = str(minute_offset)
                first_rain_desc = slot_desc

        timeline.append({
            "min": str(minute_offset),
            "desc": f"{slot_desc} ({round(conf_proba * 100)}% modèles)",
            "level": slot_level,
            "proba": round(conf_proba * 100),
            "mm_h": round(combined_rate * tranche_h * 12, 2),
        })

    # Score de consensus global affiché
    mf_max_lvl = max((s["level"] for s in mf.get("slots", [])), default=0)
    mf_score = (mf_max_lvl * 33.3) if mf_max_lvl > 0 else 0.0
    if mf.get("ok"):
        global_prob = round((mf_score * 0.6) + ((max_other_proba * 100.0) * 0.4))
    else:
        global_prob = round(max_other_proba * 100.0)
    global_prob = max(0, min(100, global_prob))

    total_sources = active_families_max + (1 if mf.get("ok") else 0)
    if has_any_rain and first_rain_min is not None:
        if first_rain_min == "0":
            status = f"{first_rain_desc} en cours • Consensus {global_prob}% ({total_sources} sources)"
        else:
            status = f"Pluie dans {first_rain_min} min • Consensus {global_prob}% ({total_sources} sources)"
    else:
        dry_conf = max(0, 100 - global_prob)
        status = f"Temps sec • Consensus {dry_conf}% ({total_sources} sources)"

    return {
        "status": status,
        "has_rain": has_any_rain,
        "timeline": timeline,
        "consensus_percent": global_prob,
        "sources_count": total_sources,
    }
