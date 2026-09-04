function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}

function populateLocationSelect() {
  const select = document.getElementById("regLocation");
  select.innerHTML = DEMO_LOCATIONS
    .map((loc) => `<option>${esc(loc.name)}</option>`)
    .join("");
}

document.addEventListener("DOMContentLoaded", async () => {
  populateLocationSelect();
  document.getElementById("registerForm").onsubmit = registerCitizen;
  document.getElementById("sendOtpBtn").onclick = sendOtp;
  document.getElementById("verifyOtpBtn").onclick = verifyOtp;
  await loadActiveAlerts();
  // LIVE automatic refresh of the active warnings feed.
  setInterval(loadActiveAlerts, 20000);
});

async function registerCitizen(e) {
  e.preventDefault();
  const regName = document.getElementById("regName");
  const regEmail = document.getElementById("regEmail");
  const regLocation = document.getElementById("regLocation");
  const regMsg = document.getElementById("regMsg");
  const data = {
    name: regName.value.trim(),
    email: regEmail.value.trim().toLowerCase(),
    location: regLocation.value,
  };
  try {
    const r = await API.post("/sos/register", data);
    regMsg.innerHTML = `<span style="color:var(--green)">${esc(r.message)}</span>`;
    document.getElementById("otpEmail").value = regEmail.value.trim().toLowerCase();
    e.target.reset();
    populateLocationSelect();
  } catch (err) {
    regMsg.innerHTML = `<span style="color:var(--red)">Registration failed: ${esc(err.message)}</span>`;
  }
}

async function sendOtp() {
  const email = (document.getElementById("otpEmail").value || "").trim().toLowerCase();
  const otpMsg = document.getElementById("otpMsg");
  if (!email) { otpMsg.innerHTML = `<span style="color:var(--red)">Enter your email first.</span>`; return; }
  try {
    const r = await API.post("/auth/send-otp", { email });
    otpMsg.innerHTML = r.demo_otp
      ? `<span style="color:var(--green)">${esc(r.message)}</span>`
      : `<span style="color:var(--green)">${esc(r.message)}</span>`;
  } catch (err) {
    otpMsg.innerHTML = `<span style="color:var(--red)">${esc(err.message)}</span>`;
  }
}

async function verifyOtp() {
  const email = (document.getElementById("otpEmail").value || "").trim().toLowerCase();
  const code = (document.getElementById("otpCode").value || "").trim();
  const otpMsg = document.getElementById("otpMsg");
  if (!email || !code) { otpMsg.innerHTML = `<span style="color:var(--red)">Enter email and code.</span>`; return; }
  try {
    const r = await API.post("/auth/verify-otp", { email, code });
    otpMsg.innerHTML = `<span style="color:var(--green)">✅ ${esc(r.message)}</span>`;
  } catch (err) {
    otpMsg.innerHTML = `<span style="color:var(--red)">${esc(err.message)}</span>`;
  }
}

async function loadActiveAlerts() {
  const activeCountBadge = document.getElementById("activeCountBadge");
  const alertsFeedContainer = document.getElementById("alertsFeedContainer");
  try {
    const alerts = await API.get("/alerts");
    activeCountBadge.textContent = `${alerts.length} Active Warnings`;
    alertsFeedContainer.innerHTML = alerts.length
      ? alerts.map((a) => `
          <div class="factor-pill">
            <span><strong>${esc(a.location)}</strong><br><small>${esc(new Date(a.timestamp).toLocaleString())}</small></span>
            <span class="badge badge-${esc(String(a.risk_level).toLowerCase())}">${esc(a.risk_level)} · ${esc(a.risk_score)}%</span>
          </div>`).join("")
      : '<div class="empty">No high-risk assessments stored yet.</div>';
  } catch (e) {
    activeCountBadge.textContent = "Unavailable";
    alertsFeedContainer.innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  }
}