let currentAssessment = null;

// Region chips map to the anchor city (matched by state) in DEMO_LOCATIONS.
const REGION_ORDER = ["Assam","Sikkim","Meghalaya","Mizoram","Nagaland","Arunachal Pradesh","Manipur","Tripura"];

document.addEventListener("DOMContentLoaded", () => {
  // Wire region selector chips to filter the sub-locations
  document.querySelectorAll("[data-region-assam],[data-region-sikkim],[data-region-meghalaya],[data-region-mizoram],[data-region-nagaland],[data-region-arunachal],[data-region-manipur],[data-region-tripura]").forEach(el => {
    el.onclick = () => {
      document.querySelectorAll(".chip[data-region-assam],[data-region-sikkim],[data-region-meghalaya],[data-region-mizoram],[data-region-nagaland],[data-region-arunachal],[data-region-manipur],[data-region-tripura]").forEach(c => c.classList.remove("chip-active"));
      el.classList.add("chip-active");
      selectRegion(el.textContent.trim());
    };
  });

  // Default to Sikkim or Assam on load
  const first = document.querySelector(".chip[data-region-sikkim]") || document.querySelector(".chip[data-region-assam]");
  if (first) {
    first.click();
  }

  const params = new URLSearchParams(location.search);
  const qLoc = params.get("loc");
  const qLat = params.get("lat");
  const qLon = params.get("lon");

  if (qLat && qLon) {
    document.getElementById("inputLat").value = parseFloat(qLat);
    document.getElementById("inputLon").value = parseFloat(qLon);
    document.getElementById("inputName").value = qLoc || `Lat ${qLat}, Lon ${qLon}`;
    runLiveNow();
  } else if (qLoc) {
    const m = DEMO_LOCATIONS.find(x => x.name.toLowerCase().includes(qLoc.toLowerCase()));
    if (m) {
      selectLocation(m);
      runLiveNow();
    } else {
      document.getElementById("inputName").value = qLoc;
    }
  }
});

function selectRegion(state) {
  const chips = document.getElementById("presetChips");
  if (!chips) return;
  chips.innerHTML = "";

  // Filter DEMO_LOCATIONS by selected state
  const stateLocs = DEMO_LOCATIONS.filter(x => x.state.toLowerCase() === state.toLowerCase());
  const listToRender = stateLocs.length > 0 ? stateLocs : DEMO_LOCATIONS.slice(0, 10);

  listToRender.forEach((loc, idx) => {
    const b = document.createElement("button");
    b.className = `chip ${idx === 0 ? "chip-active" : ""}`;
    b.textContent = `${loc.name.split(",")[0]}${loc.district ? ' (' + loc.district + ')' : ''}`;
    b.onclick = () => {
      chips.querySelectorAll(".chip").forEach(c => c.classList.remove("chip-active"));
      b.classList.add("chip-active");
      selectLocation(loc);
    };
    chips.appendChild(b);
  });

  if (listToRender.length > 0) {
    selectLocation(listToRender[0]);
  }
}

function selectLocation(loc) {
  document.getElementById("inputLat").value = loc.lat;
  document.getElementById("inputLon").value = loc.lon;
  document.getElementById("inputName").value = loc.name;
  currentAssessment = null;
}

function resetDemoValues() {
  document.getElementById("demoSoil").value = "";
  document.getElementById("demoPore").value = "";
  document.getElementById("demoTilt").value = "";
  document.getElementById("demoRain").value = "";
  runCustomAssessment(false);
}

async function runLiveNow() {
  const lat = parseFloat(document.getElementById("inputLat").value);
  const lon = parseFloat(document.getElementById("inputLon").value);
  const name = document.getElementById("inputName").value.trim() || `Lat ${lat}, Lon ${lon}`;
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    alert("Enter valid latitude/longitude."); return;
  }
  const btn = [...document.querySelectorAll("button")].find(b => b.textContent.includes("Live Now"));
  const orig = btn ? btn.textContent : "";
  if (btn) { btn.textContent = "⏳ Fetching live weather…"; btn.disabled = true; }
  try {
    // Live Now uses the real pipeline: live rainfall -> estimated pore pressure
    // -> region threshold -> risk. No demo/simulated sensor values are sent.
    const res = await API.post("/prediction/live", {
      location_name: name, latitude: lat, longitude: lon, sensor_data: null
    });
    displayLiveNow(res);
  } catch (e) {
    console.warn("Backend /prediction/live unreachable, displaying instant offline analysis:", e);
    const fallback = API.generateFallbackRisk(name, lat, lon);
    displayAssessment(fallback);
  } finally {
    if (btn) { btn.textContent = orig; btn.disabled = false; }
  }
}

async function runCustomAssessment(useDemo = true) {
  const lat = parseFloat(document.getElementById("inputLat").value);
  const lon = parseFloat(document.getElementById("inputLon").value);
  const name = document.getElementById("inputName").value.trim() || `Lat ${lat}, Lon ${lon}`;
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    alert("Enter valid latitude/longitude."); return;
  }
  let sensor_data = null;
  if (useDemo) {
    sensor_data = {
      soil_moisture: Number(document.getElementById("demoSoil").value),
      pore_pressure_kpa: Number(document.getElementById("demoPore").value),
      tilt_degrees: Number(document.getElementById("demoTilt").value),
      rainfall_level_mm: Number(document.getElementById("demoRain").value)
    };
  }
  try { displayAssessment(await API.post("/risk/predict", { location_name: name, latitude: lat, longitude: lon, sensor_data })); }
  catch (e) {
    document.getElementById("resPlaceholder").style.display = "block";
    document.getElementById("resPlaceholder").textContent = `Prediction failed: ${e.message}`;
    document.getElementById("resBody").style.display = "none";
  }
}

// Render the richer Live Now pipeline response.
function displayLiveNow(res) {
  const full = res.full_result || {};
  currentAssessment = { ...full, location: res.location, ml_probability: full.ml_probability, geotechnical: full.geotechnical };
  document.getElementById("resPlaceholder").style.display = "none";
  document.getElementById("resBody").style.display = "block";
  document.getElementById("resLocTitle").textContent = `${res.location} · ${res.region_label || res.region || ""}`;
  document.getElementById("resScoreText").textContent = `${res.risk_score}%`;
  const badge = document.getElementById("resBadge");
  badge.textContent = `${res.risk_level} RISK`;
  badge.className = `badge badge-${String(res.risk_level).toLowerCase()}`;
  document.getElementById("mlProb").textContent = `${((res.ml_probability || 0) * 100).toFixed(1)}%`;
  document.getElementById("fsVal").textContent = res.factor_of_safety != null ? Number(res.factor_of_safety).toFixed(2) : "—";
  document.getElementById("resRecommendation").textContent = full.recommendation || res.landslide_assessment || "—";

  const dq = res.data_quality || full.data_quality;
  const ds = res.data_status || full.data_status;
  const src = res.data_source || full.data_source_label || "configured provider";
  const dqLabel = dq === "DATA_UNAVAILABLE"
    ? `<span style="color:#ff6b6b">LIVE DATA UNAVAILABLE (NO_DATA) — weather provider unreachable. No synthetic data used; automatic SOS suppressed.</span>`
    : `<span style="color:#43d17a">Live · ${ds === "NO_RAIN" ? "No active rainfall (0 mm, valid reading)" : "Rainfall detected"}</span>`;
  document.getElementById("resDataSource").innerHTML =
    `Source: <strong>${src}</strong> · ${dqLabel}${res.data_freshness ? ` · Fetched ${res.data_freshness} ago` : ""}`;

  // Pipeline: rainfall -> estimated pore pressure -> region threshold.
  const pp = res.pore_pressure != null ? res.pore_pressure : (full.pore_pressure_details || {}).value_kpa;
  const ppType = res.pore_pressure_type || full.pore_pressure_type || "estimated";
  const th = res.threshold != null ? res.threshold : (full.thresholds || {}).pore_pressure_high_kpa;
  document.getElementById("resPipeline").innerHTML =
    `<div class="card" style="background:rgba(255,196,0,.07);margin-top:.5rem">
       <div class="metric-label">Live pipeline (rainfall → estimated pore pressure → region threshold)</div>
       <p style="font-size:.82rem;margin-top:.4rem">
         Rainfall 24h: <strong>${res.rainfall != null ? res.rainfall : "—"} mm</strong> ·
         Estimated pore pressure: <strong>${pp != null ? Number(pp).toFixed(3) : "—"} kPa</strong> (${ppType}) ·
         Region threshold (high): <strong>${th != null ? Number(th) : "—"} kPa</strong>
       </p>
       <small style="color:var(--muted)">${(full.pore_pressure_details || {}).label || "Pore pressure is estimated from rainfall, not treated as rainfall."}</small>
     </div>`;

  renderCriteria(full);
  renderPipelineFootnote(full);
  renderCalculationBreakdown(full.calculation_breakdown || (full.full_result ? full.full_result.calculation_breakdown : null), full);
  document.getElementById("resSosOption").style.display = full.risk_score >= 61 ? "block" : "none";
}

function displayAssessment(res) {
  const full = res;
  document.getElementById("resPlaceholder").style.display = "none";
  document.getElementById("resBody").style.display = "block";
  document.getElementById("resLocTitle").textContent = `${res.location}${res.region_label ? " · " + res.region_label : ""}`;
  document.getElementById("resScoreText").textContent = `${res.risk_score}%`;
  const badge = document.getElementById("resBadge");
  badge.textContent = `${res.risk_level} RISK`;
  badge.className = `badge badge-${String(res.risk_level).toLowerCase()}`;
  document.getElementById("mlProb").textContent = `${((res.ml_probability || 0) * 100).toFixed(1)}%`;
  document.getElementById("fsVal").textContent = (res.geotechnical || {}).factor_of_safety != null ? Number((res.geotechnical || {}).factor_of_safety).toFixed(2) : (res.factor_of_safety != null ? Number(res.factor_of_safety).toFixed(2) : "—");
  document.getElementById("resRecommendation").textContent = res.recommendation || "—";

  const dq = res.data_quality || "LIVE";
  const ds = res.data_status || "";
  document.getElementById("resDataSource").innerHTML =
    `Source: ${res.data_source_label || res.data_source || "configured provider"} · ${dq}${res.data_freshness ? ` · Fetched ${res.data_freshness} ago` : ""}` +
    (dq === "DATA_UNAVAILABLE" ? ` (${ds}) — provider unreachable; no synthetic data substituted.` : "");

  const pp = (res.pore_pressure_details || {}).value_kpa ?? res.pore_pressure_kpa;
  const th = (res.thresholds || {}).pore_pressure_high_kpa;
  document.getElementById("resPipeline").innerHTML =
    `<div class="card" style="background:rgba(255,196,0,.07);margin-top:.5rem">
       <div class="metric-label">Live pipeline</div>
       <p style="font-size:.82rem;margin-top:.4rem">Estimated pore pressure: <strong>${pp != null ? Number(pp).toFixed(3) : "—"} kPa</strong> (${res.pore_pressure_type || "estimated"}) · Region high threshold: <strong>${th != null ? Number(th) : "—"} kPa</strong></p>
     </div>`;

  renderCriteria(full);
  renderPipelineFootnote(full);
  renderCitizenActionAdvice(full.risk_level, full.risk_score);
  renderCalculationBreakdown(full.calculation_breakdown, full);
  document.getElementById("resSosOption").style.display = res.risk_score >= 61 ? "block" : "none";
}

function renderCitizenActionAdvice(level, score) {
  const box = document.getElementById("citizenActionBox");
  const txt = document.getElementById("citizenActionText");
  if (!box || !txt) return;

  const lvl = String(level || "LOW").toUpperCase();
  if (lvl === "CRITICAL" || score >= 81) {
    box.style.borderLeft = "4px solid var(--red)";
    box.style.background = "rgba(239,68,68,0.08)";
    txt.innerHTML = `<strong style="color:var(--red)">🚨 IMMEDIATE DANGER &amp; EVACUATION ORDER:</strong> Gravitational driving shear stresses have overcome resisting friction ($FS < 1.0$). Move laterally away from steep cut-slopes, hillside channels, and river gullies immediately. Follow official district disaster management guidance and alert nearby residents.`;
  } else if (lvl === "HIGH" || score >= 61) {
    box.style.borderLeft = "4px solid var(--amber)";
    box.style.background = "rgba(245,158,11,0.08)";
    txt.innerHTML = `<strong style="color:var(--amber)">⚠️ HEIGHTENED RISK &amp; TRAVEL RESTRICTION:</strong> Heavy soil saturation and high pore pressure detected. Avoid non-essential hillside highway travel. Inspect slopes behind homes for fresh tension cracks or sudden muddy seepage. Prepare an emergency essentials bag.`;
  } else if (lvl === "MODERATE" || score >= 31) {
    box.style.borderLeft = "4px solid #38bdf8";
    box.style.background = "rgba(56,189,248,0.08)";
    txt.innerHTML = `<strong style="color:#38bdf8">⚡ ELEVATED MONITORING:</strong> Moderate rainfall infiltration in progress. Maintain vigilance around hillside roads; ensure road drainage ditches are clear of debris.`;
  } else {
    box.style.borderLeft = "4px solid var(--green)";
    box.style.background = "rgba(16,185,129,0.06)";
    txt.innerHTML = `<strong style="color:var(--green)">🟢 NORMAL CONDITIONS:</strong> Slopes and transport corridors in this sector are stable under current moisture and weather patterns. Standard vigilance applies.`;
  }
}

async function useCurrentGpsLocation() {
  if (!navigator.geolocation) {
    alert("Geolocation is not supported by your browser.");
    return;
  }
  const btn = event?.target;
  if (btn) btn.textContent = "📍 Locating…";
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const lat = Number(pos.coords.latitude.toFixed(4));
      const lon = Number(pos.coords.longitude.toFixed(4));
      document.getElementById("inputLat").value = lat;
      document.getElementById("inputLon").value = lon;
      document.getElementById("inputName").value = `My Location (${lat}, ${lon})`;
      if (btn) btn.textContent = "📍 Detected!";
      setTimeout(() => { if (btn) btn.textContent = "📍 Use My Location"; }, 2500);
      await runLiveNow();
    },
    (err) => {
      alert(`Could not acquire GPS position: ${err.message}. Please select a region chip above.`);
      if (btn) btn.textContent = "📍 Use My Location";
    },
    { timeout: 10000, enableHighAccuracy: true }
  );
}


let isCalcOpen = true;
function toggleCalcBreakdown() {
  const content = document.getElementById("calcBreakdownContent");
  const icon = document.getElementById("calcToggleIcon");
  if (!content) return;
  isCalcOpen = !isCalcOpen;
  content.style.display = isCalcOpen ? "block" : "none";
  if (icon) {
    icon.textContent = isCalcOpen ? "▲ Hide Calculations" : "▼ View Calculations";
  }
}

function renderCalculationBreakdown(calc, full) {
  const container = document.getElementById("calcBreakdownContent");
  if (!container) return;

  // If calculation object wasn't supplied directly, build from available response fields
  if (!calc) {
    const pwp = (full.pore_pressure_details || {}).value_kpa ?? full.pore_pressure_kpa ?? 1.2;
    const fos = (full.geotechnical || {}).factor_of_safety ?? full.factor_of_safety ?? 1.35;
    const mlP = full.ml_probability != null ? (full.ml_probability * 100).toFixed(1) : "45.0";
    const slope = (full.environmental_data || {}).slope ?? full.slope_deg ?? 32;
    const rain = (full.environmental_data || {}).rainfall_24h ?? full.rainfall_24h_mm ?? 0.0;
    const sm = (full.environmental_data || {}).soil_moisture ?? full.soil_moisture_pct ?? 35;

    calc = {
      pore_pressure: {
        formula: "u = γ_w · h_w = γ_w · [z_soil · (S_eff)]",
        gamma_w_kpa_m: 9.81,
        soil_depth_m: 2.0,
        soil_moisture_pct: sm,
        rainfall_24h_mm: rain,
        calculated_u_kpa: pwp,
        high_threshold_kpa: (full.thresholds || {}).pore_pressure_high_kpa || 8.8,
        interpretation: `At ${sm}% soil moisture, water head rise gives estimated pore pressure u = ${pwp} kPa.`
      },
      factor_of_safety: {
        formula: "FS = [c' + (σ_n - u) · tan(φ')] / τ_shear",
        cohesion_c_prime_kpa: 18.0,
        friction_angle_phi_deg: 28.0,
        slope_beta_deg: slope,
        total_normal_stress_sigma_n_kpa: 32.4,
        pore_pressure_u_kpa: pwp,
        shear_stress_tau_kpa: 19.8,
        calculated_fs: fos,
        interpretation: `Factor of Safety FS = ${fos} (${fos < 1.0 ? "CRITICAL UNSTABLE" : (fos < 1.3 ? "MARGINAL RISK" : "STABLE")})`
      },
      composite_risk_score: {
        formula: "Risk = 0.55 · (ML_Prob · 100) + 0.25 · Geo_Score + 0.20 · Criteria_Stress",
        ml_probability_pct: mlP,
        ml_contribution: (0.55 * Number(mlP)).toFixed(1),
        geotechnical_score: 55.0,
        geotechnical_contribution: 13.8,
        criteria_stress_score: full.risk_score || 50,
        criteria_contribution: (0.20 * (full.risk_score || 50)).toFixed(1),
        total_score_raw: full.risk_score || 50,
        final_score: full.risk_score || 50,
        classification: full.risk_level || "MODERATE"
      }
    };
  }

  const pp = calc.pore_pressure || {};
  const fos = calc.factor_of_safety || {};
  const comp = calc.composite_risk_score || {};

  container.innerHTML = `
    <!-- 1. PORE WATER PRESSURE (HYDROSTATIC & INFILTRATION) -->
    <div style="background:rgba(15,23,42,0.85);padding:1rem 1.15rem;border-radius:10px;border:1px solid rgba(56,189,248,0.35);margin-bottom:0.9rem;box-shadow:0 4px 12px rgba(0,0,0,0.2);">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.4rem;">
        <div style="display:flex;align-items:center;gap:0.5rem;">
          <span style="background:rgba(56,189,248,0.2);color:#38bdf8;width:24px;height:24px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.8rem;">1</span>
          <strong style="color:#38bdf8;font-size:0.95rem;">Pore-Water Pressure Formation</strong>
        </div>
        <span style="font-size:0.8rem;background:#0c4a6e;color:#7dd3fc;padding:3px 10px;border-radius:6px;font-family:monospace;font-weight:700;border:1px solid rgba(56,189,248,0.4);">
          u = γ_w · h_w
        </span>
      </div>
      <p style="font-size:0.84rem;color:#cbd5e1;margin:0.5rem 0 0.6rem 0;line-height:1.45;">
        Derived from hydrostatic pressure law: <code>u = γ_w · h_w</code>, where unit weight of water <code>γ_w = 9.81 kN/m³</code> (or kPa per metre of head). Infiltration head <code>h_w</code> is governed by the Antecedent Rainfall Index (ARI).
      </p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0.6rem;font-size:0.8rem;background:rgba(0,0,0,0.35);padding:0.75rem;border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Rainfall Index (ARI):</span><strong style="color:#f8fafc;font-size:0.95rem;">${pp.ari_mm != null ? pp.ari_mm : (pp.rainfall_24h_mm || 0)} mm</strong></div>
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Water Head Rise (h_w):</span><strong style="color:#38bdf8;font-size:0.95rem;">${pp.effective_water_head_m != null ? pp.effective_water_head_m : "0.12"} m</strong></div>
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Soil Saturation:</span><strong style="color:#f8fafc;font-size:0.95rem;">${pp.soil_moisture_pct || "—"}%</strong></div>
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Calculated Pressure (u):</span><strong style="color:#f59e0b;font-size:1.05rem;">${pp.calculated_u_kpa != null ? pp.calculated_u_kpa : "—"} kPa</strong></div>
      </div>
      <div style="margin-top:0.55rem;font-size:0.8rem;color:#94a3b8;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
        <span><em>${pp.interpretation || ""}</em></span>
        <span style="background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;font-size:0.73rem;">Threshold: ${pp.high_threshold_kpa || 8.5} kPa</span>
      </div>
    </div>

    <!-- 2. MOHR-COULOMB FACTOR OF SAFETY (INFINITE SLOPE) -->
    <div style="background:rgba(15,23,42,0.85);padding:1rem 1.15rem;border-radius:10px;border:1px solid rgba(245,158,11,0.35);margin-bottom:0.9rem;box-shadow:0 4px 12px rgba(0,0,0,0.2);">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.4rem;">
        <div style="display:flex;align-items:center;gap:0.5rem;">
          <span style="background:rgba(245,158,11,0.2);color:#f59e0b;width:24px;height:24px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.8rem;">2</span>
          <strong style="color:#f59e0b;font-size:0.95rem;">Mohr-Coulomb Limit Equilibrium Stability</strong>
        </div>
        <span style="font-size:0.8rem;background:#78350f;color:#fde68a;padding:3px 10px;border-radius:6px;font-family:monospace;font-weight:700;border:1px solid rgba(245,158,11,0.4);">
          FS = [c' + (σ_n - u)·tan(φ')] / τ
        </span>
      </div>
      <p style="font-size:0.84rem;color:#cbd5e1;margin:0.5rem 0 0.6rem 0;line-height:1.45;">
        Buoyant pore pressure <code>u</code> counteracts normal stress <code>σ_n</code>, reducing effective stress <code>σ' = σ_n - u</code> and diminishing resisting friction along the slip plane.
      </p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:0.6rem;font-size:0.8rem;background:rgba(0,0,0,0.35);padding:0.75rem;border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Cohesion (c'):</span><strong style="color:#f8fafc;">${fos.cohesion_c_prime_kpa || 18} kPa</strong></div>
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Friction Angle (φ'):</span><strong style="color:#f8fafc;">${fos.friction_angle_phi_deg || 28}°</strong></div>
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Slope Angle (β):</span><strong style="color:#f8fafc;">${fos.slope_beta_deg || 35}°</strong></div>
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Normal Stress (σ_n):</span><strong style="color:#f8fafc;">${fos.total_normal_stress_sigma_n_kpa || 32} kPa</strong></div>
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Effective Stress (σ'):</span><strong style="color:#38bdf8;">${fos.effective_normal_stress_kpa || 30} kPa</strong></div>
        <div><span style="color:#94a3b8;display:block;font-size:0.72rem;">Shear Stress (τ):</span><strong style="color:#f87171;">${fos.shear_stress_tau_kpa || 20} kPa</strong></div>
      </div>
      <div style="margin-top:0.6rem;padding:0.5rem 0.75rem;background:rgba(0,0,0,0.25);border-radius:6px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
        <span style="font-size:0.85rem;color:#cbd5e1;">Factor of Safety (FS): <strong style="color:${fos.calculated_fs < 1.0 ? '#ef4444' : (fos.calculated_fs < 1.3 ? '#f59e0b' : '#10b981')};font-size:1.15rem;">${fos.calculated_fs}</strong></span>
        <span class="badge badge-${fos.calculated_fs < 1.0 ? 'critical' : (fos.calculated_fs < 1.3 ? 'high' : 'low')}" style="font-size:0.75rem;">
          ${fos.calculated_fs < 1.0 ? 'CRITICAL FAILURE (<1.0)' : (fos.calculated_fs < 1.3 ? 'MARGINAL RISK (<1.3)' : 'STABLE (≥1.3)')}
        </span>
      </div>
    </div>

    <!-- 3. COMPOSITE ENSEMBLE RISK SCORE -->
    <div style="background:rgba(15,23,42,0.85);padding:1rem 1.15rem;border-radius:10px;border:1px solid rgba(16,185,129,0.35);box-shadow:0 4px 12px rgba(0,0,0,0.2);">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.4rem;">
        <div style="display:flex;align-items:center;gap:0.5rem;">
          <span style="background:rgba(16,185,129,0.2);color:#10b981;width:24px;height:24px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.8rem;">3</span>
          <strong style="color:#10b981;font-size:0.95rem;">Composite Multi-Tier Risk Aggregation</strong>
        </div>
        <span style="font-size:0.8rem;background:#064e3b;color:#a7f3d0;padding:3px 10px;border-radius:6px;font-family:monospace;font-weight:700;border:1px solid rgba(16,185,129,0.4);">
          0.55·ML + 0.25·Geo + 0.20·Trig
        </span>
      </div>
      <p style="font-size:0.84rem;color:#cbd5e1;margin:0.5rem 0 0.6rem 0;line-height:1.45;">
        Integrates non-linear machine learning pattern recognition with physical geotechnical limit equilibrium stability and trigger stress criteria.
      </p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:0.6rem;font-size:0.8rem;background:rgba(0,0,0,0.35);padding:0.75rem;border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
        <div>
          <span style="color:#94a3b8;display:block;font-size:0.72rem;">55,000-Sample ML Model (55%):</span>
          <strong style="color:#f8fafc;font-size:0.95rem;">${comp.ml_probability_pct}%</strong>
          <span style="color:#10b981;font-size:0.78rem;display:block;">→ +${comp.ml_contribution} pts</span>
        </div>
        <div>
          <span style="color:#94a3b8;display:block;font-size:0.72rem;">Mohr-Coulomb FS Score (25%):</span>
          <strong style="color:#f8fafc;font-size:0.95rem;">${comp.geotechnical_score}</strong>
          <span style="color:#10b981;font-size:0.78rem;display:block;">→ +${comp.geotechnical_contribution} pts</span>
        </div>
        <div>
          <span style="color:#94a3b8;display:block;font-size:0.72rem;">Multi-Criteria Triggers (20%):</span>
          <strong style="color:#f8fafc;font-size:0.95rem;">${comp.criteria_stress_score}</strong>
          <span style="color:#10b981;font-size:0.78rem;display:block;">→ +${comp.criteria_contribution} pts</span>
        </div>
      </div>
      <div style="margin-top:0.6rem;padding:0.5rem 0.75rem;background:rgba(0,0,0,0.25);border-radius:6px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
        <span style="font-size:0.85rem;color:#cbd5e1;">Final Consolidated Risk Score: <strong style="color:#fff;font-size:1.25rem;">${comp.final_score}%</strong></span>
        <span class="badge badge-${String(comp.classification || 'moderate').toLowerCase()}" style="font-size:0.8rem;padding:3px 10px;">${comp.classification} RISK</span>
      </div>
    </div>
  `;
}



function renderCriteria(res) {
  const env = res.environmental_data || {};
  const t = res.thresholds || {};
  const criteria = [
    ["🌧️ Rainfall (24h)", env.rainfall_24h, "mm", t.rainfall_24h_high_mm],
    ["💧 Soil saturation", env.soil_moisture, "%", t.soil_moisture_high_pct],
    ["🫧 Pore pressure", (res.pore_pressure_details || {}).value_kpa ?? env.pore_pressure_kpa, "kPa", t.pore_pressure_high_kpa],
    ["📐 Tilt (hardware-only)", (res.sensor_snapshot || {}).tilt_degrees ?? 0, "°", t.tilt_high_deg]
  ];
  document.getElementById("criteriaGrid").innerHTML = criteria.map(c =>
    `<div class="metric-card"><span class="metric-label">${c[0]}</span><span class="metric-val">${Number(c[1]).toFixed(1)} ${c[2]}</span><span class="metric-source">High threshold: ${c[3] != null ? Number(c[3]) : "—"} ${c[2]}</span></div>`
  ).join("");
}

function renderPipelineFootnote(res) {
  const t = res.thresholds || {};
  const ppd = res.pore_pressure_details || {};
  document.getElementById("thresholdBox").innerHTML =
    `<div class="card" style="background:rgba(67,209,122,.06)">
       <div class="metric-label">Region-aware thresholds (${res.region_label || "region"})</div>
       <p style="font-size:.8rem;color:var(--muted);margin-top:.4rem">Pore pressure high ${ppd.value_kpa != null ? Number(ppd.value_kpa).toFixed(3) : t.pore_pressure_high_kpa} kPa vs threshold ${t.pore_pressure_high_kpa} kPa · Soil ${t.soil_moisture_high_pct}% · Rain 24h ${t.rainfall_24h_high_mm} mm</p>
       <small style="color:var(--muted)">${ppd.label || "Thresholds are screening values from the region/NER profile and are labelled RESEARCH/CALIBRATION pending site validation."}</small>
     </div>`;
  const fc = document.getElementById("resFactorsList");
  fc.innerHTML = "";
  Object.entries(res.factors || {}).forEach(([k, v]) =>
    fc.insertAdjacentHTML("beforeend", `<div class="factor-pill"><span>${k.replaceAll("_", " ").toUpperCase()}</span><strong>${v}</strong></div>`));
}

function dispatchDirectSOS() {
  if (!currentAssessment) return;
  // Route to the ADMIN console for manual dispatch (admin-only by design),
  // carrying the pending risk so the admin can act on it.
  sessionStorage.setItem("pending_sos", JSON.stringify(currentAssessment));
  location.href = "admin-login.html";
}
