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

// TRMNL Elements
const cardTrmnl = document.getElementById('cardTrmnl');
const trmnlBadge = document.getElementById('trmnlBadge');
const trmnlBody = document.getElementById('trmnlBody');
const trmnlModal = document.getElementById('trmnlModal');
const btnCloseTrmnlModal = document.getElementById('btnCloseTrmnlModal');
const trmnlModalBody = document.getElementById('trmnlModalBody');
const trmnlModalFooterNote = document.getElementById('trmnlModalFooterNote');
let currentTrmnlData = null;

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
        catImg.src = `assets/cats/cat${catIndex + 1}.jpg`;
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
    const wasInactive = isDimmed || isSleeping;
    idleSeconds = 0;
    if (wasInactive) {
        wakeScreen();
    }
}

function updateIdleCountdown() {
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
    isDimmed = false;
    isSleeping = false;
    kioskContainer.classList.remove('dimmed');
    screenSleepOverlay.classList.remove('active');
    try { await fetch('/api/screen/wake', { method: 'POST' }); } catch (e) {}
}

['touchstart', 'touchend', 'click', 'mousemove', 'keydown'].forEach(evt => {
    window.addEventListener(evt, resetIdleTimer, { passive: true });
});

screenSleepOverlay.addEventListener('click', wakeScreen);
screenSleepOverlay.addEventListener('touchstart', (e) => {
    e.preventDefault();
    wakeScreen();
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
        
        if (data.week_ab) {
            weekBadge.textContent = data.week_ab;
        }
        
        renderWeather(data.weather);
        renderRain(data.rain_hour);
        renderTraffic(data.traffic);
        renderRouteAlerts(data.route_alerts);
        renderTemperatures(data.temperatures);
        renderColis(data.colis);
        renderTrmnl(data.trmnl);
        
        const now = new Date();
        lastSyncTime.textContent = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
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

function renderRain(rain) {
    if (!rain) return;
    
    rainStatusText.textContent = rain.status || "Temps sec la prochaine heure";
    rainTimeline.innerHTML = '';
    
    const timeline = rain.timeline || [];
    timeline.forEach(item => {
        const bar = document.createElement('div');
        bar.className = `rain-bar rain-${item.level}`;
        bar.title = `${item.min} min : ${item.desc}`;
        rainTimeline.appendChild(bar);
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
        colisList.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; padding:20px;">Aucun colis en attente</div>';
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

/* -------------------------------------------------------------------------- */
/* Suivi TRMNL Model X (#56352)                                               */
/* -------------------------------------------------------------------------- */
function openTrmnlModal(t) {
    if (!trmnlModal || !t) return;
    const isShipped = t.is_shipped;
    const badgeHtml = isShipped 
        ? `<span class="colis-status-badge badge-delivery" style="font-size:0.75rem; padding:3px 8px;">Expédié</span>`
        : `<span class="colis-status-badge badge-transit" style="font-size:0.75rem; padding:3px 8px;">En attente de fabrication</span>`;

    const rows = [
        ['Statut', badgeHtml],
        ['Appareil', 'TRMNL Model X (Écran e-Paper 10.3 pouces connecté)'],
        ['Numéro de commande', `<span class="colis-detail-mono">#${escapeHtml(t.order_number || '56352')}</span>`],
        ['Atelier d\'assemblage', 'Berlin, Allemagne (TRMNL Europe / 48.8% du volume mondial)'],
        ['File Europe (corrigée)', `<strong>Rang #${t.pos_eu || '—'}</strong> sur ~${t.total_eu || '—'} commandes`],
        ['Commandes devant vous', `<strong>~${t.ahead_eu || 0}</strong> appareils restants à assembler à Berlin`],
        ['Avancement Europe', `${t.progress_percent || 0}% de la file Berlin traitée`],
        ['File globale mondiale', `Rang #${t.pos_global || '—'} sur ${t.total_global || '—'} (Ateliers Atlanta + Berlin)`],
        ['Dernier point logistique', escapeHtml(t.berlin_status || '—')]
    ];

    if (isShipped && t.days_remaining !== null) {
        rows.push(['Règle de rétention', `Cette carte disparaîtra automatiquement dans ${t.days_remaining} jour(s)`]);
    }

    trmnlModalBody.innerHTML = rows.map(([k, v]) => `
        <div class="colis-detail-row">
            <span class="colis-detail-label">${k}</span>
            <span class="colis-detail-value">${v}</span>
        </div>`).join('');

    if (trmnlModalFooterNote && t.last_check) {
        const d = new Date(t.last_check);
        trmnlModalFooterNote.textContent = `Dernière vérification TRMNL : ${d.toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'})}`;
    }

    trmnlModal.classList.remove('hidden');
}

function closeTrmnlModal() {
    if (trmnlModal) trmnlModal.classList.add('hidden');
}

if (cardTrmnl) {
    cardTrmnl.addEventListener('click', (e) => {
        e.stopPropagation();
        if (currentTrmnlData) openTrmnlModal(currentTrmnlData);
    });
}
if (btnCloseTrmnlModal) {
    btnCloseTrmnlModal.addEventListener('click', (e) => {
        e.stopPropagation();
        closeTrmnlModal();
    });
}
if (trmnlModal) {
    trmnlModal.addEventListener('click', (e) => {
        if (e.target === trmnlModal) closeTrmnlModal();
    });
}

function renderTrmnl(trmnl) {
    if (!cardTrmnl) return;
    currentTrmnlData = trmnl;

    if (!trmnl || trmnl.visible === false || trmnl.expired === true) {
        cardTrmnl.style.display = 'none';
        return;
    }

    cardTrmnl.style.display = 'flex';

    if (trmnl.is_shipped) {
        if (trmnlBadge) {
            trmnlBadge.className = 'badge badge-trmnl shipped';
            trmnlBadge.textContent = 'EXPÉDIÉ';
        }
        if (trmnlBody) {
            trmnlBody.innerHTML = `
                <div class="trmnl-shipped-box">
                    <div class="trmnl-shipped-title">🎉 Commande Expédiée !</div>
                    <div class="trmnl-shipped-countdown">${trmnl.days_remaining ? `Auto-suppression dans ${trmnl.days_remaining}j` : 'En acheminement'}</div>
                </div>
            `;
        }
        return;
    }

    if (trmnlBadge) {
        trmnlBadge.className = 'badge badge-trmnl';
        trmnlBadge.textContent = `#${trmnl.order_number || '56352'}`;
    }

    if (trmnlBody) {
        const pct = Math.min(100, Math.max(5, trmnl.progress_percent || 0));
        trmnlBody.innerHTML = `
            <div class="trmnl-rank-row">
                <div class="trmnl-eu-rank">
                    <span style="font-size:0.68rem; color:var(--text-secondary); font-weight:normal; margin-right:3px;">Europe</span>
                    <span class="rank-num">#${trmnl.pos_eu || '—'}</span>
                    <span class="trmnl-eu-total">/~${trmnl.total_eu || '—'}</span>
                </div>
                <span class="trmnl-global-stat">Monde #${trmnl.pos_global}/${trmnl.total_global}</span>
            </div>
            <div class="trmnl-progress-bar-bg" title="${trmnl.progress_percent || 0}% complété">
                <div class="trmnl-progress-bar-fill" style="width: ${pct}%;"></div>
            </div>
            <div class="trmnl-sub-stats">
                <span>Devant vous : <strong class="trmnl-ahead-highlight">~${trmnl.ahead_eu || 0}</strong></span>
                <span style="color:var(--text-muted); font-size:0.56rem;">Détails au toucher</span>
            </div>
        `;
    }
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
initRouteMap();
updateClock();
setInterval(updateClock, 1000);
setInterval(updateIdleCountdown, 1000);
fetchData();
setInterval(fetchData, CONFIG.REFRESH_INTERVAL);

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
if (urlParams.get('trmnl') === '1') {
    setTimeout(() => { if (currentTrmnlData) openTrmnlModal(currentTrmnlData); }, 1500);
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

