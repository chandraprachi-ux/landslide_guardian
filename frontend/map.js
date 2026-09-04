/**
 * LANDSLIDE GUARDIAN — Weather-Style Interactive Regional Map Controller
 * 
 * Conceptual Features:
 * - Zoom Level 1: NER Broad Regional Overview with polygon bounds & regional summary
 * - Zoom Level 2: State / District Regional View with regional risk grid
 * - Zoom Level 3-4: Local Area & Sub-Locations (Rimbi, Gyalshing, Mawlai, Tupul, etc.)
 * - Weather Map Layers: Landslide Risk, 24h Rainfall, Soil Moisture, Slope, History, Sensors
 * - Live Autocomplete Search Box
 * - Location Condition Detail Card Panel
 * - Controlled concurrency, viewport-based lazy loading & caching
 */

let mapInstance = null;
let currentLayer = "risk"; // "risk" | "rainfall" | "moisture" | "slope" | "history" | "sensors"
let currentRegionId = null;

// Map layer groups
let regionPolygonsGroup = null;
let gridLayerGroup = null;
let sublocationsLayerGroup = null;
let historicalLayerGroup = null;
let sensorLayerGroup = null;

// Cached data
let allRegions = [];
let allSublocations = [];
let regionGridsCache = {};
let sublocationsDataCache = {};
let activeHotspots = [];
let selectedLocation = null;

const RISK_COLORS = {
  LOW: "#10b981",
  MODERATE: "#eab308",
  HIGH: "#f97316",
  CRITICAL: "#ef4444"
};

const RAIN_COLORS = [
  { max: 5, color: "#93c5fd" },
  { max: 25, color: "#3b82f6" },
  { max: 50, color: "#1d4ed8" },
  { max: 100, color: "#d97706" },
  { max: 9999, color: "#dc2626" }
];

const MOISTURE_COLORS = [
  { max: 30, color: "#86efac" },
  { max: 50, color: "#22c55e" },
  { max: 70, color: "#eab308" },
  { max: 85, color: "#f97316" },
  { max: 100, color: "#ef4444" }
];

const SLOPE_COLORS = [
  { max: 15, color: "#22c55e" },
  { max: 28, color: "#eab308" },
  { max: 38, color: "#f97316" },
  { max: 90, color: "#ef4444" }
];

document.addEventListener("DOMContentLoaded", async () => {
  initMap();
  setupSearch();
  await loadBaseData();
  renderRegionalOverview();
});

function initMap() {
  // Center of North-Eastern Region (NER)
  mapInstance = L.map("fullMap", {
    zoomControl: true,
    minZoom: 6,
    maxZoom: 16
  }).setView([26.1158, 91.7086], 7);

  // Standard high-contrast OpenStreetMap tile layer (100% free, no API key watermark)
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  }).addTo(mapInstance);

  regionPolygonsGroup = L.layerGroup().addTo(mapInstance);
  gridLayerGroup = L.layerGroup().addTo(mapInstance);
  sublocationsLayerGroup = L.layerGroup().addTo(mapInstance);
  historicalLayerGroup = L.layerGroup().addTo(mapInstance);
  sensorLayerGroup = L.layerGroup().addTo(mapInstance);

  // Dynamic zoom listener to adapt detail like modern weather apps
  mapInstance.on("zoomend", () => {
    handleZoomLevelChange();
  });

  // Map click anywhere outside markers can deselect or close panel
  mapInstance.on("click", (e) => {
    // If clicked on open area at high zoom, can resolve coordinate
    if (mapInstance.getZoom() >= 10 && !e.originalEvent._markerClicked) {
      loadCoordinateData(e.latlng.lat, e.latlng.lng);
    }
  });
}

async function loadBaseData() {
  try {
    const res = await API.get("/map/layers");
    allRegions = res.regions || [];
    allSublocations = res.sublocations || [];
    activeHotspots = res.hotspots || [];

    // Update hotspots badge
    const badge = document.getElementById("statHotspotsBadge");
    if (badge) {
      badge.textContent = `${activeHotspots.length} Emerging Hotspots`;
      badge.className = activeHotspots.length > 0 ? "badge badge-critical" : "badge badge-low";
    }

    // Render historical & sensors layer groups ahead of time
    renderHistoricalLayer(res.historical_events || []);
    renderSensorLayer(res.sensor_nodes || []);
  } catch (err) {
    console.warn("API /map/layers unavailable, initializing local regional geography:", err);
    // Initialize default NER regions bounds
    allRegions = [
      { id: "sikkim", name: "Sikkim", center: [27.35, 88.50], bounds: [[27.05, 88.05], [27.85, 88.90]], high_risk: true },
      { id: "meghalaya", name: "Meghalaya", center: [25.55, 91.85], bounds: [[25.10, 90.00], [26.05, 92.80]], high_risk: false },
      { id: "mizoram", name: "Mizoram", center: [23.40, 92.85], bounds: [[21.90, 92.20], [24.55, 93.45]], high_risk: true },
      { id: "nagaland", name: "Nagaland", center: [26.05, 94.45], bounds: [[25.20, 93.35], [27.05, 95.25]], high_risk: false },
      { id: "arunachal_pradesh", name: "Arunachal Pradesh", center: [27.75, 93.80], bounds: [[26.65, 91.60], [29.45, 97.40]], high_risk: false },
      { id: "assam", name: "Assam", center: [26.20, 92.93], bounds: [[24.15, 89.70], [27.95, 96.00]], high_risk: false },
      { id: "manipur", name: "Manipur", center: [24.80, 93.90], bounds: [[23.80, 93.05], [25.70, 94.80]], high_risk: true },
      { id: "tripura", name: "Tripura", center: [23.83, 91.30], bounds: [[22.95, 91.15], [24.55, 92.35]], high_risk: false }
    ];
    // Map all 37 DEMO_LOCATIONS
    allSublocations = DEMO_LOCATIONS.map(l => ({
      name: l.name,
      state: l.state,
      district: l.district || l.state,
      lat: l.lat,
      lon: l.lon,
      slope: l.slope || 32,
      historical_freq: 5
    }));
    handleZoomLevelChange();
  }
}

function handleZoomLevelChange() {
  const z = mapInstance.getZoom();
  const hint = document.getElementById("zoomHint");

  if (z <= 7) {
    // Level 1: NER Overview
    if (hint) hint.textContent = "Level 1: NER Overview · Click any region to zoom";
    gridLayerGroup.clearLayers();
    sublocationsLayerGroup.clearLayers();
    renderRegionalOverview();
  } else if (z >= 8 && z <= 9) {
    // Level 2: Region / District Grid
    if (hint) hint.textContent = "Level 2: Regional Grid · Zoom closer for named sub-locations";
    regionPolygonsGroup.clearLayers();
    renderActiveRegionGrid();
    renderKeySublocations(false);
  } else {
    // Level 3+: Local Sub-locations and Detailed Grid Cells
    if (hint) hint.textContent = "Level 3+: Local Sub-Locations & Site Telemetry";
    regionPolygonsGroup.clearLayers();
    renderActiveRegionGrid();
    renderKeySublocations(true);
  }
}

function renderRegionalOverview() {
  regionPolygonsGroup.clearLayers();

  allRegions.forEach(reg => {
    const bounds = reg.bounds;
    // Sleek, modern region boundary outline
    const polygon = L.rectangle(bounds, {
      color: "#10b981",
      weight: 1.2,
      dashArray: "3, 6",
      fillColor: "#059669",
      fillOpacity: 0.05
    });

    const centerMarker = L.circleMarker(reg.center, {
      radius: 12,
      color: "#ffffff",
      fillColor: "#10b981",
      fillOpacity: 0.9,
      weight: 2
    });

    const tooltipHtml = `
      <div style="font-family: sans-serif; font-size: 0.85rem; padding: 2px;">
        <strong style="color: #fff; font-size: 0.95rem;">${reg.name} Region</strong><br>
        <span style="color: #94a3b8;">${reg.districts ? reg.districts.length : 4} monitored districts</span><br>
        <span style="color: #34d399; font-weight: 600; font-size: 0.76rem;">Click to zoom into region &rarr;</span>
      </div>
    `;
    polygon.bindTooltip(tooltipHtml, { sticky: true });
    centerMarker.bindTooltip(tooltipHtml, { sticky: true });

    const clickAction = () => {
      zoomToRegion(reg.id);
    };

    polygon.on("click", clickAction);
    centerMarker.on("click", clickAction);

    regionPolygonsGroup.addLayer(polygon);
    regionPolygonsGroup.addLayer(centerMarker);
  });
}

async function renderActiveRegionGrid() {
  // If we don't have an active region, determine from map center
  const center = mapInstance.getCenter();
  let nearestRegion = allRegions.find(r => {
    const b = r.bounds;
    return center.lat >= b[0][0] && center.lat <= b[1][0] &&
           center.lng >= b[0][1] && center.lng <= b[1][1];
  }) || allRegions[0];

  if (!nearestRegion) return;
  const rid = nearestRegion.id;

  if (!regionGridsCache[rid]) {
    try {
      const data = await API.get(`/locations/grid/${rid}?step=0.22`);
      regionGridsCache[rid] = data.cells || [];
    } catch (e) {
      console.error(`Failed to fetch grid for ${rid}:`, e);
      return;
    }
  }

  const cells = regionGridsCache[rid] || [];
  gridLayerGroup.clearLayers();

  cells.forEach(cell => {
    // Generate risk/weather value based on current layer
    let fillColor = "#10b981";
    let fillOpacity = 0.45;
    let labelVal = "";

    if (currentLayer === "risk") {
      // Landslide Risk based on slope and historical frequency
      let score = Math.round(cell.slope * 1.3 + cell.historical_freq * 3.5);
      score = Math.min(95, Math.max(15, score));
      let level = score >= 81 ? "CRITICAL" : (score >= 61 ? "HIGH" : (score >= 31 ? "MODERATE" : "LOW"));
      fillColor = RISK_COLORS[level];
      labelVal = `Risk: ${level} (${score}%)`;
    } else if (currentLayer === "rainfall") {
      fillColor = "#3b82f6";
      labelVal = `Rainfall Overlay`;
      fillOpacity = 0.55;
    } else if (currentLayer === "moisture") {
      let moist = Math.round(cell.porosity * 80);
      fillColor = getMetricColor(moist, MOISTURE_COLORS);
      labelVal = `Soil Moisture: ~${moist}%`;
    } else if (currentLayer === "slope") {
      fillColor = getMetricColor(cell.slope, SLOPE_COLORS);
      labelVal = `Slope: ${cell.slope}°`;
    }

    const rect = L.rectangle(cell.bounds, {
      color: fillColor,
      weight: 1,
      fillColor: fillColor,
      fillOpacity: fillOpacity
    });

    rect.bindTooltip(`
      <div style="font-family: sans-serif; font-size: 0.8rem;">
        <strong>${cell.name}</strong><br>
        <span>${labelVal}</span><br>
        <small style="color: #cbd5e1;">Near ${cell.nearest_sublocation}</small>
      </div>
    `);

    rect.on("click", (e) => {
      e.originalEvent._markerClicked = true;
      loadLocationData(cell.name, cell.lat, cell.lon);
    });

    gridLayerGroup.addLayer(rect);
  });
}

function renderKeySublocations(showDetailed) {
  sublocationsLayerGroup.clearLayers();
  const bounds = mapInstance.getBounds();

  // Filter sublocations within current visible viewport
  const visible = allSublocations.filter(sub => {
    return bounds.contains([sub.lat, sub.lon]);
  });

  visible.forEach(loc => {
    let markerColor = "#38bdf8";
    let radius = showDetailed ? 10 : 7;

    // In landslide risk layer, color sublocations by their risk tier
    if (currentLayer === "risk") {
      let estScore = Math.min(96, Math.max(18, Math.round(loc.slope * 1.4 + loc.historical_freq * 3.8)));
      let level = estScore >= 81 ? "CRITICAL" : (estScore >= 61 ? "HIGH" : (estScore >= 31 ? "MODERATE" : "LOW"));
      markerColor = RISK_COLORS[level];
    } else if (currentLayer === "slope") {
      markerColor = getMetricColor(loc.slope, SLOPE_COLORS);
    }

    const marker = L.circleMarker([loc.lat, loc.lon], {
      radius: radius,
      color: "#fff",
      fillColor: markerColor,
      fillOpacity: 0.9,
      weight: 2
    });

    const isHotspot = activeHotspots.some(h => h.location.includes(loc.name));
    const hotspotBadge = isHotspot ? '<span style="background: #ef4444; color: #fff; padding: 1px 5px; border-radius: 4px; font-size: 0.65rem; margin-left: 4px;">🚨 HOTSPOT</span>' : '';

    marker.bindTooltip(`
      <div style="font-family: sans-serif; min-width: 140px;">
        <strong style="font-size: 0.9rem; color: #fff;">${loc.name}</strong> ${hotspotBadge}<br>
        <span style="color: #94a3b8; font-size: 0.78rem;">${loc.district}, ${loc.state}</span><br>
        <span style="color: #cbd5e1; font-size: 0.75rem;">Slope: ${loc.slope}° · Elev: ${loc.elevation}m</span>
      </div>
    `, { direction: 'top', offset: [0, -8] });

    marker.on("click", (e) => {
      e.originalEvent._markerClicked = true;
      loadLocationData(`${loc.name}, ${loc.state}`, loc.lat, loc.lon);
    });

    sublocationsLayerGroup.addLayer(marker);
  });
}

function renderHistoricalLayer(events) {
  historicalLayerGroup.clearLayers();
  events.forEach(ev => {
    const icon = L.divIcon({
      className: 'custom-div-icon',
      html: `<div style="background: rgba(220, 38, 38, 0.9); border: 2px solid #fff; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 11px;">⚠️</div>`,
      iconSize: [22, 22],
      iconAnchor: [11, 11]
    });

    const marker = L.marker([ev.lat, ev.lon], { icon: icon });
    marker.bindPopup(`
      <div style="font-family: sans-serif; max-width: 220px;">
        <h4 style="margin: 0 0 4px 0; color: #f87171;">⚠️ Historical Landslide</h4>
        <strong>${ev.name} (${ev.year})</strong>
        <p style="font-size: 0.78rem; margin: 4px 0; color: #cbd5e1;">Type: ${ev.type}</p>
        <p style="font-size: 0.75rem; color: #94a3b8;">${ev.impact}</p>
      </div>
    `);
    historicalLayerGroup.addLayer(marker);
  });
}

function renderSensorLayer(sensors) {
  sensorLayerGroup.clearLayers();
  sensors.forEach(sn => {
    const icon = L.divIcon({
      className: 'custom-div-icon',
      html: `<div style="background: rgba(16, 185, 129, 0.9); border: 2px solid #fff; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 11px;">📡</div>`,
      iconSize: [22, 22],
      iconAnchor: [11, 11]
    });

    const marker = L.marker([sn.lat, sn.lon], { icon: icon });
    marker.bindPopup(`
      <div style="font-family: sans-serif; max-width: 220px;">
        <h4 style="margin: 0 0 4px 0; color: #34d399;">📡 IoT Telemetry Node</h4>
        <strong>${sn.node_id} — ${sn.location}</strong>
        <p style="font-size: 0.78rem; margin: 4px 0; color: #cbd5e1;">Type: ${sn.type}</p>
        <p style="font-size: 0.75rem; color: #94a3b8;">Sensor depth: ${sn.depth_m}m · Status: <span style="color:#10b981;font-weight:700;">${sn.status}</span></p>
      </div>
    `);
    sensorLayerGroup.addLayer(marker);
  });
}

function getMetricColor(val, scale) {
  for (let s of scale) {
    if (val <= s.max) return s.color;
  }
  return scale[scale.length - 1].color;
}

// ---------------------------------------------------------------------------
// LAYER SWITCHING & REGION NAVIGATION
// ---------------------------------------------------------------------------

function switchLayer(layerKey) {
  currentLayer = layerKey;

  // Update active pill styling
  document.querySelectorAll(".layer-pill").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-layer") === layerKey);
  });

  // Toggle visibility of specialized static layers
  if (layerKey === "history") {
    mapInstance.addLayer(historicalLayerGroup);
    mapInstance.removeLayer(sensorLayerGroup);
  } else if (layerKey === "sensors") {
    mapInstance.addLayer(sensorLayerGroup);
    mapInstance.removeLayer(historicalLayerGroup);
  } else {
    mapInstance.removeLayer(historicalLayerGroup);
    mapInstance.removeLayer(sensorLayerGroup);
  }

  // Update dynamic legend
  updateLegend(layerKey);

  // Re-render visible grids & sublocations
  handleZoomLevelChange();
}

function updateLegend(layerKey) {
  const bar = document.getElementById("mapLegendBar");
  if (!bar) return;

  if (layerKey === "rainfall") {
    bar.innerHTML = `
      <span style="color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase;">24h Rainfall:</span>
      <div class="legend-item"><span class="status-dot" style="background: #93c5fd;"></span> Light (&lt;5mm)</div>
      <div class="legend-item"><span class="status-dot" style="background: #3b82f6;"></span> Moderate (5-25mm)</div>
      <div class="legend-item"><span class="status-dot" style="background: #1d4ed8;"></span> Heavy (25-50mm)</div>
      <div class="legend-item"><span class="status-dot" style="background: #d97706;"></span> Very Heavy (50-100mm)</div>
      <div class="legend-item"><span class="status-dot" style="background: #dc2626;"></span> Extreme (&gt;100mm)</div>
    `;
  } else if (layerKey === "moisture") {
    bar.innerHTML = `
      <span style="color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase;">Soil Saturation:</span>
      <div class="legend-item"><span class="status-dot" style="background: #86efac;"></span> Dry (&lt;30%)</div>
      <div class="legend-item"><span class="status-dot" style="background: #22c55e;"></span> Moderate (30-50%)</div>
      <div class="legend-item"><span class="status-dot" style="background: #eab308;"></span> High (50-70%)</div>
      <div class="legend-item"><span class="status-dot" style="background: #ef4444;"></span> Saturated (&gt;70%)</div>
    `;
  } else if (layerKey === "slope") {
    bar.innerHTML = `
      <span style="color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase;">Slope Gradient:</span>
      <div class="legend-item"><span class="status-dot" style="background: #22c55e;"></span> Gentle (&lt;15°)</div>
      <div class="legend-item"><span class="status-dot" style="background: #eab308;"></span> Moderate (15-28°)</div>
      <div class="legend-item"><span class="status-dot" style="background: #f97316;"></span> Steep (28-38°)</div>
      <div class="legend-item"><span class="status-dot" style="background: #ef4444;"></span> Critical (&gt;38°)</div>
    `;
  } else if (layerKey === "history") {
    bar.innerHTML = `
      <span style="color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase;">Historical Slides:</span>
      <div class="legend-item">⚠️ Major Historical Debris Avalanches & Slope Failures in NER</div>
    `;
  } else if (layerKey === "sensors") {
    bar.innerHTML = `
      <span style="color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase;">IoT Stations:</span>
      <div class="legend-item">📡 Surface Inclinometers, Piezometers & Rain Telemetry Nodes</div>
    `;
  } else {
    // Default Risk Legend
    bar.innerHTML = `
      <span style="color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase;">Risk Level:</span>
      <div class="legend-item"><span class="status-dot dot-low"></span> Low (&lt;31%)</div>
      <div class="legend-item"><span class="status-dot dot-moderate"></span> Moderate (31-60%)</div>
      <div class="legend-item"><span class="status-dot dot-high"></span> High (61-80%)</div>
      <div class="legend-item"><span class="status-dot dot-critical"></span> Critical (&gt;80%)</div>
    `;
  }
}

function zoomToNER() {
  currentRegionId = null;
  document.querySelectorAll(".ner-region-chip").forEach(c => c.classList.remove("active"));
  document.querySelector(".ner-region-chip")?.classList.add("active");
  mapInstance.flyTo([26.1158, 91.7086], 7, { duration: 1.2 });
}

function zoomToRegion(regionId) {
  const reg = allRegions.find(r => r.id === regionId);
  if (!reg) return;

  currentRegionId = regionId;
  document.querySelectorAll(".ner-region-chip").forEach(c => {
    c.classList.toggle("active", c.textContent.toLowerCase().includes(reg.name.toLowerCase()));
  });

  mapInstance.flyTo(reg.center, reg.zoom || 9, { duration: 1.2 });
}

// ---------------------------------------------------------------------------
// SEARCH AUTOCOMPLETE & NAVIGATION
// ---------------------------------------------------------------------------

function setupSearch() {
  const input = document.getElementById("mapSearchInput");
  const dropdown = document.getElementById("searchResultsDropdown");
  if (!input || !dropdown) return;

  let debounceTimeout = null;

  input.addEventListener("input", () => {
    clearTimeout(debounceTimeout);
    const q = input.value.trim();
    if (!q) {
      dropdown.style.display = "none";
      return;
    }

    debounceTimeout = setTimeout(async () => {
      let results = [];
      try {
        results = await API.get(`/location/search?q=${encodeURIComponent(q)}`);
      } catch (e) {
        console.warn("API search unavailable, using client sublocations list");
      }

      if (!results || results.length === 0) {
        // Instant client fallback match across all 37 sublocations
        results = DEMO_LOCATIONS.filter(l => 
          l.name.toLowerCase().includes(q.toLowerCase()) || 
          l.state.toLowerCase().includes(q.toLowerCase()) ||
          (l.district && l.district.toLowerCase().includes(q.toLowerCase()))
        ).map(l => ({
          name: l.name,
          state: l.state,
          district: l.district,
          lat: l.lat,
          lon: l.lon,
          latitude: l.lat,
          longitude: l.lon
        }));
      }
      renderSearchResults(results);
    }, 150);
  });

  document.addEventListener("click", (e) => {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.style.display = "none";
    }
  });
}

function renderSearchResults(results) {
  const dropdown = document.getElementById("searchResultsDropdown");
  if (!dropdown) return;

  if (!results || results.length === 0) {
    dropdown.innerHTML = `<div style="padding: 0.8rem; color: var(--muted); font-size: 0.82rem; text-align: center;">No matching locations found</div>`;
    dropdown.style.display = "block";
    return;
  }

  dropdown.innerHTML = "";
  results.forEach(item => {
    const div = document.createElement("div");
    div.className = "search-item";
    div.innerHTML = `
      <div>
        <strong>${item.name}</strong><br>
        <small>${item.district ? item.district + ' · ' : ''}${item.corridor || item.state}</small>
      </div>
      <span style="color: var(--green); font-size: 0.75rem; font-weight: 600;">Go &rarr;</span>
    `;

    div.onclick = () => {
      dropdown.style.display = "none";
      document.getElementById("mapSearchInput").value = item.name;

      if (item.is_region && item.region_id) {
        zoomToRegion(item.region_id);
      } else {
        // Fly directly to sub-location
        mapInstance.flyTo([item.latitude || item.lat, item.longitude || item.lon], 11, { duration: 1.4 });
        loadLocationData(item.name, item.latitude || item.lat, item.longitude || item.lon);
      }
    };

    dropdown.appendChild(div);
  });

  dropdown.style.display = "block";
}

// ---------------------------------------------------------------------------
// LOCATION DATA & WEATHER-STYLE DETAIL PANEL
// ---------------------------------------------------------------------------

async function loadLocationData(name, lat, lon) {
  selectedLocation = { name, lat, lon };
  openLocationPanel(name, lat, lon);

  // Set loading placeholder values
  document.getElementById("panelLocName").textContent = name.split(",")[0];
  document.getElementById("panelLocSub").textContent = `${name} · Lat ${Number(lat).toFixed(4)}°, Lon ${Number(lon).toFixed(4)}°`;
  document.getElementById("panelRiskLabel").textContent = "⏳ CALCULATING RISK...";
  document.getElementById("panelRiskScore").textContent = "—";
  document.getElementById("panelRiskStrip").className = "panel-risk-strip moderate";

  try {
    const detail = await API.get(`/location/detail?name=${encodeURIComponent(name)}&lat=${lat}&lon=${lon}`);
    populateLocationPanel(detail);
  } catch (err) {
    console.warn("Backend API unavailable, using offline risk simulation:", err);
    // Instant fallback using local geotechnical & weather baseline
    const fallback = API.generateFallbackRisk(name, lat, lon);
    populateLocationPanel(fallback);
  }
}

async function loadCoordinateData(lat, lon) {
  try {
    const res = await API.get(`/location/resolve?lat=${lat}&lon=${lon}`);
    loadLocationData(res.name || `Lat ${lat.toFixed(3)}°, Lon ${lon.toFixed(3)}°`, lat, lon);
  } catch (e) {
    loadLocationData(`Lat ${lat.toFixed(3)}°, Lon ${lon.toFixed(3)}°`, lat, lon);
  }
}

function openLocationPanel(name, lat, lon) {
  const panel = document.getElementById("locationPanel");
  if (panel) {
    panel.classList.add("active");
  }
}

function closeLocationPanel() {
  const panel = document.getElementById("locationPanel");
  if (panel) {
    panel.classList.remove("active");
  }
}

function populateLocationPanel(data) {
  document.getElementById("panelLocName").textContent = (data.location || "Location").split(",")[0];
  document.getElementById("panelLocSub").textContent = `${data.region_label || data.region} · Lat ${Number(data.latitude).toFixed(4)}°, Lon ${Number(data.longitude).toFixed(4)}°`;

  const level = data.risk_level || "MODERATE";
  const score = data.risk_score != null ? data.risk_score : 50;

  const strip = document.getElementById("panelRiskStrip");
  strip.className = `panel-risk-strip ${level.toLowerCase()}`;
  document.getElementById("panelRiskLabel").textContent = `🔴 LANDSLIDE RISK: ${level}`;
  document.getElementById("panelRiskScore").textContent = `${score}%`;

  document.getElementById("panelRainfall").textContent = `${Number(data.rainfall_24h_mm || 0).toFixed(1)} mm`;
  document.getElementById("panelRainStatus").textContent = data.data_status === "NO_DATA" ? "Data Stale/Fallback" : (data.data_source || "Open-Meteo Live");

  document.getElementById("panelSoilMoisture").textContent = `${Number(data.soil_moisture_pct || 0).toFixed(1)}%`;
  document.getElementById("panelSlope").textContent = `${Number(data.slope_deg || 0).toFixed(1)}°`;
  document.getElementById("panelElevation").textContent = `Elevation: ${Math.round(data.elevation_m || 0)} m`;

  document.getElementById("panelTemp").textContent = `${Number(data.temperature_c || 22).toFixed(1)}°C`;
  document.getElementById("panelHumidity").textContent = `RH: ${Math.round(data.humidity_pct || 75)}%`;

  document.getElementById("panelPorePressure").textContent = `${Number(data.pore_pressure_kpa || 0).toFixed(2)} kPa`;
  document.getElementById("panelPoreType").textContent = data.pore_pressure_type === "measured" ? "Sensor Measured" : "Estimated Index";

  const mlProb = data.ml_probability != null ? Math.round(data.ml_probability * 100) : score;
  document.getElementById("panelMlProb").textContent = `${mlProb}%`;
  document.getElementById("panelFos").textContent = `FS: ${Number(data.factor_of_safety || 1.25).toFixed(2)}`;

  // Explainable AI factors
  const whyList = document.getElementById("panelWhyList");
  whyList.innerHTML = "";
  const reasons = data.why_explanation || [];
  if (reasons.length === 0) {
    whyList.innerHTML = `<li>Parameters are within normal regional boundaries.</li>`;
  } else {
    reasons.forEach(r => {
      const li = document.createElement("li");
      li.textContent = r;
      whyList.appendChild(li);
    });
  }

  // Active Physics Formula preview
  const formulaPwp = document.getElementById("panelFormulaPwp");
  const formulaText = document.getElementById("panelFormulaText");
  const pwpVal = Number(data.pore_pressure_kpa || 0).toFixed(2);
  const fosVal = Number(data.factor_of_safety || 1.25).toFixed(2);
  if (formulaPwp) formulaPwp.textContent = `u = ${pwpVal} kPa | FS = ${fosVal}`;
  if (formulaText) formulaText.textContent = `u = 9.81·h_w (${pwpVal} kPa) → FS = [${data.slope_deg || 35}° slope] = ${fosVal}`;

  // Freshness
  const timeStr = data.timestamp ? new Date(data.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Just now";
  document.getElementById("panelFreshness").textContent = `Updated: ${timeStr} IST · ${data.data_quality || 'LIVE'}`;

  // Link to assessment page with exact query
  const assessLink = document.getElementById("panelAssessLink");
  if (assessLink) {
    assessLink.href = `assessment.html?loc=${encodeURIComponent(data.location)}&lat=${data.latitude}&lon=${data.longitude}`;
  }
}

// ---------------------------------------------------------------------------
// LIVE NOW BUTTON ACTION
// ---------------------------------------------------------------------------

async function triggerLiveNow() {
  const btn = document.getElementById("btnLiveNow");
  const origHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.innerHTML = `<span class="pulse-dot"></span> Fetching Live...`;
    btn.disabled = true;
  }

  try {
    // 1. Recompute or refresh selected location if panel is open
    if (selectedLocation) {
      await loadLocationData(selectedLocation.name, selectedLocation.lat, selectedLocation.lon);
    }

    // 2. Trigger active layer refresh
    handleZoomLevelChange();

    // 3. Re-fetch hotspots
    const h = await API.get("/monitoring/hotspots");
    activeHotspots = h.hotspots || [];
    const badge = document.getElementById("statHotspotsBadge");
    if (badge) {
      badge.textContent = `${activeHotspots.length} Emerging Hotspots`;
    }
  } catch (err) {
    console.error("Live now update error:", err);
  } finally {
    if (btn) {
      btn.innerHTML = origHtml;
      btn.disabled = false;
    }
  }
}

// Make functions globally accessible for inline HTML callbacks
window.switchLayer = switchLayer;
window.zoomToNER = zoomToNER;
window.zoomToRegion = zoomToRegion;
window.closeLocationPanel = closeLocationPanel;
window.triggerLiveNow = triggerLiveNow;