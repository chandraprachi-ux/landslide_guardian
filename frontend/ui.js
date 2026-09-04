/* Shared UI + administrator session lock */
document.addEventListener("DOMContentLoaded", () => {
  const isAdmin = sessionStorage.getItem("lg_admin_token");
  const page = location.pathname.split("/").pop() || "index.html";

  // Once the admin console is open, public pages are deliberately blocked until logout.
  if (isAdmin && page !== "admin.html" && page !== "admin-login.html") {
    location.replace("admin.html");
    return;
  }

  const nav = document.querySelector(".navbar");
  if (nav) {
    const actions = document.createElement("div");
    actions.className = "nav-actions";
    if (isAdmin) {
      actions.innerHTML = `<span class="api-status-badge">ADMIN SESSION</span><a class="nav-admin" href="admin.html">Admin Console</a>`;
    } else {
      actions.innerHTML = `<a class="nav-admin" href="admin-login.html">Admin</a>`;
    }
    nav.appendChild(actions);
  }

  const footer = document.querySelector("footer");
  if (footer) {
    footer.innerHTML = `
      <div class="footer-grid">
        <div><div class="footer-title">⛰️ Landslide Guardian</div>
          <p style="font-size:.78rem;max-width:280px">AI-based landslide risk monitoring for North-Eastern India with a software-only SIH demonstration and future sensor compatibility.</p>
        </div>
        <div><div class="footer-title">Explore</div><ul class="footer-links">
          <li><a href="index.html">Home</a></li><li><a href="dashboard.html">Dashboard</a></li><li><a href="assessment.html">Risk Assessment</a></li><li><a href="map.html">Risk Map</a></li><li><a href="history.html">Historical Context</a></li></ul>
        </div>
        <div><div class="footer-title">Emergency</div><ul class="footer-links">
          <li><a href="alerts.html">Email SOS</a></li><li><a href="https://ndma.gov.in/" target="_blank" rel="noopener">NDMA</a></li><li><a href="https://sachet.ndma.gov.in/" target="_blank" rel="noopener">SACHET</a></li><li><a href="https://www.gsi.gov.in/" target="_blank" rel="noopener">GSI</a></li></ul>
        </div>
        <div><div class="footer-title">Helplines</div><div class="helpline-list">
          <span>National Emergency</span><strong>112</strong><span>Disaster Management</span><strong>1070</strong>
          <span>Police</span><strong>100</strong><span>Fire</span><strong>101</strong><span>Ambulance</span><strong>108</strong>
        </div></div>
      </div>
      <div class="footer-bottom"><span>© 2026 Landslide Guardian · SIH software prototype</span><span>For life-threatening emergencies, call 112 and follow official instructions.</span></div>`;
  }

  if (!document.querySelector(".floating-assist")) {
    const wrap = document.createElement("div");
    wrap.className = "floating-assist";
    wrap.innerHTML = `
      <div class="assist-label">Guardian Assistant</div>
      <button class="assist-button" id="assistToggle" aria-label="Open assistant">24/7<br><small>HELP</small></button>
      <div class="assist-panel" id="assistPanel">
        <div class="assist-head"><strong>🛡️ Guardian</strong><button id="assistClose">✕</button></div>
        <div class="assist-messages" id="assistMessages"><div class="msg bot">Ask me about risk, weather, the four trigger criteria, or safety actions.</div></div>
        <form class="assist-form" id="assistForm"><input id="assistInput" class="form-control" placeholder="Ask about landslide risk…" autocomplete="off"><button>Send</button></form>
      </div>`;
    document.body.appendChild(wrap);
    const panel = document.getElementById("assistPanel");
    document.getElementById("assistToggle").onclick=()=>panel.classList.toggle("open");
    document.getElementById("assistClose").onclick=()=>panel.classList.remove("open");
    document.getElementById("assistForm").onsubmit=async e=>{
      e.preventDefault();
      const input=document.getElementById("assistInput"), text=input.value.trim(); if(!text)return;
      addMsg(text,"user"); input.value="";
      let reply="";
      try { reply=(await API.post("/assistant/chat",{message:text})).reply; } catch(_){}
      addMsg(reply || localAssistant(text),"bot");
    };
  }
});

function addMsg(text, kind) {
  const box=document.getElementById("assistMessages"); if(!box)return;
  const el=document.createElement("div"); el.className=`msg ${kind}`; el.textContent=text; box.appendChild(el); box.scrollTop=box.scrollHeight;
}
function localAssistant(q) {
  const s = q.toLowerCase();
  if (s.includes("pore") || s.includes("pressure") || s.includes("formula")) {
    return "Pore-Water Pressure Formula:\nu = γ_w · h_w = 9.81 kN/m³ · h_w\nEffective water head h_w is derived from the Antecedent Rainfall Index (ARI ≈ R24 + 0.5·R72) and soil saturation. Rising pore pressure directly counteracts normal stress (σ' = σ_n - u), lowering shear strength.";
  }
  if (s.includes("factor of safety") || s.includes("fos") || s.includes("mohr")) {
    return "Mohr-Coulomb Factor of Safety:\nFS = [c' + (σ_n - u)·tan(φ')] / τ_shear\nWhere c' is effective cohesion (14-28 kPa), φ' is friction angle (26°-32°), and τ_shear is gravitational driving stress. FS < 1.0 indicates critical slope failure.";
  }
  if (s.includes("50,000") || s.includes("train") || s.includes("accuracy")) {
    return "The ML model is an ExtraTreesClassifier trained on 55,000 physical samples modeled across the 8 NER states, achieving high precision in separating stable conditions from rainfall-triggered slope failures.";
  }
  if (s.includes("risk") || s.includes("calculate") || s.includes("score")) {
    return "Final Risk Score (0-100%) = 0.55 · (ML Probability · 100) + 0.25 · Geotechnical Score + 0.20 · Criteria Stress. It blends physical limit equilibrium with our 55k-sample ML model.";
  }
  if (s.includes("sync") || s.includes("collide") || s.includes("map") || s.includes("different")) {
    return "Both the Risk Map and Risk Assessment pages connect to the same calculate_risk_assessment engine, ensuring identical coordinates, pore pressure, and risk numbers across all views.";
  }
  if (s.includes("weather")) {
    return "The system queries live atmospheric data from Open-Meteo for the selected coordinates, tracking 24h & 72h precipitation, temperature, humidity, and soil moisture.";
  }
  if (s.includes("sos") || s.includes("alert")) {
    return "Critical alerts trigger automatic SOS notifications to registered community members in the affected region.";
  }
  return "I am the Guardian AI Assistant. Ask me about our pore pressure calculations (u = γ_w · h_w), Mohr-Coulomb Factor of Safety, or our 55,000-sample trained ML engine.";
}

