// ── Configuratie ───────────────────────────────────────────────────────────
// Pas dit aan naar het IP van de Mac waarop control-server/server.py draait.
// Dit IP moet overeenkomen met SERVER_IP in rover-code/main.py.
const GPS_SERVER = 'http://172.20.10.7:5000';
const GPS_POLL_MS = 1000;

// ── Map setup ──────────────────────────────────────────────────────────────

const map = L.map('map').setView([51.002844, 3.693125], 13);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
}).addTo(map);

new L.Control.Geocoder().addTo(map);

navigator.geolocation.getCurrentPosition(pos => {
    map.setView([pos.coords.latitude, pos.coords.longitude], 16);
    L.marker([pos.coords.latitude, pos.coords.longitude]).addTo(map);
}, () => {});

// ── State ──────────────────────────────────────────────────────────────────

let fieldPoints   = [];      // [[lat, lng], ...]
let fieldClosed   = false;
let previewPoly   = null;    // L.polyline tijdens tekenen
let closingLine   = null;    // stippellijn terug naar beginpunt
let firstMarker   = null;    // speciaal startpunt-markering
let fieldPolygon  = null;    // L.polygon na sluiten
const vertexMarkers = [];

const cropLayer   = L.layerGroup().addTo(map);
let cropRowCoords = [];      // [[startLatLng, endLatLng], ...] voor export


// ── Veld tekenen ───────────────────────────────────────────────────────────

map.on('click', e => {
    if (fieldClosed) return;

    // Klik dicht bij beginpunt → veld sluiten
    if (fieldPoints.length >= 3) {
        const firstLatLng = L.latLng(fieldPoints[0]);
        const clickPx  = map.latLngToLayerPoint(e.latlng);
        const firstPx  = map.latLngToLayerPoint(firstLatLng);
        if (clickPx.distanceTo(firstPx) < 14) {
            closeField();
            return;
        }
    }

    const { lat, lng } = e.latlng;
    fieldPoints.push([lat, lng]);
    updateCoords();

    // Beginpunt krijgt een aparte stijl met tooltip
    if (fieldPoints.length === 1) {
        firstMarker = L.circleMarker([lat, lng], {
            radius: 7, color: '#fff', weight: 2,
            fillColor: '#e87722', fillOpacity: 1
        }).addTo(map);
        firstMarker.bindTooltip('Klik hier om te sluiten', { sticky: true });
    } else {
        vertexMarkers.push(
            L.circleMarker([lat, lng], {
                radius: 4, color: '#e87722',
                fillColor: '#e87722', fillOpacity: 1, weight: 0
            }).addTo(map)
        );
    }

    // Preview-polyline bijwerken
    if (previewPoly) {
        previewPoly.setLatLngs(fieldPoints);
    } else {
        previewPoly = L.polyline(fieldPoints, {
            color: '#e87722', weight: 2, dashArray: '6 4'
        }).addTo(map);
    }

    // Sluitlijn naar beginpunt
    if (fieldPoints.length >= 2) {
        const closeCoords = [[lat, lng], fieldPoints[0]];
        if (closingLine) {
            closingLine.setLatLngs(closeCoords);
        } else {
            closingLine = L.polyline(closeCoords, {
                color: '#e87722', weight: 1.5, dashArray: '3 6', opacity: 0.4
            }).addTo(map);
        }
    }

    document.getElementById('close-field-btn').disabled = fieldPoints.length < 3;
});

function updateCoords() {
    document.getElementById('coordinates-textarea').value =
        fieldPoints.map(p => p[0].toFixed(7) + ', ' + p[1].toFixed(7)).join('\n');
}

function closeField() {
    if (fieldPoints.length < 3) return;
    fieldClosed = true;

    [previewPoly, closingLine].forEach(l => l && map.removeLayer(l));
    previewPoly = closingLine = null;
    if (firstMarker) { map.removeLayer(firstMarker); firstMarker = null; }
    vertexMarkers.forEach(m => map.removeLayer(m));
    vertexMarkers.length = 0;

    fieldPolygon = L.polygon(fieldPoints, {
        color: '#5a7a32', weight: 2.5,
        fillColor: '#7db35e', fillOpacity: 0.15
    }).addTo(map);

    map.fitBounds(fieldPolygon.getBounds(), { padding: [32, 32] });

    document.getElementById('close-field-btn').disabled = true;
    document.getElementById('step-crops').hidden = false;
    generateRows();
    sendFieldToServer();
}

async function sendFieldToServer() {
    const ring = fieldPoints.map(p => [p[1], p[0]]);
    ring.push(ring[0]);
    const poly = turf.polygon([ring]);

    // Krimp polygon 5m naar binnen als buffer tegen GPS-drift
    const shrunk = turf.buffer(poly, -0.005, { units: 'kilometers' });
    if (!shrunk) {
        console.warn('Polygon te klein om te krimpen, origineel gebruikt');
        return;
    }
    const shrunkPoints = shrunk.geometry.coordinates[0]
        .slice(0, -1)               // sluitpunt verwijderen
        .map(c => [c[1], c[0]]);    // [lng, lat] → [lat, lng]

    const status = document.getElementById('geofence-status');
    try {
        await fetch(`${GPS_SERVER}/field`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ polygon: shrunkPoints })
        });
        status.textContent = `Geofence actief (${shrunkPoints.length} punten, 5m buffer)`;
        status.style.color = '#5a7a32';
    } catch (e) {
        console.warn('Kon geofence niet naar server sturen:', e);
        status.textContent = 'Geofence upload mislukt';
        status.style.color = '#c0392b';
    }
}

document.getElementById('close-field-btn').addEventListener('click', closeField);

document.getElementById('clear-btn').addEventListener('click', () => {
    fieldPoints   = [];
    fieldClosed   = false;
    cropRowCoords = [];

    // Geofence wissen op server
    fetch(`${GPS_SERVER}/field`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ polygon: null })
    }).catch(() => {});
    const status = document.getElementById('geofence-status');
    status.textContent = 'Geen geofence actief';
    status.style.color = '';

    [previewPoly, closingLine, fieldPolygon].forEach(l => l && map.removeLayer(l));
    previewPoly = closingLine = fieldPolygon = null;
    if (firstMarker) { map.removeLayer(firstMarker); firstMarker = null; }
    vertexMarkers.forEach(m => map.removeLayer(m));
    vertexMarkers.length = 0;
    cropLayer.clearLayers();

    document.getElementById('coordinates-textarea').value = '';
    document.getElementById('close-field-btn').disabled = true;
    document.getElementById('step-crops').hidden = true;
});

// ── Hoekslider ─────────────────────────────────────────────────────────────

const angleSlider  = document.getElementById('angle-slider');
const angleDisplay = document.getElementById('angle-display');
const dirRows      = document.getElementById('dir-rows');

angleSlider.addEventListener('input', () => {
    const a = parseInt(angleSlider.value);
    angleDisplay.textContent = a + '°';
    dirRows.setAttribute('transform', `rotate(${a})`);
    generateRows();
});

document.getElementById('spacing-input').addEventListener('input', generateRows);

// ── Rijgeneratie (Turf.js) ─────────────────────────────────────────────────

document.getElementById('clear-rows-btn').addEventListener('click', () => {
    cropLayer.clearLayers();
    cropRowCoords = [];
});

function generateRows() {
    if (!fieldPolygon) return;
    cropLayer.clearLayers();
    cropRowCoords = [];

    const angle   = parseInt(angleSlider.value);
    const spacing = parseFloat(document.getElementById('spacing-input').value);
    if (!spacing || spacing <= 0) return;

    const color = '#5a7a32';

    // Turf gebruikt [lng, lat]
    const ring = fieldPoints.map(p => [p[1], p[0]]);
    ring.push(ring[0]); // ring sluiten
    const poly     = turf.polygon([ring]);
    const polyLine = turf.polygonToLine(poly); // voor snijpunten

    const center = turf.centroid(poly);
    const bbox   = turf.bbox(poly);
    const far    = turf.point([bbox[0], bbox[1]]);
    const radius = turf.distance(center, far, { units: 'kilometers' }) * 1.5; // km

    const perpBearing = (angle + 90) % 360;
    const halfCount   = Math.ceil((radius * 1000) / spacing) + 2;

    for (let i = -halfCount; i <= halfCount; i++) {
        const offsetKm = (i * spacing) / 1000;
        const offPt    = turf.destination(center, offsetKm, perpBearing, { units: 'kilometers' });
        const p1 = turf.destination(offPt, radius + 0.1, angle,               { units: 'kilometers' });
        const p2 = turf.destination(offPt, radius + 0.1, (angle + 180) % 360, { units: 'kilometers' });
        const rowLine = turf.lineString([p1.geometry.coordinates, p2.geometry.coordinates]);

        let ixResult;
        try { ixResult = turf.lineIntersect(rowLine, polyLine); }
        catch (err) { continue; }

        const pts = ixResult.features.map(f => f.geometry.coordinates);
        if (pts.length < 2) continue;

        // Sorteren op afstand van p1 (zodat paren correct zijn)
        pts.sort((a, b) =>
            turf.distance(p1, turf.point(a)) -
            turf.distance(p1, turf.point(b))
        );

        // Elk opeenvolgend paar: middelpunt controleren op ligging binnen polygoon
        for (let j = 0; j + 1 < pts.length; j++) {
            const mid = turf.point([
                (pts[j][0] + pts[j + 1][0]) / 2,
                (pts[j][1] + pts[j + 1][1]) / 2,
            ]);
            let inside = false;
            try { inside = turf.booleanPointInPolygon(mid, poly); }
            catch (err) { continue; }

            if (inside) {
                const a = [pts[j][1],     pts[j][0]    ];
                const b = [pts[j + 1][1], pts[j + 1][0]];
                L.polyline([a, b], { color, weight: 1.5, opacity: 0.9 }).addTo(cropLayer);
                cropRowCoords.push([a, b]);
            }
        }
    }
}

// ── Robot GPS ─────────────────────────────────────────────────────────────

const robotIcon = L.icon({
    iconUrl: 'robot.png',
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -20],
});

let robotMarker = null;
let robotPath   = L.polyline([], { color: '#4a6e9e', weight: 2.5, opacity: 0.7 }).addTo(map);

const gpsDot    = document.getElementById('gps-dot');
const gpsCoords = document.getElementById('gps-coords');
const centerBtn = document.getElementById('center-robot-btn');

document.getElementById('clear-track-btn').addEventListener('click', () => {
    robotPath.setLatLngs([]);
});

centerBtn.addEventListener('click', () => {
    if (robotMarker) map.panTo(robotMarker.getLatLng());
});

async function pollGps() {
    try {
        const res  = await fetch(`${GPS_SERVER}/gps`);
        const data = await res.json();

        if (data.fix && data.lat !== null && data.lon !== null) {
            const latlng = [data.lat, data.lon];

            if (!robotMarker) {
                robotMarker = L.marker(latlng, { icon: robotIcon, zIndexOffset: 1000 })
                    .bindPopup('Robot')
                    .addTo(map);
            } else {
                robotMarker.setLatLng(latlng);
            }

            robotPath.addLatLng(latlng);

            gpsDot.className = 'gps-dot gps-dot--fix';
            gpsCoords.textContent =
                `${data.lat.toFixed(6)}, ${data.lon.toFixed(6)}`;
            centerBtn.disabled = false;
        } else {
            gpsDot.className = 'gps-dot gps-dot--nofix';
            gpsCoords.textContent = 'Geen GPS-fix';
        }
    } catch {
        gpsDot.className = 'gps-dot gps-dot--off';
        gpsCoords.textContent = 'Server niet bereikbaar';
    }
}

setInterval(pollGps, GPS_POLL_MS);
pollGps();

// ── Download ───────────────────────────────────────────────────────────────

document.getElementById('download-btn').addEventListener('click', () => {
    if (fieldPoints.length === 0) return;

    const angle   = angleSlider.value;
    const spacing = document.getElementById('spacing-input').value;

    let csv = '# Veld Planner Export\n';
    if (fieldClosed) {
        csv += `# Rijrichting: ${angle}°\n# Rijafstand: ${spacing} m\n`;
    }
    csv += '#\n# Veldgrens\nlatitude,longitude\n';
    fieldPoints.forEach(p => { csv += `${p[0].toFixed(7)},${p[1].toFixed(7)}\n`; });

    if (cropRowCoords.length > 0) {
        csv += '#\n# Rijen\nlat_start,lng_start,lat_eind,lng_eind\n';
        cropRowCoords.forEach(([a, b]) => {
            csv += `${a[0].toFixed(7)},${a[1].toFixed(7)},${b[0].toFixed(7)},${b[1].toFixed(7)}\n`;
        });
    }

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href     = url;
    link.download = 'veld.csv';
    link.click();
    URL.revokeObjectURL(url);
});
