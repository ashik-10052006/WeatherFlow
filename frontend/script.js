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
  temperatureTrend: [],
  humidityTrend: [],
  chartMode: "RANKED", // "RANKED" or "TREND"
  selectedChartCity: "ALL",
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

  // History Filters & Instant Dynamic Search
  const btnApplyFilter = document.getElementById("btn-apply-filter");
  const filterCity = document.getElementById("filter-history-city");
  const filterLimit = document.getElementById("filter-history-limit");
  const inputHistorySearch = document.getElementById("input-history-search");

  if (btnApplyFilter) {
    btnApplyFilter.addEventListener("click", () => fetchWeatherHistory());
  }
  if (filterCity) {
    filterCity.addEventListener("change", () => {
      if (inputHistorySearch) inputHistorySearch.value = filterCity.value;
      updateHistoryChipsActive(filterCity.value);
      fetchWeatherHistory();
    });
  }
  if (filterLimit) {
    filterLimit.addEventListener("change", () => fetchWeatherHistory());
  }
  if (inputHistorySearch) {
    inputHistorySearch.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      filterHistoryTableClientSide(q);
    });
    inputHistorySearch.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const val = inputHistorySearch.value.trim();
        if (filterCity) filterCity.value = val;
        fetchWeatherHistory();
      }
    });
  }

  // Modal Close
  document.getElementById("modal-close").addEventListener("click", closeModal);
  window.addEventListener("click", (e) => {
    if (e.target === document.getElementById("modal-run-detail")) {
      closeModal();
    }
  });

  // GenAI Assistant Setup
  setupGenAI();

  // Dynamic City Search Setup
  setupCitySearch();

  // Chart Visualizer Mode Toggles
  const btnRanked = document.getElementById("btn-chart-mode-compare");
  const btnTrend = document.getElementById("btn-chart-mode-trend");
  const selectChartCity = document.getElementById("select-chart-city");

  if (btnRanked && btnTrend && selectChartCity) {
    btnRanked.addEventListener("click", () => {
      btnRanked.classList.add("active");
      btnTrend.classList.remove("active");
      selectChartCity.classList.add("hidden");
      state.chartMode = "RANKED";
      renderCharts();
    });

    btnTrend.addEventListener("click", () => {
      btnTrend.classList.add("active");
      btnRanked.classList.remove("active");
      selectChartCity.classList.remove("hidden");
      state.chartMode = "TREND";
      renderCharts();
    });

    selectChartCity.addEventListener("change", (e) => {
      state.selectedChartCity = e.target.value;
      renderCharts();
    });
  }
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

    // Populate City Filter dropdown in Weather History
    const select = document.getElementById("filter-history-city");
    const currentVal = select.value;
    select.innerHTML = '<option value="">All Cities</option>';
    data.forEach((loc) => {
      const opt = document.createElement("option");
      opt.value = loc.city_name;
      opt.textContent = `${loc.city_name}, ${loc.country || ""}`;
      select.appendChild(opt);
    });
    if (currentVal) select.value = currentVal;

    // Populate Quick Filter Chips in Weather History
    const chipsContainer = document.getElementById("history-quick-chips");
    if (chipsContainer) {
      let chipsHtml = `<button class="chip-history-btn ${!select.value ? 'active' : ''}" data-city="">🌐 All Cities</button>`;
      data.forEach((loc) => {
        const isActive = select.value === loc.city_name ? "active" : "";
        chipsHtml += `<button class="chip-history-btn ${isActive}" data-city="${loc.city_name}">${loc.city_name}</button>`;
      });
      chipsContainer.innerHTML = chipsHtml;

      chipsContainer.querySelectorAll(".chip-history-btn").forEach((chip) => {
        chip.addEventListener("click", () => {
          const city = chip.getAttribute("data-city");
          select.value = city;
          updateHistoryChipsActive(city);
          const inputSearch = document.getElementById("input-history-search");
          if (inputSearch) inputSearch.value = city;
          fetchWeatherHistory();
        });
      });
    }
  } catch (e) {
    console.error("fetchLocations failed:", e);
  }
}

function updateHistoryChipsActive(selectedCity) {
  const chipsContainer = document.getElementById("history-quick-chips");
  if (!chipsContainer) return;
  chipsContainer.querySelectorAll(".chip-history-btn").forEach((chip) => {
    const city = chip.getAttribute("data-city") || "";
    if (city.toLowerCase() === (selectedCity || "").toLowerCase()) {
      chip.classList.add("active");
    } else {
      chip.classList.remove("active");
    }
  });
}

function filterHistoryTableClientSide(q) {
  const rows = document.querySelectorAll("#tbody-history tr");
  let visibleCount = 0;
  rows.forEach((row) => {
    const text = row.textContent.toLowerCase();
    const matches = !q || text.includes(q);
    row.style.display = matches ? "" : "none";
    if (matches) visibleCount++;
  });
  const badge = document.getElementById("badge-history-count");
  if (badge) badge.textContent = `${visibleCount} Records`;
}

function getWeatherVisuals(conditionText) {
  const cond = (conditionText || "").toLowerCase();
  if (cond.includes("sun") || cond.includes("clear")) {
    return { icon: "☀️", cssClass: "condition-sunny" };
  }
  if (cond.includes("rain") || cond.includes("drizzle") || cond.includes("shower")) {
    return { icon: "🌧️", cssClass: "condition-rain" };
  }
  if (cond.includes("thunder")) {
    return { icon: "⛈️", cssClass: "condition-thunder" };
  }
  if (cond.includes("snow") || cond.includes("ice") || cond.includes("blizzard")) {
    return { icon: "❄️", cssClass: "condition-snow" };
  }
  return { icon: "☁️", cssClass: "condition-cloudy" };
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
        const visuals = getWeatherVisuals(cond);
        const time = item.recorded_at ? new Date(item.recorded_at).toUTCString() : "Pending sync";

        return `
          <div class="weather-city-card ${visuals.cssClass}" data-city="${item.city_name.toLowerCase()}">
            <div class="card-top">
              <div>
                <div class="city-title">${item.city_name}</div>
                <div class="country-title">${item.country || ""}</div>
              </div>
              <div class="temp-large">${temp}</div>
            </div>
            <div class="weather-condition-tag">${visuals.icon} ${cond}</div>
            <div class="weather-details-grid">
              <div class="weather-detail-item">Humidity: <span>${hum}</span></div>
              <div class="weather-detail-item">Wind: <span>${wind}</span></div>
            </div>
            <div class="card-recorded-time">🕒 ${time}</div>
          </div>
        `;
      })
      .join("");

    populateChartCityDropdown();
    renderCharts();
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
    state.temperatureTrend = data;
    renderCharts();
  } catch (e) {
    console.error("fetchTemperatureTrend failed:", e);
  }
}

async function fetchHumidityTrend() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/humidity-trend?days=7`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.humidityTrend = data;
    renderCharts();
  } catch (e) {
    console.error("fetchHumidityTrend failed:", e);
  }
}

async function fetchWeatherHistory() {
  try {
    const citySelect = document.getElementById("filter-history-city");
    const cityInput = document.getElementById("input-history-search");
    const limitSelect = document.getElementById("filter-history-limit");

    const limit = limitSelect ? limitSelect.value : 50;
    let city = (citySelect && citySelect.value) ? citySelect.value : (cityInput ? cityInput.value.trim() : "");

    let url = `${API_BASE}/api/weather/history?limit=${limit}`;
    if (city) url += `&city=${encodeURIComponent(city)}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const badge = document.getElementById("badge-history-count");
    if (badge) badge.textContent = `${data.length} Records`;

    const tbody = document.getElementById("tbody-history");
    if (!data || data.length === 0) {
      const searchPrompt = city ? `
        <div style="margin-top: 0.75rem;">
          <button class="btn btn-primary btn-sm" onclick="searchAndIngestCity('${city}')">
            🌐 Search & Ingest "${city}" Live from Weather API
          </button>
        </div>
      ` : "";
      tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">No matching historical records found for "${city || 'all'}". ${searchPrompt}</td></tr>`;
      return;
    }

    tbody.innerHTML = data
      .map((r) => {
        const condVisuals = getWeatherVisuals(r.weather_condition);
        return `
          <tr>
            <td>#${r.weather_id}</td>
            <td><strong>${r.city_name}</strong></td>
            <td>${r.country || "--"}</td>
            <td>${r.recorded_at ? r.recorded_at.replace("T", " ") : "--"}</td>
            <td><strong>${r.temperature_c !== null ? `${r.temperature_c}°C` : "--"}</strong></td>
            <td>${r.humidity_percent !== null ? `${r.humidity_percent}%` : "--"}</td>
            <td>${r.wind_speed_kmh !== null ? `${r.wind_speed_kmh} km/h` : "--"}</td>
            <td>${condVisuals.icon} ${r.weather_condition || "Unknown"}</td>
            <td><span class="badge">${r.source}</span></td>
          </tr>
        `;
      })
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
function populateChartCityDropdown() {
  const select = document.getElementById("select-chart-city");
  if (!select) return;

  const currentVal = select.value;
  const cities = [...new Set((state.latestWeather || []).map((c) => c.city_name))].sort();

  let opts = '<option value="ALL">🌐 All Stations (Warehouse Avg)</option>';
  opts += cities.map((c) => `<option value="${c}">${c}</option>`).join("");
  select.innerHTML = opts;

  if (cities.includes(currentVal)) {
    select.value = currentVal;
  } else {
    select.value = "ALL";
    state.selectedChartCity = "ALL";
  }
}

function renderCharts() {
  if (state.chartMode === "RANKED") {
    renderRankedCharts();
  } else {
    renderTrendCharts();
  }
}

function renderRankedCharts() {
  const hTemp = document.getElementById("heading-chart-temp");
  const bTemp = document.getElementById("badge-chart-temp-mode");
  const hHum = document.getElementById("heading-chart-humidity");
  const bHum = document.getElementById("badge-chart-humidity-mode");

  if (hTemp) hTemp.textContent = "Current Temperature by Station (°C)";
  if (bTemp) bTemp.textContent = "Ranked Comparison";
  if (hHum) hHum.textContent = "Relative Humidity by Station (%)";
  if (bHum) bHum.textContent = "Ranked Comparison";

  const data = state.latestWeather || [];
  if (data.length === 0) return;

  // 1. Temperature Chart (Ranked Horizontal Bars from Hottest to Coolest)
  const sortedTemp = [...data].sort((a, b) => (b.temperature_c ?? 0) - (a.temperature_c ?? 0));
  const tempLabels = sortedTemp.map((d) => d.city_name);
  const tempValues = sortedTemp.map((d) => d.temperature_c);

  const tempColors = tempValues.map((t) => {
    if (t >= 32) return "rgba(244, 63, 94, 0.85)"; // Hot Rose
    if (t >= 26) return "rgba(245, 158, 11, 0.85)"; // Warm Amber
    if (t >= 20) return "rgba(6, 182, 212, 0.85)"; // Mild Cyan
    return "rgba(59, 130, 246, 0.85)"; // Cool Blue
  });

  const ctxTemp = document.getElementById("chart-temp-trend");
  if (ctxTemp) {
    if (tempTrendChart) tempTrendChart.destroy();
    tempTrendChart = new Chart(ctxTemp, {
      type: "bar",
      data: {
        labels: tempLabels,
        datasets: [
          {
            label: "Temperature (°C)",
            data: tempValues,
            backgroundColor: tempColors,
            borderRadius: 8,
            borderSkipped: false,
            barPercentage: 0.65,
            categoryPercentage: 0.85,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            titleColor: "#ffffff",
            bodyColor: "#f1f5f9",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctx) => ` Temperature: ${ctx.parsed.x}°C`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#94a3b8", callback: (val) => `${val}°C` },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
          },
          y: {
            ticks: { color: "#f1f5f9", font: { weight: "600", size: 12 } },
            grid: { display: false },
          },
        },
      },
    });
  }

  // 2. Humidity Chart (Ranked Horizontal Bars from Most Humid to Drier)
  const sortedHum = [...data].sort((a, b) => (b.humidity_percent ?? 0) - (a.humidity_percent ?? 0));
  const humLabels = sortedHum.map((d) => d.city_name);
  const humValues = sortedHum.map((d) => d.humidity_percent);

  const humColors = humValues.map((h) => {
    if (h >= 75) return "rgba(56, 189, 248, 0.85)"; // Sky Blue
    if (h >= 50) return "rgba(6, 182, 212, 0.85)"; // Cyan
    return "rgba(99, 102, 241, 0.85)"; // Indigo
  });

  const ctxHum = document.getElementById("chart-humidity-trend");
  if (ctxHum) {
    if (humidityTrendChart) humidityTrendChart.destroy();
    humidityTrendChart = new Chart(ctxHum, {
      type: "bar",
      data: {
        labels: humLabels,
        datasets: [
          {
            label: "Humidity (%)",
            data: humValues,
            backgroundColor: humColors,
            borderRadius: 8,
            borderSkipped: false,
            barPercentage: 0.65,
            categoryPercentage: 0.85,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            titleColor: "#ffffff",
            bodyColor: "#f1f5f9",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctx) => ` Relative Humidity: ${ctx.parsed.x}%`,
            },
          },
        },
        scales: {
          x: {
            max: 100,
            ticks: { color: "#94a3b8", callback: (val) => `${val}%` },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
          },
          y: {
            ticks: { color: "#f1f5f9", font: { weight: "600", size: 12 } },
            grid: { display: false },
          },
        },
      },
    });
  }
}

function renderTrendCharts() {
  const trend = state.temperatureTrend || [];
  const humTrend = state.humidityTrend || [];
  if (trend.length === 0) return;

  const hTemp = document.getElementById("heading-chart-temp");
  const bTemp = document.getElementById("badge-chart-temp-mode");
  const hHum = document.getElementById("heading-chart-humidity");
  const bHum = document.getElementById("badge-chart-humidity-mode");

  const selected = state.selectedChartCity || "ALL";

  let dates = [];
  let tempPoints = [];
  let humPoints = [];

  if (selected === "ALL") {
    if (hTemp) hTemp.textContent = "Warehouse Average Temperature (Past 7 Days)";
    if (bTemp) bTemp.textContent = "Global 7-Day Trend";
    if (hHum) hHum.textContent = "Warehouse Average Humidity (Past 7 Days)";
    if (bHum) bHum.textContent = "Global 7-Day Trend";

    dates = [...new Set(trend.map((d) => d.date))].sort();
    tempPoints = dates.map((dt) => {
      const match = trend.filter((d) => d.date === dt);
      const sum = match.reduce((a, b) => a + (b.avg_temperature || 0), 0);
      return match.length > 0 ? parseFloat((sum / match.length).toFixed(1)) : null;
    });

    humPoints = dates.map((dt) => {
      const match = humTrend.filter((d) => d.date === dt);
      const sum = match.reduce((a, b) => a + (b.avg_humidity || 0), 0);
      return match.length > 0 ? Math.round(sum / match.length) : null;
    });
  } else {
    if (hTemp) hTemp.textContent = `${selected} — 7-Day Temperature Trend (°C)`;
    if (bTemp) bTemp.textContent = "Single Station";
    if (hHum) hHum.textContent = `${selected} — 7-Day Humidity Trend (%)`;
    if (bHum) bHum.textContent = "Single Station";

    const filteredTemp = trend.filter((d) => d.city_name === selected).sort((a, b) => a.date.localeCompare(b.date));
    const filteredHum = humTrend.filter((d) => d.city_name === selected).sort((a, b) => a.date.localeCompare(b.date));

    dates = filteredTemp.map((d) => d.date);
    tempPoints = filteredTemp.map((d) => d.avg_temperature);
    humPoints = filteredHum.map((d) => d.avg_humidity);
  }

  // Format date labels: "Aug 28", "Aug 29", etc.
  const formattedDates = dates.map((dt) => {
    try {
      const parts = dt.split("-");
      if (parts.length === 3) {
        const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      }
      return dt;
    } catch {
      return dt;
    }
  });

  // 1. Temperature Line Chart (Smooth Area Spline)
  const ctxTemp = document.getElementById("chart-temp-trend");
  if (ctxTemp) {
    if (tempTrendChart) tempTrendChart.destroy();
    tempTrendChart = new Chart(ctxTemp, {
      type: "line",
      data: {
        labels: formattedDates,
        datasets: [
          {
            label: "Average Temperature (°C)",
            data: tempPoints,
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.15)",
            borderWidth: 3,
            fill: true,
            tension: 0.35,
            pointBackgroundColor: "#0284c7",
            pointBorderColor: "#38bdf8",
            pointRadius: 5,
            pointHoverRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            titleColor: "#ffffff",
            bodyColor: "#f1f5f9",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctx) => ` Temp: ${ctx.parsed.y}°C`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#94a3b8" },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
          },
          y: {
            ticks: { color: "#94a3b8", callback: (val) => `${val}°C` },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
          },
        },
      },
    });
  }

  // 2. Humidity Bar Chart (Spacious Daily Bars)
  const ctxHum = document.getElementById("chart-humidity-trend");
  if (ctxHum) {
    if (humidityTrendChart) humidityTrendChart.destroy();
    humidityTrendChart = new Chart(ctxHum, {
      type: "bar",
      data: {
        labels: formattedDates,
        datasets: [
          {
            label: "Average Humidity (%)",
            data: humPoints,
            backgroundColor: "rgba(6, 182, 212, 0.65)",
            borderColor: "#06b6d4",
            borderWidth: 1.5,
            borderRadius: 6,
            barPercentage: 0.5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            titleColor: "#ffffff",
            bodyColor: "#f1f5f9",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctx) => ` Humidity: ${ctx.parsed.y}%`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#94a3b8" },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
          },
          y: {
            max: 100,
            ticks: { color: "#94a3b8", callback: (val) => `${val}%` },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
          },
        },
      },
    });
  }
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

// ============================================================================
// GenAI Assistant Functions
// ============================================================================
function setupGenAI() {
  const askBtn = document.getElementById("btn-ask-genai");
  const input = document.getElementById("genai-question-input");
  if (!askBtn || !input) return;

  // Load current AI configuration
  loadAiConfig();

  // Toggle AI Configuration Drawer
  const toggleBtn = document.getElementById("toggle-ai-config");
  const configPanel = document.getElementById("ai-config-panel");
  const toggleIcon = document.getElementById("icon-toggle-ai");
  if (toggleBtn && configPanel) {
    toggleBtn.addEventListener("click", () => {
      configPanel.classList.toggle("hidden");
      if (toggleIcon) {
        toggleIcon.textContent = configPanel.classList.contains("hidden") ? "▼ Configure" : "▲ Close";
      }
    });
  }

  // Save AI Configuration Button
  const btnSaveAi = document.getElementById("btn-save-ai-config");
  if (btnSaveAi) {
    btnSaveAi.addEventListener("click", async () => {
      const provider = document.getElementById("select-ai-provider").value;
      const apiKey = document.getElementById("input-ai-key").value.trim();
      const model = document.getElementById("input-ai-model").value.trim();
      const statusSpan = document.getElementById("ai-config-status");

      btnSaveAi.disabled = true;
      btnSaveAi.textContent = "Saving...";
      statusSpan.textContent = "Updating AI configuration...";
      statusSpan.style.color = "var(--text-muted)";

      try {
        const res = await fetch(`${API_BASE}/api/genai/config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider, api_key: apiKey || null, model: model || null }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to save configuration");

        statusSpan.textContent = `✓ Active: ${data.config.provider} (${data.config.model})`;
        statusSpan.style.color = "#34d399";
        showAlert(`AI Provider updated to ${data.config.provider}`, "success");

        updateAiBadges(data.config);
        document.getElementById("input-ai-key").value = "";
      } catch (err) {
        statusSpan.textContent = `Error: ${err.message}`;
        statusSpan.style.color = "#f87171";
      } finally {
        btnSaveAi.disabled = false;
        btnSaveAi.textContent = "💾 Save & Activate AI Key";
      }
    });
  }

  askBtn.addEventListener("click", () => {
    const q = input.value.trim();
    if (q) askGenAIQuestion(q);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const q = input.value.trim();
      if (q) askGenAIQuestion(q);
    }
  });

  // Chip buttons
  document.querySelectorAll(".chip-btn").forEach((chip) => {
    chip.addEventListener("click", () => {
      const promptText = chip.getAttribute("data-prompt");
      input.value = promptText;
      askGenAIQuestion(promptText);
    });
  });
}

async function loadAiConfig() {
  try {
    const res = await fetch(`${API_BASE}/api/genai/config`);
    if (!res.ok) return;
    const cfg = await res.json();

    const select = document.getElementById("select-ai-provider");
    if (select) select.value = cfg.provider;

    const modelInput = document.getElementById("input-ai-model");
    if (modelInput && cfg.model) modelInput.placeholder = `Current: ${cfg.model}`;

    const keyInput = document.getElementById("input-ai-key");
    if (keyInput && cfg.has_api_key) {
      keyInput.placeholder = `Key configured (${cfg.masked_key || 'saved'})`;
    }

    updateAiBadges(cfg);
  } catch (e) {
    console.error("loadAiConfig failed:", e);
  }
}

function updateAiBadges(cfg) {
  const badgeHeader = document.getElementById("badge-active-ai-provider");
  const badgePill = document.getElementById("badge-ai-provider-pill");

  const nameMap = {
    gemini: "Google Gemini AI",
    openai: "OpenAI ChatGPT",
    groq: "Groq Fast Llama",
    deepseek: "DeepSeek AI",
    anthropic: "Anthropic Claude",
    ollama: "Local Ollama LLM",
    rule_based: "Safe Read-Only SQL Engine",
  };

  const displayName = nameMap[cfg.provider] || cfg.provider;
  if (badgeHeader) badgeHeader.textContent = `${displayName}`;
  if (badgePill) {
    badgePill.textContent = cfg.has_api_key ? `⚡ ${displayName} (Key Active)` : displayName;
  }
}

async function askGenAIQuestion(question) {
  const btn = document.getElementById("btn-ask-genai");
  const container = document.getElementById("genai-response-container");

  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Reasoning...';

  try {
    const res = await fetch(`${API_BASE}/api/genai/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || data.detail || "Query failed");
    }

    // Render results
    document.getElementById("genai-explanation").innerHTML = data.explanation.replace(
      /\*\*(.*?)\*\*/g,
      "<strong>$1</strong>"
    );
    document.getElementById("genai-row-count").textContent = data.row_count;

    // Build results table
    const thead = document.getElementById("thead-genai");
    const tbody = document.getElementById("tbody-genai");

    if (data.rows && data.rows.length > 0) {
      const cols = Object.keys(data.rows[0]);
      thead.innerHTML = `<tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr>`;
      tbody.innerHTML = data.rows
        .map(
          (row) =>
            `<tr>${cols.map((c) => `<td>${row[c] !== null ? row[c] : "--"}</td>`).join("")}</tr>`
        )
        .join("");
    } else {
      thead.innerHTML = "";
      tbody.innerHTML = '<tr><td class="loading-cell">Zero rows matched query conditions.</td></tr>';
    }

    container.classList.remove("hidden");
  } catch (err) {
    showAlert(`GenAI Error: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Ask Assistant";
  }
}

// ============================================================================
// Dynamic Global City Search & Ingestion
// ============================================================================
function setupCitySearch() {
  const searchInput = document.getElementById("input-city-search");
  const searchBtn = document.getElementById("btn-search-city");
  if (!searchInput || !searchBtn) return;

  searchBtn.addEventListener("click", () => {
    const q = searchInput.value.trim();
    if (q) searchAndIngestCity(q);
  });

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const q = searchInput.value.trim();
      if (q) searchAndIngestCity(q);
    }
  });

  // Quick Ingest City Chips
  document.querySelectorAll(".city-chip-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const city = btn.getAttribute("data-city");
      searchInput.value = city;
      searchAndIngestCity(city);
    });
  });

  // Client-side instant filter on cards grid
  const cardsFilter = document.getElementById("input-cards-filter");
  if (cardsFilter) {
    cardsFilter.addEventListener("input", (e) => {
      const val = e.target.value.toLowerCase().trim();
      const cards = document.querySelectorAll("#latest-weather-cards .weather-city-card");
      cards.forEach((card) => {
        const city = card.getAttribute("data-city") || "";
        card.style.display = city.includes(val) ? "" : "none";
      });
    });
  }
}

async function searchAndIngestCity(cityName) {
  const btn = document.getElementById("btn-search-city");
  const container = document.getElementById("search-result-container");

  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Ingesting...';
  showAlert(`Searching live weather for ${cityName}...`, "info");

  try {
    const res = await fetch(`${API_BASE}/api/weather/search?city=${encodeURIComponent(cityName)}&refresh=true`);
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.detail || data.error || "City search failed");
    }

    const w = data.weather || {};
    const visuals = getWeatherVisuals(w.weather_condition);
    const tempF = w.temperature_c !== null ? ((w.temperature_c * 9/5) + 32).toFixed(1) : "--";

    container.innerHTML = `
      <div class="dynamic-result-card">
        <div class="dynamic-result-left">
          <div class="dynamic-weather-icon">${visuals.icon}</div>
          <div>
            <div style="font-size: 1.4rem; font-weight: 700; color: #ffffff;">${data.city_name}, ${data.country || ""}</div>
            <div class="dynamic-cond-badge">${w.weather_condition || "Live"}</div>
            <div style="font-size: 0.75rem; color: #34d399; margin-top: 0.25rem;">
              ${data.is_new ? "✓ Newly Added & Ingested into SQL Server" : "✓ Ingested / Updated in Warehouse"} (${w.source || "weather_api"})
            </div>
          </div>
        </div>
        <div>
          <div class="dynamic-temp-big">${w.temperature_c !== null ? `${w.temperature_c}°C` : "--"}</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">${tempF}°F</div>
        </div>
        <div class="dynamic-meta-grid">
          <div class="dynamic-meta-item"><span>Humidity</span><strong>${w.humidity_percent !== null ? `${w.humidity_percent}%` : "--"}</strong></div>
          <div class="dynamic-meta-item"><span>Wind</span><strong>${w.wind_speed_kmh !== null ? `${w.wind_speed_kmh} km/h` : "--"}</strong></div>
          <div class="dynamic-meta-item"><span>Observed</span><strong>${w.recorded_at ? w.recorded_at.replace("T", " ") : "--"}</strong></div>
        </div>
      </div>
    `;
    container.classList.remove("hidden");

    showAlert(`✓ Live weather for ${data.city_name}: ${w.temperature_c}°C, ${w.weather_condition}`, "success");

    // Refresh entire platform data so KPIs, cards, and history update immediately
    await fetchAllData();

    // Auto-select and display newly searched city in Weather History filter
    const histSelect = document.getElementById("filter-history-city");
    if (histSelect) {
      histSelect.value = data.city_name;
      updateHistoryChipsActive(data.city_name);
      fetchWeatherHistory();
    }
  } catch (err) {
    console.error("City search error:", err);
    showAlert(`City Search: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">🔍</span> Search & Ingest';
  }
}
