/**
 * WEATHERDATA Platform — Frontend Dashboard Controller
 * Vanilla JavaScript (ES6+), Fetch API, Chart.js
 */

const API_BASE = window.location.origin;

// Chart instances
let tempTrendChart = null;
let humidityTrendChart = null;
let cityDistChart = null;

// Application State
const state = {
  summary: null,
  latestWeather: [],
  locations: [],
  pipelineRuns: [],
};

// ============================================================================
// Initialization & Event Listeners
// ============================================================================
document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupActions();
  fetchAllData();
});

function setupNavigation() {
  const navButtons = document.querySelectorAll(".nav-btn");
  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      navButtons.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".content-section").forEach((sec) => sec.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-target");
      const targetSec = document.getElementById(targetId);
      if (targetSec) targetSec.classList.add("active");
    });
  });
}

function setupActions() {
  // Global Refresh Button
  document.getElementById("btn-refresh").addEventListener("click", () => {
    showAlert("Refreshing platform data...", "info");
    fetchAllData();
  });

  // Run Pipeline from Navbar
  document.getElementById("btn-run-pipeline").addEventListener("click", () => {
    triggerETLPipeline(false);
  });

  // Run Pipeline from Pipeline Monitor (with offline sample toggle)
  document.getElementById("btn-trigger-monitor").addEventListener("click", () => {
    const useSample = document.getElementById("chk-sample-data").checked;
    triggerETLPipeline(useSample);
  });

  // History Filters
  document.getElementById("btn-apply-filter").addEventListener("click", fetchWeatherHistory);

  // Modal Close
  document.getElementById("modal-close").addEventListener("click", closeModal);
  window.addEventListener("click", (e) => {
    if (e.target === document.getElementById("modal-run-detail")) {
      closeModal();
    }
  });
}

// ============================================================================
// Data Fetching Functions
// ============================================================================
async function fetchAllData() {
  try {
    await Promise.all([
      fetchSummary(),
      fetchLocations(),
      fetchLatestWeather(),
      fetchTemperatureTrend(),
      fetchHumidityTrend(),
      fetchWeatherHistory(),
      fetchPipelineRuns(),
    ]);
  } catch (error) {
    console.error("Error loading dashboard data:", error);
    showAlert("Failed to load some data. Ensure backend is running.", "error");
  }
}

async function fetchSummary() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/summary`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.summary = data;

    // Update KPI Cards
    document.getElementById("kpi-total-records").textContent = data.total_records.toLocaleString();
    document.getElementById("kpi-cities-count").textContent = `${data.total_locations} Cities Monitored`;

    const avgTemp = data.avg_temperature_c !== null ? `${data.avg_temperature_c}°C` : "--°C";
    document.getElementById("kpi-latest-temp").textContent = avgTemp;

    const minTemp = data.min_temperature_c !== null ? `${data.min_temperature_c}°C` : "--";
    const maxTemp = data.max_temperature_c !== null ? `${data.max_temperature_c}°C` : "--";
    document.getElementById("kpi-temp-range").textContent = `Min: ${minTemp} | Max: ${maxTemp}`;

    const avgHum = data.avg_humidity_percent !== null ? `${data.avg_humidity_percent}%` : "--%";
    document.getElementById("kpi-avg-humidity").textContent = avgHum;

    // Update Analytics Section Stats
    document.getElementById("stat-max-temp").textContent = maxTemp;
    document.getElementById("stat-min-temp").textContent = minTemp;
    document.getElementById("stat-mean-temp").textContent = avgTemp;
    document.getElementById("stat-mean-humidity").textContent = avgHum;
  } catch (e) {
    console.error("fetchSummary failed:", e);
  }
}

async function fetchLocations() {
  try {
    const res = await fetch(`${API_BASE}/api/locations`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.locations = data;

    // Populate City Filter dropdown
    const select = document.getElementById("filter-history-city");
    const currentVal = select.value;
    select.innerHTML = '<option value="">All Cities</option>';
    data.forEach((loc) => {
      const opt = document.createElement("option");
      opt.value = loc.city_name;
      opt.textContent = `${loc.city_name}, ${loc.country || ""}`;
      select.appendChild(opt);
    });
    select.value = currentVal;
  } catch (e) {
    console.error("fetchLocations failed:", e);
  }
}

async function fetchLatestWeather() {
  try {
    const res = await fetch(`${API_BASE}/api/weather/latest`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.latestWeather = data;

    document.getElementById("badge-latest-count").textContent = `${data.length} Locations`;

    const container = document.getElementById("latest-weather-cards");
    if (!data || data.length === 0) {
      container.innerHTML = '<div class="loading-state">No weather records loaded yet. Click "Run ETL Pipeline" to ingest.</div>';
      return;
    }

    container.innerHTML = data
      .map((item) => {
        const temp = item.temperature_c !== null ? `${item.temperature_c}°C` : "--";
        const hum = item.humidity_percent !== null ? `${item.humidity_percent}%` : "--";
        const wind = item.wind_speed_kmh !== null ? `${item.wind_speed_kmh} km/h` : "--";
        const cond = item.weather_condition || "Unknown";
        const time = item.recorded_at ? new Date(item.recorded_at).toUTCString() : "Pending sync";

        return `
          <div class="weather-city-card">
            <div class="card-top">
              <div>
                <div class="city-title">${item.city_name}</div>
                <div class="country-title">${item.country || ""}</div>
              </div>
              <div class="temp-large">${temp}</div>
            </div>
            <div class="weather-condition-tag">⛅ ${cond}</div>
            <div class="weather-details-grid">
              <div class="weather-detail-item">Humidity: <span>${hum}</span></div>
              <div class="weather-detail-item">Wind: <span>${wind}</span></div>
            </div>
            <div class="card-recorded-time">🕒 ${time}</div>
          </div>
        `;
      })
      .join("");

    renderCityDistributionChart(data);
  } catch (e) {
    console.error("fetchLatestWeather failed:", e);
  }
}

async function fetchTemperatureTrend() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/temperature-trend?days=7`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderTemperatureChart(data);
  } catch (e) {
    console.error("fetchTemperatureTrend failed:", e);
  }
}

async function fetchHumidityTrend() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/humidity-trend?days=7`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderHumidityChart(data);
  } catch (e) {
    console.error("fetchHumidityTrend failed:", e);
  }
}

async function fetchWeatherHistory() {
  try {
    const city = document.getElementById("filter-history-city").value;
    const limit = document.getElementById("filter-history-limit").value;

    let url = `${API_BASE}/api/weather/history?limit=${limit}`;
    if (city) url += `&city=${encodeURIComponent(city)}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const tbody = document.getElementById("tbody-history");
    if (!data || data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="loading-cell">No matching historical records found.</td></tr>';
      return;
    }

    tbody.innerHTML = data
      .map((r) => `
        <tr>
          <td>#${r.weather_id}</td>
          <td><strong>${r.city_name}</strong></td>
          <td>${r.country || "--"}</td>
          <td>${r.recorded_at ? r.recorded_at.replace("T", " ") : "--"}</td>
          <td>${r.temperature_c !== null ? `${r.temperature_c}°C` : "--"}</td>
          <td>${r.humidity_percent !== null ? `${r.humidity_percent}%` : "--"}</td>
          <td>${r.wind_speed_kmh !== null ? `${r.wind_speed_kmh} km/h` : "--"}</td>
          <td>${r.weather_condition || "Unknown"}</td>
          <td><span class="badge">${r.source}</span></td>
        </tr>
      `)
      .join("");
  } catch (e) {
    console.error("fetchWeatherHistory failed:", e);
  }
}

async function fetchPipelineRuns() {
  try {
    const res = await fetch(`${API_BASE}/api/pipeline/runs?limit=20`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const runs = await res.json();
    state.pipelineRuns = runs;

    if (runs.length > 0) {
      const latest = runs[0];
      const statusBadge = document.getElementById("kpi-pipeline-status");
      statusBadge.textContent = latest.status;
      statusBadge.className = `kpi-value badge-status ${latest.status.toLowerCase()}`;

      const started = new Date(latest.started_at);
      document.getElementById("kpi-last-run-time").textContent = `Last run: ${started.toLocaleTimeString()}`;
    }

    const tbody = document.getElementById("tbody-pipeline-runs");
    if (!runs || runs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="loading-cell">No pipeline runs recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = runs
      .map((r) => {
        const start = new Date(r.started_at);
        const end = r.completed_at ? new Date(r.completed_at) : null;
        const duration = end ? `${((end - start) / 1000).toFixed(1)}s` : "Running...";

        return `
          <tr>
            <td>#${r.run_id}</td>
            <td><strong>${r.pipeline_name}</strong></td>
            <td><span class="badge-status ${r.status.toLowerCase()}">${r.status}</span></td>
            <td>${start.toLocaleString()}</td>
            <td>${duration}</td>
            <td>${r.records_extracted}</td>
            <td>${r.records_loaded}</td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="viewRunDetails(${r.run_id})">Inspect</button>
            </td>
          </tr>
        `;
      })
      .join("");
  } catch (e) {
    console.error("fetchPipelineRuns failed:", e);
  }
}

// ============================================================================
// Pipeline Run Execution Trigger
// ============================================================================
async function triggerETLPipeline(useSampleData = false) {
  const btn1 = document.getElementById("btn-run-pipeline");
  const btn2 = document.getElementById("btn-trigger-monitor");

  btn1.disabled = true;
  btn2.disabled = true;
  btn1.innerHTML = '<span class="btn-icon">⏳</span> Ingesting...';
  btn2.innerHTML = '<span class="btn-icon">⏳</span> Ingesting...';

  showAlert(`Triggering ${useSampleData ? 'offline sample' : 'live REST API'} ETL Pipeline...`, "info");

  try {
    const res = await fetch(`${API_BASE}/api/pipeline/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_sample_data: useSampleData }),
    });

    const result = await res.json();
    if (res.ok && result.success) {
      showAlert(
        `✓ ETL Success: Extracted ${result.records_extracted}, Loaded ${result.records_loaded}, Skipped ${result.duplicates_skipped} duplicates.`,
        "success"
      );
    } else {
      showAlert(`Pipeline Run: ${result.message || result.error || 'Failed'}`, "error");
    }

    // Refresh all panels
    await fetchAllData();
  } catch (err) {
    console.error("Pipeline trigger error:", err);
    showAlert(`Failed to execute ETL pipeline: ${err.message}`, "error");
  } finally {
    btn1.disabled = false;
    btn2.disabled = false;
    btn1.innerHTML = '<span class="btn-icon">▶</span> Run ETL Pipeline';
    btn2.innerHTML = '▶ Trigger ETL Pipeline';
  }
}

// ============================================================================
// Run Detail Modal
// ============================================================================
window.viewRunDetails = async function (runId) {
  try {
    const res = await fetch(`${API_BASE}/api/pipeline/runs/${runId}`);
    if (!res.ok) throw new Error("Failed to load run details");
    const data = await res.json();

    document.getElementById("modal-title").textContent = `Pipeline Run #${data.run_id} Details`;

    const qualityLogsHtml =
      data.quality_logs && data.quality_logs.length > 0
        ? `
          <h4 style="margin-top: 1rem; margin-bottom: 0.5rem; color: #fbbf24;">Data Quality Issues Logged</h4>
          <table class="data-table">
            <thead>
              <tr><th>Issue Type</th><th>Table</th><th>Count</th></tr>
            </thead>
            <tbody>
              ${data.quality_logs
                .map(
                  (q) =>
                    `<tr><td>${q.issue_type}</td><td>${q.table_name}</td><td>${q.issue_count}</td></tr>`
                )
                .join("")}
            </tbody>
          </table>
        `
        : '<p style="margin-top: 1rem; color: #34d399;">✓ Zero data quality anomalies detected during this execution.</p>';

    document.getElementById("modal-body").innerHTML = `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 1rem;">
        <div><strong>Pipeline:</strong> ${data.pipeline_name}</div>
        <div><strong>Status:</strong> <span class="badge-status ${data.status.toLowerCase()}">${data.status}</span></div>
        <div><strong>Started:</strong> ${new Date(data.started_at).toLocaleString()}</div>
        <div><strong>Completed:</strong> ${data.completed_at ? new Date(data.completed_at).toLocaleString() : '--'}</div>
        <div><strong>Records Extracted:</strong> ${data.records_extracted}</div>
        <div><strong>Records Loaded:</strong> ${data.records_loaded}</div>
      </div>
      ${data.error_message ? `<div class="alert-banner error" style="margin-top: 1rem;">Error: ${data.error_message}</div>` : ''}
      ${qualityLogsHtml}
    `;

    document.getElementById("modal-run-detail").classList.remove("hidden");
  } catch (err) {
    showAlert(`Could not load run details: ${err.message}`, "error");
  }
};

function closeModal() {
  document.getElementById("modal-run-detail").classList.add("hidden");
}

function showAlert(msg, type = "info") {
  const banner = document.getElementById("alert-banner");
  banner.textContent = msg;
  banner.className = `alert-banner ${type}`;
  banner.classList.remove("hidden");

  setTimeout(() => {
    banner.classList.add("hidden");
  }, 5000);
}

// ============================================================================
// Chart.js Visualizations
// ============================================================================
function renderTemperatureChart(trendData) {
  const ctx = document.getElementById("chart-temp-trend");
  if (!ctx) return;

  if (tempTrendChart) tempTrendChart.destroy();

  // If no trend data yet
  if (!trendData || trendData.length === 0) {
    return;
  }

  // Group by date or city
  const labels = [...new Set(trendData.map((d) => d.date))];
  const cities = [...new Set(trendData.map((d) => d.city_name))];

  const colors = [
    "#3b82f6", "#10b981", "#f97316", "#8b5cf6",
    "#06b6d4", "#ec4899", "#eab308", "#14b8a6",
  ];

  const datasets = cities.map((city, idx) => {
    const cityPoints = trendData.filter((d) => d.city_name === city);
    const dataMap = {};
    cityPoints.forEach((p) => (dataMap[p.date] = p.avg_temperature));

    return {
      label: city,
      data: labels.map((dt) => dataMap[dt] ?? null),
      borderColor: colors[idx % colors.length],
      backgroundColor: colors[idx % colors.length] + "20",
      tension: 0.3,
      fill: false,
    };
  });

  tempTrendChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8" } },
      },
      scales: {
        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: {
          ticks: { color: "#64748b", callback: (val) => `${val}°C` },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
    },
  });
}

function renderHumidityChart(trendData) {
  const ctx = document.getElementById("chart-humidity-trend");
  if (!ctx) return;

  if (humidityTrendChart) humidityTrendChart.destroy();
  if (!trendData || trendData.length === 0) return;

  const labels = [...new Set(trendData.map((d) => d.date))];
  const cities = [...new Set(trendData.map((d) => d.city_name))];

  const colors = ["#06b6d4", "#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444"];

  const datasets = cities.map((city, idx) => {
    const cityPoints = trendData.filter((d) => d.city_name === city);
    const dataMap = {};
    cityPoints.forEach((p) => (dataMap[p.date] = p.avg_humidity));

    return {
      label: city,
      data: labels.map((dt) => dataMap[dt] ?? null),
      borderColor: colors[idx % colors.length],
      backgroundColor: colors[idx % colors.length] + "33",
      borderWidth: 1.5,
    };
  });

  humidityTrendChart = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8" } },
      },
      scales: {
        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: {
          max: 100,
          ticks: { color: "#64748b", callback: (val) => `${val}%` },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
    },
  });
}

function renderCityDistributionChart(latestData) {
  const ctx = document.getElementById("chart-city-distribution");
  if (!ctx) return;

  if (cityDistChart) cityDistChart.destroy();
  if (!latestData || latestData.length === 0) return;

  const labels = latestData.map((d) => d.city_name);
  const temps = latestData.map((d) => d.temperature_c);
  const humidities = latestData.map((d) => d.humidity_percent);

  cityDistChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Current Temperature (°C)",
          data: temps,
          backgroundColor: "rgba(249, 115, 22, 0.7)",
          borderColor: "#f97316",
          borderWidth: 1,
        },
        {
          label: "Relative Humidity (%)",
          data: humidities,
          backgroundColor: "rgba(6, 182, 212, 0.7)",
          borderColor: "#06b6d4",
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8" } },
      },
      scales: {
        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
      },
    },
  });
}
