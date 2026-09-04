/**
 * LANDSLIDE GUARDIAN — History Logs
 * Uses actual risk assessments stored in MongoDB Atlas.
 */

document.addEventListener("DOMContentLoaded", async () => {
  await renderHistory();
});

async function renderHistory() {
  try {
    const records = await API.get("/risk/all");
    renderHistoryChart(records);
    renderHistoryTable(records);
  } catch (error) {
    console.error(error);
    const tbody = document.getElementById("historyTableBody");
    tbody.innerHTML = `<tr><td colspan="5" style="padding:1rem;">Could not load history from the backend.</td></tr>`;
  }
}

function renderHistoryChart(records) {
  const ctx = document.getElementById("historyChart").getContext("2d");

  const latest = records.slice(0, 10).reverse();

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: latest.map(r => {
        const date = new Date(r.timestamp);
        return `${r.location} (${date.toLocaleDateString()})`;
      }),
      datasets: [{
        label: "Calculated Risk Score (%)",
        data: latest.map(r => r.risk_score),
        backgroundColor: latest.map(r => {
          const colors = {
            CRITICAL: "#ef4444",
            HIGH: "#f97316",
            MODERATE: "#eab308",
            LOW: "#10b981"
          };
          return colors[r.risk_level] || "#38bdf8";
        })
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: "#334155" } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function renderHistoryTable(records) {
  const tbody = document.getElementById("historyTableBody");
  tbody.innerHTML = "";

  if (!records.length) {
    tbody.innerHTML =
      `<tr><td colspan="5" style="padding:1rem;">No assessments stored yet.</td></tr>`;
    return;
  }

  records.slice(0, 20).forEach(r => {
    const tr = document.createElement("tr");
    const rain = r.environmental_data?.rainfall_24h ?? "N/A";

    tr.style.borderBottom = "1px solid #334155";
    tr.innerHTML = `
      <td style="padding: 0.5rem;">${new Date(r.timestamp).toLocaleString()}</td>
      <td style="padding: 0.5rem; color: #fff;">${r.location}</td>
      <td style="padding: 0.5rem;">${rain} mm</td>
      <td style="padding: 0.5rem;"><span class="badge badge-${r.risk_level.toLowerCase()}">${r.risk_level}</span></td>
      <td style="padding: 0.5rem; color: var(--accent-blue); font-size: 0.75rem;">LIVE ASSESSMENT</td>
    `;
    tbody.appendChild(tr);
  });
}
