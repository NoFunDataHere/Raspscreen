/* ==========================================================
   DUCHISCREEN - Dashboard Controller
   Home Assistant, Météo-France Pluie 1h, Trafic, Fiat 500 & Chats
   ========================================================== */

const CONFIG = {
    DIM_TIMEOUT_SECONDS: 60,     // 1 min : Atténuation
    SLEEP_TIMEOUT_SECONDS: 120,  // 2 min : Veille complète
    REFRESH_INTERVAL: 15000,     // 15 sec : Rafraîchissement des données HA
    FLIP_INTERVAL: 15000         // 15 sec : Alternance Trafic / Chat
};

let idleSeconds = 0;
let isDimmed = false;
let isSleeping = false;
let isCatShowing = false;
let catIndex = 0;
const TOTAL_CATS = 7;

// DOM Elements
const digitalClock = document.getElementById('digitalClock');
const calendarDate = document.getElementById('calendarDate');
const weekBadge = document.getElementById('weekBadge');
const idleTimer = document.getElementById('idleTimer');
const screenSleepOverlay = document.getElementById('screenSleepOverlay');
const kioskContainer = document.getElementById('kioskContainer');
const btnRefresh = document.getElementById('btnRefresh');
const btnSleep = document.getElementById('btnSleep');
const lastSyncTime = document.getElementById('lastSyncTime');

// Weather Elements
const weatherTemp = document.getElementById('weatherTemp');
const weatherDesc = document.getElementById('weatherDesc');
const weatherFeels = document.getElementById('weatherFeels');
const weatherWind = document.getElementById('weatherWind');
const weatherHum = document.getElementById('weatherHum');

// Rain Elements
const rainStatusText = document.getElementById('rainStatusText');
const rainTimeline = document.getElementById('rainTimeline');

// Traffic & Cat Elements
const flipperSlot = document.getElementById('flipperSlot');
const cardTraffic = document.getElementById('cardTraffic');
const cardCat = document.getElementById('cardCat');
const catImg = document.getElementById('catImg');
const trafficMinutes = document.getElementById('trafficMinutes');
const trafficRoute = document.getElementById('trafficRoute');
const trafficState = document.getElementById('trafficState');
const trafficBadge = document.getElementById('trafficBadge');

// Rooms Elements
const roomIds = ['salon', 'gab', 'cuisine', 'parents', 'sdb', 'exterieur'];

// Colis Elements
const colisList = document.getElementById('colisList');
const colisCount = document.getElementById('colisCount');
const btnScrollColisUp = document.getElementById('btnScrollColisUp');
const btnScrollColisDown = document.getElementById('btnScrollColisDown');

// Route Alerts Elements
const routeAlertsList = document.getElementById('routeAlertsList');
const routeAlertsCard = document.querySelector('.route-alerts-card');
const routeAlertsModal = document.getElementById('routeAlertsModal');
const btnCloseAlertsModal = document.getElementById('btnCloseAlertsModal');
const modalAlertsList = document.getElementById('modalAlertsList');
const modalAlertsCount = document.getElementById('modalAlertsCount');

// Map variables
let routeMap = null;
let routePolyline = null;

/* -------------------------------------------------------------------------- */
/* 1. Horloge & Date                                                          */
/* -------------------------------------------------------------------------- */
function updateClock() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    digitalClock.textContent = `${hours}:${minutes}`;
    
    const options = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
    calendarDate.textContent = now.toLocaleDateString('fr-FR', options);
}

/* -------------------------------------------------------------------------- */
/* 2. Alternance Trafic / Chat (Flipper)                                      */
/* -------------------------------------------------------------------------- */
function toggleFlipper() {
    isCatShowing = !isCatShowing;
    if (isCatShowing) {
        catIndex = (catIndex + 1) % TOTAL_CATS;
        const newSrc = `assets/cats/cat${catIndex + 1}.jpg`;
        catImg.src = newSrc;
        const catBg = document.getElementById('catBgBlur');
        if (catBg) catBg.style.backgroundImage = `url('${newSrc}')`;
        cardTraffic.classList.add('hidden');
        cardCat.classList.remove('hidden');
    } else {
        cardCat.classList.add('hidden');
        cardTraffic.classList.remove('hidden');
        if (routeMap) {
            setTimeout(() => routeMap.invalidateSize(), 50);
        }
    }
}

if (flipperSlot) {
    flipperSlot.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleFlipper();
    });
}

setInterval(toggleFlipper, CONFIG.FLIP_INTERVAL);

/* -------------------------------------------------------------------------- */
/* 3. Gestion de l'inactivité tactile                                         */
/* -------------------------------------------------------------------------- */
function resetIdleTimer() {
    idleSeconds = 0;
    if (isDimmed || isSleeping) {
        wakeScreen();
    }
}

let wasInMorningWindow = false;

function isMorningWakeWindow() {
    const now = new Date();
    const day = now.getDay(); // 1 (Lun) .. 5 (Ven)
    if (day < 1 || day > 5) return false;
    const mins = now.getHours() * 60 + now.getMinutes();
    return mins >= (7 * 60 + 45) && mins < (8 * 60 + 15);
}

function updateIdleCountdown() {
    if (isMorningWakeWindow()) {
        if (!wasInMorningWindow) {
            wasInMorningWindow = true;
            if (isSleeping || isDimmed) {
                wakeScreen();
            }
        }
        idleSeconds = 0;
        idleTimer.textContent = "Réveil 07h45-08h15";
        return;
    } else if (wasInMorningWindow) {
        wasInMorningWindow = false;
        idleSeconds = 0;
    }

    idleSeconds++;
    
    if (idleSeconds >= CONFIG.DIM_TIMEOUT_SECONDS && !isDimmed && !isSleeping) {
        triggerDim();
    }
    if (idleSeconds >= CONFIG.SLEEP_TIMEOUT_SECONDS && !isSleeping) {
        triggerSleep();
    }
    
    let nextStageSeconds = CONFIG.DIM_TIMEOUT_SECONDS - idleSeconds;
    let label = "Dim";
    if (idleSeconds >= CONFIG.DIM_TIMEOUT_SECONDS) {
        nextStageSeconds = CONFIG.SLEEP_TIMEOUT_SECONDS - idleSeconds;
        label = "Veille";
    }
    
    if (nextStageSeconds < 0) nextStageSeconds = 0;
    const mins = Math.floor(nextStageSeconds / 60);
    const secs = nextStageSeconds % 60;
    idleTimer.textContent = `${label} dans ${mins}:${String(secs).padStart(2, '0')}`;
}

async function triggerDim() {
    isDimmed = true;
    kioskContainer.classList.add('dimmed');
    try { await fetch('/api/screen/dim', { method: 'POST' }); } catch (e) {}
}

async function triggerSleep() {
    isSleeping = true;
    screenSleepOverlay.classList.add('active');
    try { await fetch('/api/screen/sleep', { method: 'POST' }); } catch (e) {}
}

async function wakeScreen() {
    idleSeconds = 0;
    isDimmed = false;
    isSleeping = false;
    kioskContainer.classList.remove('dimmed');
    screenSleepOverlay.classList.remove('active');
    try { await fetch('/api/screen/wake', { method: 'POST' }); } catch (e) {}
}

function handleUserActivity() {
    resetIdleTimer();
}

['touchstart', 'touchend', 'touchmove', 'pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'keydown'].forEach(evt => {
    window.addEventListener(evt, handleUserActivity, { passive: true });
});

function handleOverlayWake(e) {
    if (e && typeof e.stopPropagation === 'function') {
        e.stopPropagation();
    }
    resetIdleTimer();
    wakeScreen();
}

['pointerdown', 'touchstart', 'mousedown', 'click'].forEach(evt => {
    screenSleepOverlay.addEventListener(evt, handleOverlayWake, { passive: true });
});

btnSleep.addEventListener('click', (e) => {
    e.stopPropagation();
    triggerSleep();
});

btnRefresh.addEventListener('click', async (e) => {
    e.stopPropagation();
    btnRefresh.style.transform = 'rotate(180deg)';
    try {
        await fetch('/api/refresh', { method: 'POST' });
        setTimeout(fetchData, 800);
    } catch (err) {}
    setTimeout(() => { btnRefresh.style.transform = ''; }, 600);
});

/* -------------------------------------------------------------------------- */
/* 4. Conditions Météo WMO                                                    */
/* -------------------------------------------------------------------------- */
const WMO_MAP = {
    0: "Ensoleillé",
    1: "Peu nuageux",
    2: "Partiellement couvert",
    3: "Couvert",
    45: "Brouillard",
    48: "Brouillard givrant",
    51: "Bruine légère",
    61: "Pluie faible",
    63: "Pluie modérée",
    65: "Forte pluie",
    71: "Neige",
    80: "Averses",
    95: "Orage"
};

/* -------------------------------------------------------------------------- */
/* 5. Récupération & Rendu des Données Home Assistant                         */
/* -------------------------------------------------------------------------- */
async function fetchData() {
    try {
        const res = await fetch('/api/home');
        if (!res.ok) throw new Error("Erreur API Home");
        const data = await res.json();

        if (data.force_awake && (isSleeping || isDimmed)) {
            wakeScreen();
        }
        if (data.week_ab) {
            weekBadge.textContent = data.week_ab;
        }
        
        renderWeather(data.weather);
        renderRain(data.rain_hour, data.weather);
        renderTraffic(data.traffic);
        renderRouteAlerts(data.route_alerts);
        renderTemperatures(data.temperatures);
        renderColis(data.colis);
        
        const now = new Date();
        lastSyncTime.textContent = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
        
        const footerIp = document.getElementById('footerIp');
        if (footerIp && data.system_ip) {
            if (data.tailscale_ip) {
                footerIp.textContent = `${data.system_ip} • TS ${data.tailscale_ip}`;
                footerIp.title = `LAN: ${data.system_ip} | Tailscale: ${data.tailscale_ip}`;
            } else {
                footerIp.textContent = data.system_ip;
                footerIp.title = `LAN: ${data.system_ip}`;
            }
        }
    } catch (e) {
        console.error("Erreur actualisation :", e);
    }
}

function renderWeather(cur) {
    if (cur && cur.temp !== undefined) {
        weatherTemp.textContent = cur.temp;
        weatherFeels.textContent = `${cur.feels}°`;
        weatherWind.textContent = `${cur.wind} km/h`;
        weatherHum.textContent = `${cur.humidity}%`;
        weatherDesc.textContent = WMO_MAP[cur.code] || "Variable";
    }
}

let latestRainData = null;
let latestWeatherData = null;

function renderRainSegments(segsEl, timeline) {
    if (!segsEl) return;
    segsEl.innerHTML = '';
    timeline.forEach((item, idx) => {
        const seg = document.createElement('div');
        const lvl = item.level || 0;
        seg.className = `rain-seg lvl-${lvl}`;
        const trancheH = idx < 6 ? (5 / 60) : (10 / 60);
        const slotMm = (item.mm_h || 0) * trancheH;
        seg.textContent = lvl > 0 ? Math.max(0.1, slotMm).toFixed(1).replace('.', ',') : '0';
        seg.style.flex = idx < 6 ? '1' : '1.45';
        seg.title = `${item.min}m : ${item.desc}`;
        segsEl.appendChild(seg);
    });
}

function renderRainDialSvg(dialSvg, rain, weather) {
    if (!dialSvg || !rain) return;

    const totalMm = Number(rain.total_mm || 0);
    const riskPct = Number(rain.consensus_percent || 0);
    const timeline = rain.timeline || [];

    const minuteLevels = new Array(60).fill(0);
    for (let m = 0; m < 60; m++) {
        let lvl = 0;
        for (let i = 0; i < timeline.length; i++) {
            const slotMin = parseInt(timeline[i].min || '0', 10);
            const nextMin = (i + 1 < timeline.length) ? parseInt(timeline[i + 1].min || '60', 10) : 60;
            if (m >= slotMin && m < nextMin) {
                lvl = timeline[i].level || 0;
                break;
            }
        }
        minuteLevels[m] = lvl;
    }

    const colors = ['#10b981', '#38bdf8', '#f59e0b', '#ef4444'];
    const cx = 110, cy = 110;
    const innerRingR = 66;

    let barsHtml = `<circle cx="${cx}" cy="${cy}" r="${innerRingR}" fill="none" stroke="#334155" stroke-width="1.5" />`;
    for (let m = 0; m < 60; m++) {
        const lvl = minuteLevels[m];
        const isCardinal = (m % 15 === 0);
        const angleRad = ((m / 60) * 360 - 90) * (Math.PI / 180);
        const r1 = isCardinal ? innerRingR - 2 : innerRingR + 3;
        const r2 = (isCardinal ? 82 : 78) + (lvl * 2.5);
        const x1 = (cx + r1 * Math.cos(angleRad)).toFixed(1);
        const y1 = (cy + r1 * Math.sin(angleRad)).toFixed(1);
        const x2 = (cx + r2 * Math.cos(angleRad)).toFixed(1);
        const y2 = (cy + r2 * Math.sin(angleRad)).toFixed(1);
        const strokeW = isCardinal ? 4.2 : (lvl > 0 ? 2.6 : 2.2);
        barsHtml += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${colors[lvl]}" stroke-width="${strokeW}" stroke-linecap="round" opacity="${lvl > 0 || isCardinal ? 1 : 0.78}" />`;
    }

    const tickLabels = [
        { m: 0, txt: 'MAINTENANT', r: 97, size: 8.5, fill: '#e2e8f0', bold: 700 },
        { m: 5, txt: '5m', r: 95, size: 7.5, fill: '#94a3b8', bold: 600 },
        { m: 10, txt: '10m', r: 96, size: 7.5, fill: '#94a3b8', bold: 600 },
        { m: 15, txt: '+15m', r: 98, size: 8.2, fill: '#cbd5e1', bold: 700 },
        { m: 20, txt: '20m', r: 96, size: 7.5, fill: '#94a3b8', bold: 600 },
        { m: 25, txt: '25m', r: 95, size: 7.5, fill: '#94a3b8', bold: 600 },
        { m: 30, txt: '+30m', r: 98, size: 8.2, fill: '#cbd5e1', bold: 700 },
        { m: 35, txt: '35m', r: 95, size: 7.5, fill: '#94a3b8', bold: 600 },
        { m: 40, txt: '40m', r: 96, size: 7.5, fill: '#94a3b8', bold: 600 },
        { m: 45, txt: '+45m', r: 98, size: 8.2, fill: '#cbd5e1', bold: 700 },
        { m: 50, txt: '50m', r: 96, size: 7.5, fill: '#94a3b8', bold: 600 },
        { m: 55, txt: '55m', r: 95, size: 7.5, fill: '#94a3b8', bold: 600 },
    ];
    let labelsHtml = '';
    tickLabels.forEach(t => {
        const rad = ((t.m / 60) * 360 - 90) * (Math.PI / 180);
        const lx = (cx + t.r * Math.cos(rad)).toFixed(1);
        const ly = (cy + t.r * Math.sin(rad) + 3).toFixed(1);
        labelsHtml += `<text x="${lx}" y="${ly}" text-anchor="middle" fill="${t.fill}" font-size="${t.size}" font-weight="${t.bold}">${t.txt}</text>`;
    });

    const maxLevel = Math.max(0, ...minuteLevels);
    const centerColor = colors[maxLevel] || '#10b981';
    const tempVal = (weather && weather.temp !== undefined) ? `${Math.round(weather.temp)}°` : (weatherTemp ? `${weatherTemp.textContent}°` : '--°');
    const centerLabel = maxLevel === 0 ? 'TEMPS SEC' : (maxLevel === 1 ? 'PLUIE EN COURS' : (maxLevel === 2 ? 'PLUIE MODÉRÉE' : 'PLUIE FORTE'));

    const nowDt = new Date(Date.now() + 60 * 60000);
    const endHH = `${String(nowDt.getHours()).padStart(2, '0')}:${String(nowDt.getMinutes()).padStart(2, '0')}`;
    let subLabel = 'Temps sec sur 60 min';
    if (maxLevel > 0) {
        const dryAfter = minuteLevels.slice(1).findIndex(l => l === 0);
        if (minuteLevels[0] > 0 && dryAfter === -1) {
            subLabel = `Fin après ${endHH} (> 1h)`;
        } else if (minuteLevels[0] > 0 && dryAfter > 0) {
            subLabel = `Fin dans ~${dryAfter + 1} min`;
        } else {
            const firstIdx = minuteLevels.findIndex(l => l > 0);
            subLabel = firstIdx >= 0 ? `Début dans ~${firstIdx} min` : 'Averse prévue';
        }
    }

    const centerIcon = maxLevel === 0
        ? `<circle cx="110" cy="69" r="7" fill="#fbbf24" stroke="#f59e0b" stroke-width="1.5"/><g stroke="#fbbf24" stroke-width="1.5" stroke-linecap="round"><line x1="110" y1="57" x2="110" y2="60"/><line x1="110" y1="78" x2="110" y2="81"/><line x1="98" y1="69" x2="101" y2="69"/><line x1="119" y1="69" x2="122" y2="69"/></g>`
        : `<path d="M98 73h22a5 5 0 0 0 .8-9.9 7 7 0 0 0-13.5-1.8 5.5 5.5 0 0 0-9.3 11.7z" fill="#e2e8f0"/><line x1="103" y1="77" x2="101.5" y2="81.5" stroke="${centerColor}" stroke-width="1.8" stroke-linecap="round"/><line x1="109" y1="77" x2="107.5" y2="81.5" stroke="${centerColor}" stroke-width="1.8" stroke-linecap="round"/><line x1="115" y1="77" x2="113.5" y2="81.5" stroke="${centerColor}" stroke-width="1.8" stroke-linecap="round"/>`;

    dialSvg.innerHTML = `
        ${barsHtml}
        ${labelsHtml}
        ${centerIcon}
        <text x="110" y="106" text-anchor="middle" fill="#f8fafc" font-size="22" font-weight="800">${tempVal}</text>
        <text x="110" y="121" text-anchor="middle" fill="${centerColor}" font-size="9.5" font-weight="800" letter-spacing="0.03em">${centerLabel}</text>
        <text x="110" y="133" text-anchor="middle" fill="#38bdf8" font-size="7.8" font-weight="600">${subLabel}</text>
        <text x="110" y="145" text-anchor="middle" fill="#94a3b8" font-size="7.2" font-weight="600">Épisode ~${totalMm.toFixed(1).replace('.', ',')} mm • Risque ${riskPct}%</text>
    `;
}

function renderRainModal(rain, weather) {
    if (!rain) return;
    const statusEl = document.getElementById('rainModalStatus');
    const subEl = document.getElementById('rainModalSubtitle');
    const mmEl = document.getElementById('rainModalTotalMm');
    const riskEl = document.getElementById('rainModalRiskPct');
    const segsEl = document.getElementById('rainModalSegments');
    const dialSvg = document.getElementById('rainModalDialSvg');
    const slotsEl = document.getElementById('rainModalSlots');

    const totalMm = Number(rain.total_mm || 0);
    const riskPct = Number(rain.consensus_percent || 0);
    const count = rain.sources_count || 0;

    if (statusEl) statusEl.textContent = rain.status || "Temps sec la prochaine heure";
    if (subEl) subEl.textContent = `Consensus pondéré multi-sources (${count} sources actives)`;
    if (mmEl) mmEl.textContent = `${totalMm.toFixed(1).replace('.', ',')} mm`;
    if (riskEl) {
        riskEl.textContent = `${riskPct}%`;
        riskEl.className = 'rain-metric-val ' + (riskPct >= 65 ? 'red' : (riskPct >= 40 ? 'orange' : (riskPct >= 20 ? 'blue' : 'green')));
    }

    renderRainSegments(segsEl, rain.timeline || []);
    renderRainDialSvg(dialSvg, rain, weather);

    if (slotsEl) {
        slotsEl.innerHTML = (rain.timeline || []).map(item => `
            <div class="rain-modal-slot-item">
                <strong>+${item.min} min</strong>
                <span>${escapeHtml(item.desc || 'Temps sec')}</span>
            </div>
        `).join('');
    }
}

function renderRain(rain, weather) {
    if (!rain) return;
    latestRainData = rain;
    latestWeatherData = weather;

    rainStatusText.textContent = rain.status || "Temps sec la prochaine heure";

    const sourcesBadge = document.getElementById('rainSourcesBadge');
    if (sourcesBadge) {
        const count = rain.sources_count || 0;
        sourcesBadge.textContent = count > 0 ? `${count} sources` : 'Consensus';
    }

    const totalMmEl = document.getElementById('rainTotalMm');
    const totalMm = Number(rain.total_mm || 0);
    if (totalMmEl) {
        totalMmEl.textContent = `${totalMm.toFixed(1).replace('.', ',')} mm`;
    }

    const riskEl = document.getElementById('rainRiskPct');
    const riskPct = Number(rain.consensus_percent || 0);
    if (riskEl) {
        riskEl.textContent = `${riskPct}%`;
        riskEl.className = 'rain-metric-val ' + (riskPct >= 65 ? 'red' : (riskPct >= 40 ? 'orange' : (riskPct >= 20 ? 'blue' : 'green')));
    }

    renderRainSegments(document.getElementById('rainSegments'), rain.timeline || []);
    renderRainDialSvg(document.getElementById('rainDialSvg'), rain, weather);

    const rainModal = document.getElementById('rainModal');
    if (rainModal && !rainModal.classList.contains('hidden')) {
        renderRainModal(rain, weather);
    }
}

const rainCardEl = document.getElementById('rainCard');
const rainModalEl = document.getElementById('rainModal');
const btnCloseRainModal = document.getElementById('btnCloseRainModal');

if (rainCardEl && rainModalEl) {
    rainCardEl.addEventListener('click', (e) => {
        e.stopPropagation();
        if (latestRainData) {
            renderRainModal(latestRainData, latestWeatherData);
        }
        rainModalEl.classList.remove('hidden');
    });
}
if (btnCloseRainModal && rainModalEl) {
    btnCloseRainModal.addEventListener('click', (e) => {
        e.stopPropagation();
        rainModalEl.classList.add('hidden');
    });
}
if (rainModalEl) {
    rainModalEl.addEventListener('click', (e) => {
        if (e.target === rainModalEl) {
            rainModalEl.classList.add('hidden');
        }
    });
}

function renderTraffic(traffic) {
    if (!traffic) return;
    
    trafficMinutes.textContent = traffic.duration || 18;
    trafficRoute.textContent = traffic.route || "Arsonval ➔ Gal Foy";
    trafficState.textContent = traffic.label || "Trafic normal";
    
    trafficBadge.className = `badge badge-traffic ${traffic.status === 'ralenti' ? 'orange' : (traffic.status === 'bouche' ? 'red' : '')}`;
    trafficBadge.textContent = traffic.status === 'ralenti' ? 'Ralenti' : (traffic.status === 'bouche' ? 'Bouché' : 'Fluide');

    if (traffic.geometry && traffic.geometry.length > 0) {
        updateRouteMapGeometry(traffic.geometry);
    }
    if (routeMap) {
        setTimeout(() => routeMap.invalidateSize(), 200);
    }
}

function initRouteMap() {
    const mapEl = document.getElementById('routeMap');
    if (!mapEl || typeof L === 'undefined') return;
    
    try {
        routeMap = L.map('routeMap', {
            center: [48.8605, 2.3142],
            zoom: 12.5,
            zoomControl: false,
            attributionControl: false,
            dragging: false,
            touchZoom: false,
            scrollWheelZoom: false,
            doubleClickZoom: false,
            boxZoom: false,
            keyboard: false
        });

        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 16
        }).addTo(routeMap);

        // Point de départ (1 rue d'Arsonval, 75015)
        L.circleMarker([48.8415, 2.3117], {
            radius: 5,
            color: '#10b981',
            fillColor: '#10b981',
            fillOpacity: 1,
            weight: 2
        }).addTo(routeMap);

        // Point d'arrivée (Rue du Général Foy, 75008)
        L.circleMarker([48.8795, 2.3168], {
            radius: 5,
            color: '#ef4444',
            fillColor: '#ef4444',
            fillOpacity: 1,
            weight: 2
        }).addTo(routeMap);
    } catch (e) {
        console.warn("Leaflet map init:", e);
    }
}

function updateRouteMapGeometry(geometry) {
    if (!routeMap || typeof L === 'undefined') return;
    try {
        if (routePolyline) {
            routeMap.removeLayer(routePolyline);
        }
        if (geometry && geometry.length > 0) {
            routePolyline = L.polyline(geometry, {
                color: '#00f2fe',
                weight: 3.5,
                opacity: 0.9,
                lineJoin: 'round'
            }).addTo(routeMap);
            routeMap.fitBounds(routePolyline.getBounds(), { padding: [22, 22] });
        }
    } catch (e) {
        console.warn("Update geometry:", e);
    }
}

function openAlertsModal() {
    if (routeAlertsModal) {
        routeAlertsModal.classList.remove('hidden');
    }
}

function closeAlertsModal() {
    if (routeAlertsModal) {
        routeAlertsModal.classList.add('hidden');
    }
}

if (routeAlertsCard) {
    routeAlertsCard.addEventListener('click', (e) => {
        e.stopPropagation();
        openAlertsModal();
    });
}

if (btnCloseAlertsModal) {
    btnCloseAlertsModal.addEventListener('click', (e) => {
        e.stopPropagation();
        closeAlertsModal();
    });
}

if (routeAlertsModal) {
    routeAlertsModal.addEventListener('click', (e) => {
        if (e.target === routeAlertsModal) {
            closeAlertsModal();
        }
    });
}

function renderTemperatures(temps) {
    if (!temps) return;
    
    roomIds.forEach(id => {
        const r = temps[id];
        if (r) {
            const tempEl = document.getElementById(`temp-${id}`);
            const humEl = document.getElementById(`hum-${id}`);
            if (tempEl && r.temp !== null) tempEl.textContent = Number(r.temp).toFixed(1);
            if (humEl && r.hum !== null) humEl.textContent = `${Math.round(r.hum)}%`;
        }
    });
}

const COLIS_BADGE_LABELS = {
    "delivery": "En livraison",
    "transit": "En transit",
    "ordered": "Confirmé",
    "delivered": "Livré"
};

function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}

function formatDateLivre(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
}

function openColisModal(c) {
    const modal = document.getElementById('colisModal');
    if (!modal) return;
    const badgeClass = `badge-${c.badge || 'transit'}`;
    const badgeLabel = COLIS_BADGE_LABELS[c.badge] || c.statut;
    document.getElementById('colisModalTitle').textContent = c.contenu || c.nom || 'Colis';
    document.getElementById('colisModalSubtitle').textContent = `${c.expediteur || ''}${c.transporteur ? ' • ' + c.transporteur : ''}`;

    const rows = [
        ['Statut', `<span class="colis-status-badge ${badgeClass}" style="font-size:0.75rem; padding:3px 8px;">${escapeHtml(badgeLabel)}</span>`],
        ['Détail du suivi', escapeHtml(c.statut || '—')],
        ['Expéditeur', escapeHtml(c.expediteur || '—')],
        ['Transporteur', escapeHtml(c.transporteur || '—')],
        ['N° de suivi / commande', c.numero ? `<span class="colis-detail-mono">${escapeHtml(c.numero)}</span>` : '—'],
        ['Dernière mise à jour', escapeHtml(c.date || '—')]
    ];
    if (c.date_livre) rows.push(['Livré le', escapeHtml(formatDateLivre(c.date_livre))]);

    document.getElementById('colisModalBody').innerHTML = rows.map(([k, v]) => `
        <div class="colis-detail-row">
            <span class="colis-detail-label">${k}</span>
            <span class="colis-detail-value">${v}</span>
        </div>`).join('');
    modal.classList.remove('hidden');
}

function closeColisModal() {
    const modal = document.getElementById('colisModal');
    if (modal) modal.classList.add('hidden');
}

(function bindColisModal() {
    const modal = document.getElementById('colisModal');
    const btn = document.getElementById('btnCloseColisModal');
    if (btn) btn.addEventListener('click', (e) => { e.stopPropagation(); closeColisModal(); });
    if (modal) modal.addEventListener('click', (e) => { if (e.target === modal) closeColisModal(); });
})();

// Contrôles de défilement manuel de la liste des colis
(function bindColisScrollControls() {
    if (btnScrollColisUp && colisList) {
        btnScrollColisUp.addEventListener('click', (e) => {
            e.stopPropagation();
            colisList.scrollBy({ top: -90, behavior: 'smooth' });
        });
    }
    if (btnScrollColisDown && colisList) {
        btnScrollColisDown.addEventListener('click', (e) => {
            e.stopPropagation();
            colisList.scrollBy({ top: 90, behavior: 'smooth' });
        });
    }
})();

function renderColis(colis) {
    if (!colis) return;
    
    colisCount.textContent = `${colis.length} actif${colis.length > 1 ? 's' : ''}`;
    colisList.innerHTML = '';
    
    if (colis.length === 0) {
        colisList.innerHTML = `
            <div class="colis-empty-state">
                <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="colis-empty-icon">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                    <polyline points="3.29 7 12 12 20.71 7"/>
                    <line x1="12" y1="22" x2="12" y2="12"/>
                    <path d="m9 12 2 2 4-4" stroke="#10b981" stroke-width="2.2"/>
                </svg>
                <div class="colis-empty-title">Tous les colis sont arrivés</div>
                <div class="colis-empty-subtitle">Aucune livraison en attente</div>
            </div>`;
        return;
    }

    colis.forEach(c => {
        const item = document.createElement('div');
        item.className = 'colis-item clickable';
        
        const badgeClass = `badge-${c.badge || 'transit'}`;
        const badgeLabel = COLIS_BADGE_LABELS[c.badge] || c.statut;
        
        item.innerHTML = `
            <div class="colis-item-top">
                <span class="colis-carrier">${escapeHtml(c.transporteur || c.expediteur)}</span>
                <span class="colis-status-badge ${badgeClass}">${escapeHtml(badgeLabel)}</span>
            </div>
            <div class="colis-title">${escapeHtml(c.nom)}</div>
        `;

        // Discrimination tactile : un glissement pour scroller ne doit PAS ouvrir la modale
        let startY = 0;
        let isDrag = false;
        item.addEventListener('pointerdown', (e) => {
            startY = e.clientY;
            isDrag = false;
        });
        item.addEventListener('pointermove', (e) => {
            if (Math.abs(e.clientY - startY) > 8) {
                isDrag = true;
            }
        });
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!isDrag) {
                openColisModal(c);
            }
        });

        colisList.appendChild(item);
    });
}

function renderRouteAlerts(routeAlerts) {
    if (!routeAlertsList) return;
    
    const count = routeAlerts && routeAlerts.alerts ? routeAlerts.alerts.length : 0;
    if (modalAlertsCount) {
        modalAlertsCount.textContent = `${count} perturbation${count > 1 ? 's' : ''} active${count > 1 ? 's' : ''}`;
    }

    if (!routeAlerts || !routeAlerts.alerts || routeAlerts.alerts.length === 0) {
        routeAlertsList.innerHTML = `
            <div class="route-alert-empty">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>
                <span>Itinéraire dégagé • Aucun obstacle</span>
            </div>
        `;
        if (modalAlertsList) {
            modalAlertsList.innerHTML = `
                <div style="text-align:center; padding:40px; color:#10b981; font-weight:600; font-size:1rem; display:flex; flex-direction:column; align-items:center; gap:12px;">
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>
                    <span>Itinéraire totalement dégagé • Aucun obstacle ni fermeture signalés par le PC Lutèce sur Arsonval ➔ Général Foy.</span>
                </div>
            `;
        }
        return;
    }
    
    routeAlertsList.innerHTML = '';
    if (modalAlertsList) modalAlertsList.innerHTML = '';

    routeAlerts.alerts.forEach(alert => {
        const badgeClass = alert.severity === 'danger' ? 'badge-alert-danger' : (alert.severity === 'warning' ? 'badge-alert-warning' : 'badge-alert-info');
        
        // Petite tuile
        const item = document.createElement('div');
        item.className = 'route-alert-item';
        item.innerHTML = `
            <div class="route-alert-left">
                <div class="route-alert-street">${alert.street} <span style="font-size:0.58rem; color:var(--text-muted); font-weight:normal;">(${alert.dist_m}m)</span></div>
                <div class="route-alert-desc" title="${alert.desc}">${alert.desc || 'Perturbation signalée'}</div>
            </div>
            <span class="route-alert-badge ${badgeClass}">${alert.label}</span>
        `;
        routeAlertsList.appendChild(item);

        // Grande modale détaillée
        if (modalAlertsList) {
            const mItem = document.createElement('div');
            mItem.className = 'modal-alert-item';
            mItem.innerHTML = `
                <div class="modal-alert-top">
                    <div>
                        <span class="modal-alert-street">${alert.street}</span>
                        <span class="modal-alert-distance">à ${alert.dist_m}m de votre parcours</span>
                    </div>
                    <span class="route-alert-badge ${badgeClass}" style="font-size:0.75rem; padding:3px 8px;">${alert.label}</span>
                </div>
                <div class="modal-alert-desc">
                    ${alert.desc || 'Intervention ou restriction de circulation en cours sur cet axe.'}
                </div>
                ${alert.until ? `<div class="modal-alert-distance" style="margin-top:4px;">Jusqu'au ${alert.until}</div>` : ''}
            `;
            modalAlertsList.appendChild(mItem);
        }
    });
}

/* -------------------------------------------------------------------------- */
/* Initialisation                                                             */
/* -------------------------------------------------------------------------- */
async function fetchSystemHealth() {
    const el = document.getElementById('footerHealth');
    if (!el) return;
    try {
        const res = await fetch('/api/system/health');
        if (!res.ok) return;
        const h = await res.json();
        const parts = [];
        if (h.cpu_temp !== null && h.cpu_temp !== undefined) parts.push(`${h.cpu_temp}°C`);
        if (h.fan_rpm !== null && h.fan_rpm !== undefined) {
            parts.push(`${h.fan_rpm} RPM`);
        } else if (h.fan_percent !== null && h.fan_percent !== undefined) {
            parts.push(`Fan ${h.fan_percent}%`);
        }
        if (h.disk_used_pct !== null && h.disk_used_pct !== undefined) {
            parts.push(`SD ${h.disk_used_pct}%`);
        }
        if (h.sd_readonly) parts.push('RO!');

        el.textContent = parts.join(' · ');
        el.classList.remove('warn', 'crit');
        if (h.status === 'warn' || h.status === 'crit') {
            el.classList.add(h.status);
        }
    } catch (e) {}
}

initRouteMap();
updateClock();
setInterval(updateClock, 1000);
setInterval(updateIdleCountdown, 1000);
fetchData();
setInterval(fetchData, CONFIG.REFRESH_INTERVAL);
fetchSystemHealth();
setInterval(fetchSystemHealth, 30000);

// Support URL params pour tests d'affichage (?modal=1, ?cat=1)
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('modal') === '1') {
    setTimeout(openAlertsModal, 800);
}
if (urlParams.get('cat') === '1') {
    setTimeout(toggleFlipper, 800);
}
if (urlParams.get('colis') === '1') {
    setTimeout(() => { const el = colisList && colisList.querySelector('.colis-item'); if (el) el.click(); }, 2500);
}

/* -------------------------------------------------------------------------- */
/* Sortie du mode kiosque (5 taps rapides sur le logo)                        */
/* -------------------------------------------------------------------------- */
let brandTapCount = 0;
let brandTapTimer = null;
const brandContainer = document.querySelector('.brand');

if (brandContainer) {
    brandContainer.style.cursor = 'pointer';
    brandContainer.setAttribute('title', 'Tapez 5 fois pour quitter le mode kiosque');
    
    brandContainer.addEventListener('click', async (e) => {
        brandTapCount++;
        clearTimeout(brandTapTimer);
        brandTapTimer = setTimeout(() => {
            brandTapCount = 0;
        }, 2000); // Réinitialise si plus de 2s sans interaction

        // Feedback visuel à chaque tap
        brandContainer.style.transition = 'transform 0.12s ease';
        brandContainer.style.transform = `scale(${1 + brandTapCount * 0.05})`;
        setTimeout(() => { brandContainer.style.transform = 'scale(1)'; }, 120);

        if (brandTapCount >= 5) {
            brandTapCount = 0;
            
            // Toast de confirmation
            const toast = document.createElement('div');
            toast.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(15, 23, 42, 0.96);
                border: 2px solid #ef4444;
                color: #ffffff;
                padding: 24px 36px;
                border-radius: 16px;
                text-align: center;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8), 0 0 25px rgba(239, 68, 68, 0.5);
                z-index: 99999;
                font-family: 'Outfit', sans-serif;
            `;
            toast.innerHTML = `
                <div style="font-size: 36px; margin-bottom: 8px;">🔓</div>
                <div style="font-size: 19px; font-weight: 700; color: #ef4444; margin-bottom: 4px;">Sortie du mode kiosque</div>
                <div style="font-size: 13px; color: #94a3b8;">Fermeture de Chromium en cours...</div>
            `;
            document.body.appendChild(toast);

            try {
                await fetch('/api/kiosk/exit', { method: 'POST' });
            } catch (err) {
                console.error("Erreur exit kiosk:", err);
            }
        }
    });
}

