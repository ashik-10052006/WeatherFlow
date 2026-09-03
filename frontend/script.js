/**
 * WEATHERFLOW Platform — Frontend Dashboard Controller
 * Vanilla JavaScript (ES6+), Fetch API, Chart.js
 */

const API_BASE = window.location.origin;

// Chart instances
let tempTrendChart = null;
let humidityTrendChart = null;
let cityDistChart = null;
let drawerTrendChart = null;
let chartConditionDonut = null;
let chartStationPolar = null;
let chartMultiCityTrend = null;
let chartCityRadar = null;
let chartCorrelationScatter = null;
let chartThermalRanked = null;

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
  // Client-Level History Table State
  history: {
    allRecords: [],
    filteredRecords: [],
    sortColumn: "recorded_at",
    sortAsc: false,
    page: 1,
    pageSize: 25,
    search: "",
    city: "",
    condition: "",
  },
  // Client-Level Auto-Refresh State
  autoRefresh: {
    intervalSec: 0,
    remainingSec: 0,
    timerId: null,
  },
};

// ============================================================================
// Initialization & Event Listeners
// ============================================================================
document.addEventListener("DOMContentLoaded", () => {
  try { setupNavigation(); } catch (e) { console.error("setupNavigation:", e); }
  try { setupActions(); } catch (e) { console.error("setupActions:", e); }
  try { setupCommandPalette(); } catch (e) { console.error("setupCommandPalette:", e); }
  try { setupAutoRefresh(); } catch (e) { console.error("setupAutoRefresh:", e); }
  try { setupStationDrawer(); } catch (e) { console.error("setupStationDrawer:", e); }
  try { setupHistoryTableSortingAndExport(); } catch (e) { console.error("setupHistoryTableSortingAndExport:", e); }
  try { setupPortalsDropdown(); } catch (e) { console.error("setupPortalsDropdown:", e); }
  fetchAllData();
});

function setupPortalsDropdown() {
  const dropdown = document.getElementById("dropdown-portals");
  const trigger = document.getElementById("btn-portals-toggle");
  if (!dropdown || !trigger) return;

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("open");
  });

  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target)) {
      dropdown.classList.remove("open");
    }
  });
}

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
  const modalCloseBtn = document.getElementById("modal-close");
  if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeModal);
  window.addEventListener("click", (e) => {
    if (e.target === document.getElementById("modal-run-detail")) {
      closeModal();
    }
  });

  // GenAI Assistant Setup
  setupGenAI();

  // Dynamic City Search Setup
  setupCitySearch();

  // SkyCast Synoptic Intelligence & Geolocation Setup
  setupMyLocation();
  setupFavoritesAndHistory();
  fetchSynopticWeather("Chennai");

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

  // Advanced Analytics Recompute Button
  const btnRefreshAnalytics = document.getElementById("btn-refresh-analytics");
  if (btnRefreshAnalytics) {
    btnRefreshAnalytics.addEventListener("click", () => {
      showToast("Recomputing meteorological charts...", "info");
      fetchAdvancedAnalytics();
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
      fetchAdvancedAnalytics(),
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
    const totalRecordsEl = document.getElementById("kpi-total-records");
    if (totalRecordsEl) {
      totalRecordsEl.textContent = data.total_records !== undefined && data.total_records !== null ? data.total_records.toLocaleString() : "--";
    }
    const citiesCountEl = document.getElementById("kpi-cities-count");
    if (citiesCountEl) {
      citiesCountEl.textContent = `${data.total_locations ?? 0} Cities Monitored`;
    }

    const avgTemp = data.avg_temperature_c !== null && data.avg_temperature_c !== undefined ? `${data.avg_temperature_c}°C` : "--°C";
    const latestTempEl = document.getElementById("kpi-latest-temp");
    if (latestTempEl) latestTempEl.textContent = avgTemp;

    const minTemp = data.min_temperature_c !== null && data.min_temperature_c !== undefined ? `${data.min_temperature_c}°C` : "--";
    const maxTemp = data.max_temperature_c !== null && data.max_temperature_c !== undefined ? `${data.max_temperature_c}°C` : "--";
    const tempRangeEl = document.getElementById("kpi-temp-range");
    if (tempRangeEl) tempRangeEl.textContent = `Min: ${minTemp} | Max: ${maxTemp}`;

    const avgHum = data.avg_humidity_percent !== null && data.avg_humidity_percent !== undefined ? `${data.avg_humidity_percent}%` : "--%";
    const avgHumEl = document.getElementById("kpi-avg-humidity");
    if (avgHumEl) avgHumEl.textContent = avgHum;

    // Update Analytics Section Stats
    const statMax = document.getElementById("stat-max-temp");
    if (statMax) statMax.textContent = maxTemp;
    const statMin = document.getElementById("stat-min-temp");
    if (statMin) statMin.textContent = minTemp;
    const statMean = document.getElementById("stat-mean-temp");
    if (statMean) statMean.textContent = avgTemp;
    const statMeanHum = document.getElementById("stat-mean-humidity");
    if (statMeanHum) statMeanHum.textContent = avgHum;
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
  state.history.page = 1;
  renderHistoryTable();
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

function formatFriendlyTime(dateStr) {
  if (!dateStr) return "Just synced";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "Recently synced";
    const now = new Date();
    const diffMs = now - d;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins >= 0 && diffMins < 60) {
      return diffMins <= 1 ? "Just now" : `${diffMins}m ago`;
    }
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return "Recently synced";
  }
}

function quickFilterCity(cityName) {
  const historyBtn = document.querySelector('[data-target="section-history"]');
  if (historyBtn) historyBtn.click();
  const searchInput = document.getElementById("input-history-search");
  const citySelect = document.getElementById("filter-history-city");
  if (citySelect) citySelect.value = cityName;
  if (searchInput) searchInput.value = cityName;
  updateHistoryChipsActive(cityName);
  state.history.page = 1;
  fetchWeatherHistory();
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
        const friendlyTime = formatFriendlyTime(item.recorded_at);

        return `
          <div class="weather-city-card ${visuals.cssClass}" data-city="${item.city_name.toLowerCase()}">
            <div class="card-top">
              <div class="card-location-meta">
                <div class="city-title">${item.city_name}</div>
                <div class="country-pill">${item.country || "Global"}</div>
              </div>
              <div class="temp-large">${temp}</div>
            </div>
            
            <div class="card-mid">
              <span class="weather-condition-pill">${visuals.icon} ${cond}</span>
            </div>

            <div class="weather-details-chips">
              <div class="weather-detail-chip">
                <span class="chip-val">${hum}</span>
                <span class="chip-label">💧 Humidity</span>
              </div>
              <div class="weather-detail-chip">
                <span class="chip-val">${wind}</span>
                <span class="chip-label">💨 Wind</span>
              </div>
            </div>

            <div class="card-bottom">
              <div class="card-recorded-time"><span class="pulse-dot-small"></span> Synced ${friendlyTime}</div>
              <div style="display: flex; gap: 0.35rem;">
                <button class="card-explore-btn" onclick="openStationDrawerByCity('${item.city_name}')" title="Inspect ${item.city_name} Station Telemetry & 7-Day Curve">Inspect &rarr;</button>
                <button class="card-explore-btn" onclick="quickFilterCity('${item.city_name}')" title="Filter history for ${item.city_name}">History &rarr;</button>
              </div>
            </div>
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

// ============================================================================
// Client-Level Production Modules
// ============================================================================

// Floating Toasts & Alerts
function showAlert(msg, type = "info") {
  showToast(msg, type);
  const banner = document.getElementById("alert-banner");
  if (banner) {
    banner.textContent = msg;
    banner.className = `alert-banner ${type}`;
    banner.classList.remove("hidden");
    setTimeout(() => { banner.classList.add("hidden"); }, 5000);
  }
}

function showToast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const icons = {
    success: "✓",
    error: "✕",
    info: "⚡",
    warning: "⚠️",
  };

  const toast = document.createElement("div");
  toast.className = `toast-item toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || "•"}</span>
    <span class="toast-msg">${msg}</span>
    <button class="toast-close">&times;</button>
  `;

  toast.querySelector(".toast-close").addEventListener("click", () => {
    toast.remove();
  });

  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(50px)";
      setTimeout(() => toast.remove(), 250);
    }
  }, 4500);
}

// ----------------------------------------------------------------------------
// Enterprise Weather History Table (Filter, Sort, Paginate, Export)
// ----------------------------------------------------------------------------
async function fetchWeatherHistory() {
  try {
    const citySelect = document.getElementById("filter-history-city");
    const cityInput = document.getElementById("input-history-search");
    const limitSelect = document.getElementById("filter-history-limit");

    const limit = limitSelect ? limitSelect.value : 100;
    let city = (citySelect && citySelect.value) ? citySelect.value : (cityInput ? cityInput.value.trim() : "");

    let url = `${API_BASE}/api/weather/history?limit=${limit}`;
    if (city) url += `&city=${encodeURIComponent(city)}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    state.history.allRecords = data || [];
    state.history.page = 1;
    renderHistoryTable();
  } catch (e) {
    console.error("fetchWeatherHistory failed:", e);
    showToast(`Failed to load historical data: ${e.message}`, "error");
  }
}

function renderHistoryTable() {
  const tbody = document.getElementById("tbody-history");
  if (!tbody) return;

  const searchInput = document.getElementById("input-history-search");
  const condSelect = document.getElementById("filter-history-condition");
  const q = searchInput ? searchInput.value.toLowerCase().trim() : "";
  const condFilter = condSelect ? condSelect.value.toLowerCase().trim() : "";

  // 1. Filter
  let filtered = (state.history.allRecords || []).filter((r) => {
    if (condFilter) {
      const cond = (r.weather_condition || "").toLowerCase();
      if (condFilter === "sunny" && !(cond.includes("sun") || cond.includes("clear"))) return false;
      if (condFilter === "rain" && !(cond.includes("rain") || cond.includes("drizzle") || cond.includes("shower"))) return false;
      if (condFilter === "cloud" && !(cond.includes("cloud") || cond.includes("overcast"))) return false;
      if (condFilter === "thunder" && !cond.includes("thunder")) return false;
      if (condFilter === "snow" && !(cond.includes("snow") || cond.includes("ice"))) return false;
    }
    if (q) {
      const rowText = `${r.city_name} ${r.country || ""} ${r.weather_condition || ""} ${r.source || ""}`.toLowerCase();
      if (!rowText.includes(q)) return false;
    }
    return true;
  });

  // 2. Sort
  const col = state.history.sortColumn;
  const isAsc = state.history.sortAsc;
  filtered.sort((a, b) => {
    let valA = a[col];
    let valB = b[col];

    if (valA === null || valA === undefined) valA = "";
    if (valB === null || valB === undefined) valB = "";

    if (typeof valA === "number" && typeof valB === "number") {
      return isAsc ? valA - valB : valB - valA;
    }
    const strA = String(valA).toLowerCase();
    const strB = String(valB).toLowerCase();
    return isAsc ? strA.localeCompare(strB) : strB.localeCompare(strA);
  });

  state.history.filteredRecords = filtered;

  const badge = document.getElementById("badge-history-count");
  if (badge) badge.textContent = `${filtered.length} Records`;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">No matching historical records found for current filters.</td></tr>`;
    updatePaginationUI(0, 0, 0);
    return;
  }

  // 3. Paginate
  const pageSize = state.history.pageSize;
  const totalPages = Math.ceil(filtered.length / pageSize) || 1;
  if (state.history.page > totalPages) state.history.page = totalPages;
  if (state.history.page < 1) state.history.page = 1;

  const startIdx = (state.history.page - 1) * pageSize;
  const endIdx = Math.min(startIdx + pageSize, filtered.length);
  const pageRecords = filtered.slice(startIdx, endIdx);

  tbody.innerHTML = pageRecords
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

  updatePaginationUI(startIdx + 1, endIdx, filtered.length);
}

function updatePaginationUI(start, end, total) {
  const info = document.getElementById("history-pagination-info");
  if (info) {
    info.textContent = total > 0 ? `Showing ${start}–${end} of ${total} records` : "Showing 0 records";
  }

  const prevBtn = document.getElementById("btn-hist-prev");
  const nextBtn = document.getElementById("btn-hist-next");
  const pagesContainer = document.getElementById("history-pagination-pages");

  const totalPages = Math.ceil(total / state.history.pageSize) || 1;

  if (prevBtn) prevBtn.disabled = state.history.page <= 1;
  if (nextBtn) nextBtn.disabled = state.history.page >= totalPages;

  if (pagesContainer) {
    pagesContainer.innerHTML = "";
    const maxButtons = 5;
    let startPage = Math.max(1, state.history.page - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    if (endPage - startPage < maxButtons - 1) {
      startPage = Math.max(1, endPage - maxButtons + 1);
    }

    for (let p = startPage; p <= endPage; p++) {
      const btn = document.createElement("button");
      btn.className = `page-num-btn ${p === state.history.page ? "active" : ""}`;
      btn.textContent = p;
      btn.addEventListener("click", () => {
        state.history.page = p;
        renderHistoryTable();
      });
      pagesContainer.appendChild(btn);
    }
  }
}

function setupHistoryTableSortingAndExport() {
  document.querySelectorAll(".sortable-th").forEach((th) => {
    th.addEventListener("click", () => {
      const col = th.getAttribute("data-sort");
      if (state.history.sortColumn === col) {
        state.history.sortAsc = !state.history.sortAsc;
      } else {
        state.history.sortColumn = col;
        state.history.sortAsc = false;
      }

      document.querySelectorAll(".sortable-th").forEach((t) => {
        const icon = t.querySelector(".sort-icon");
        if (t === th) {
          icon.textContent = state.history.sortAsc ? "▲" : "▼";
        } else {
          icon.textContent = "↕";
        }
      });

      renderHistoryTable();
    });
  });

  const condSelect = document.getElementById("filter-history-condition");
  if (condSelect) {
    condSelect.addEventListener("change", () => {
      state.history.page = 1;
      renderHistoryTable();
    });
  }

  const limitSelect = document.getElementById("filter-history-limit");
  if (limitSelect) {
    limitSelect.addEventListener("change", () => {
      state.history.pageSize = parseInt(limitSelect.value, 10) || 50;
      state.history.page = 1;
      fetchWeatherHistory();
    });
  }

  const prevBtn = document.getElementById("btn-hist-prev");
  const nextBtn = document.getElementById("btn-hist-next");
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (state.history.page > 1) {
        state.history.page--;
        renderHistoryTable();
      }
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      const totalPages = Math.ceil(state.history.filteredRecords.length / state.history.pageSize) || 1;
      if (state.history.page < totalPages) {
        state.history.page++;
        renderHistoryTable();
      }
    });
  }

  const btnCsv = document.getElementById("btn-export-csv");
  const btnJson = document.getElementById("btn-export-json");
  if (btnCsv) btnCsv.addEventListener("click", exportHistoryCSV);
  if (btnJson) btnJson.addEventListener("click", exportHistoryJSON);
}

function exportHistoryCSV() {
  const records = state.history.filteredRecords || [];
  if (records.length === 0) {
    showToast("No historical records available to export.", "warning");
    return;
  }

  const headers = ["ID", "City", "Country", "Recorded_At_UTC", "Temperature_C", "Humidity_Percent", "Wind_Speed_KMH", "Weather_Condition", "Source"];
  const rows = records.map((r) => [
    r.weather_id,
    `"${(r.city_name || "").replace(/"/g, '""')}"`,
    `"${(r.country || "").replace(/"/g, '""')}"`,
    `"${(r.recorded_at || "").replace("T", " ")}"`,
    r.temperature_c !== null ? r.temperature_c : "",
    r.humidity_percent !== null ? r.humidity_percent : "",
    r.wind_speed_kmh !== null ? r.wind_speed_kmh : "",
    `"${(r.weather_condition || "").replace(/"/g, '""')}"`,
    `"${(r.source || "").replace(/"/g, '""')}"`
  ]);

  const csvContent = [headers.join(","), ...rows.map((row) => row.join(","))].join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `WeatherDataWarehouse_Export_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast(`✓ Exported ${records.length} records to CSV!`, "success");
}

function exportHistoryJSON() {
  const records = state.history.filteredRecords || [];
  if (records.length === 0) {
    showToast("No historical records available to export.", "warning");
    return;
  }

  const jsonContent = JSON.stringify(records, null, 2);
  const blob = new Blob([jsonContent], { type: "application/json;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `WeatherDataWarehouse_Export_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast(`✓ Exported ${records.length} records to JSON!`, "success");
}

// ----------------------------------------------------------------------------
// Pipeline Telemetry & Airflow-Style Visual DAG
// ----------------------------------------------------------------------------
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

function closeModal() {
  const modal = document.getElementById("modal-run-detail");
  if (modal) modal.classList.add("hidden");
}

window.closeModal = closeModal;

window.viewRunDetails = async function (runId) {
  try {
    const res = await fetch(`${API_BASE}/api/pipeline/runs/${runId}`);
    if (!res.ok) throw new Error("Failed to load run details");
    const data = await res.json();

    const modalTitle = document.getElementById("modal-title");
    if (modalTitle) modalTitle.textContent = `Pipeline Run #${data.run_id} Details`;

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

    const modalBody = document.getElementById("modal-body");
    if (modalBody) {
      modalBody.innerHTML = `
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
    }

    const modal = document.getElementById("modal-run-detail");
    if (modal) modal.classList.remove("hidden");
  } catch (err) {
    showAlert(`Could not load run details: ${err.message}`, "error");
  }
};

async function triggerETLPipeline(useSampleData = false) {
  const btn1 = document.getElementById("btn-run-pipeline");
  const btn2 = document.getElementById("btn-trigger-monitor");
  const dagStatus = document.getElementById("dag-overall-status");
  const step1 = document.getElementById("dag-step-1");
  const step2 = document.getElementById("dag-step-2");
  const step3 = document.getElementById("dag-step-3");
  const step4 = document.getElementById("dag-step-4");

  btn1.disabled = true;
  btn2.disabled = true;
  btn1.innerHTML = '<span class="btn-icon">⏳</span> Ingesting...';
  btn2.innerHTML = '<span class="btn-icon">⏳</span> Ingesting...';

  [step1, step2, step3, step4].forEach((s) => {
    if (s) s.classList.remove("active-running", "completed");
  });

  if (dagStatus) dagStatus.textContent = "DAG: 1/4 Ingesting WeatherAPI...";
  if (step1) step1.classList.add("active-running");
  showToast(`Triggering ${useSampleData ? "offline sample" : "live REST API"} ETL Pipeline...`, "info");

  const t1 = setTimeout(() => {
    if (step1) { step1.classList.remove("active-running"); step1.classList.add("completed"); }
    if (step2) step2.classList.add("active-running");
    if (dagStatus) dagStatus.textContent = "DAG: 2/4 Validating with Pandas...";
  }, 350);

  const t2 = setTimeout(() => {
    if (step2) { step2.classList.remove("active-running"); step2.classList.add("completed"); }
    if (step3) step3.classList.add("active-running");
    if (dagStatus) dagStatus.textContent = "DAG: 3/4 Upserting into SQL Server...";
  }, 700);

  try {
    const res = await fetch(`${API_BASE}/api/pipeline/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_sample_data: useSampleData }),
    });

    clearTimeout(t1);
    clearTimeout(t2);

    const result = await res.json();

    if (step1) { step1.classList.remove("active-running"); step1.classList.add("completed"); }
    if (step2) { step2.classList.remove("active-running"); step2.classList.add("completed"); }
    if (step3) { step3.classList.remove("active-running"); step3.classList.add("completed"); }
    if (step4) { step4.classList.add("completed"); }

    if (res.ok && result.success) {
      if (dagStatus) dagStatus.textContent = "DAG: Ingestion Complete (100% Quality)";
      showToast(
        `✓ ETL Success: Extracted ${result.records_extracted}, Loaded ${result.records_loaded}, Skipped ${result.duplicates_skipped} duplicates.`,
        "success"
      );
    } else {
      if (dagStatus) dagStatus.textContent = "DAG: Completed with Warnings";
      showToast(`Pipeline Run: ${result.message || result.error || "Failed"}`, "error");
    }

    await fetchAllData();
  } catch (err) {
    clearTimeout(t1);
    clearTimeout(t2);
    console.error("Pipeline trigger error:", err);
    if (dagStatus) dagStatus.textContent = "DAG: Failed";
    showToast(`Failed to execute ETL pipeline: ${err.message}`, "error");
  } finally {
    btn1.disabled = false;
    btn2.disabled = false;
    btn1.innerHTML = '<span class="btn-icon">▶</span> Run ETL';
    btn2.innerHTML = '▶ Trigger ETL Pipeline';
    setTimeout(() => {
      if (dagStatus) dagStatus.textContent = "DAG: Standby / Ready";
    }, 6000);
  }
}

// ----------------------------------------------------------------------------
// Station Detail Slide-Over Drawer
// ----------------------------------------------------------------------------
let currentDrawerCity = "";

function setupStationDrawer() {
  const closeBtn = document.getElementById("btn-close-drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  if (closeBtn) closeBtn.addEventListener("click", closeStationDrawer);
  if (backdrop) backdrop.addEventListener("click", closeStationDrawer);

  const btnHistory = document.getElementById("btn-drawer-filter-history");
  if (btnHistory) {
    btnHistory.addEventListener("click", () => {
      closeStationDrawer();
      quickFilterCity(currentDrawerCity);
    });
  }

  const btnGenAI = document.getElementById("btn-drawer-ask-genai");
  if (btnGenAI) {
    btnGenAI.addEventListener("click", () => {
      closeStationDrawer();
      const genaiBtn = document.querySelector('[data-target="section-genai"]');
      if (genaiBtn) genaiBtn.click();
      const input = document.getElementById("genai-question-input");
      if (input) {
        input.value = `Provide a full meteorological summary and historical trends for ${currentDrawerCity}`;
        askGenAIQuestion(input.value);
      }
    });
  }
}

function closeStationDrawer() {
  const drawer = document.getElementById("city-detail-drawer");
  if (drawer) drawer.classList.add("hidden");
}

async function openStationDrawerByCity(cityName) {
  const station = (state.latestWeather || []).find(
    (s) => s.city_name.toLowerCase() === cityName.toLowerCase()
  ) || { city_name: cityName, country: "Global Station", weather_condition: "Observed" };
  openStationDrawer(station);
}

window.openStationDrawerByCity = openStationDrawerByCity;

async function openStationDrawer(station) {
  currentDrawerCity = station.city_name;
  const drawer = document.getElementById("city-detail-drawer");
  if (!drawer) return;

  const visuals = getWeatherVisuals(station.weather_condition);

  document.getElementById("drawer-city-name").textContent = station.city_name;
  document.getElementById("drawer-country-name").textContent = station.country || "Global Station";
  document.getElementById("drawer-temp").textContent = station.temperature_c !== null && station.temperature_c !== undefined ? `${station.temperature_c}°C` : "--°C";
  document.getElementById("drawer-cond").innerHTML = `${visuals.icon} ${station.weather_condition || "Observed"}`;
  document.getElementById("drawer-humidity").textContent = station.humidity_percent !== null && station.humidity_percent !== undefined ? `${station.humidity_percent}%` : "--%";
  document.getElementById("drawer-wind").textContent = station.wind_speed_kmh !== null && station.wind_speed_kmh !== undefined ? `${station.wind_speed_kmh} km/h` : "-- km/h";
  document.getElementById("drawer-lat").textContent = station.latitude ? Number(station.latitude).toFixed(4) : "Monitored";
  document.getElementById("drawer-lon").textContent = station.longitude ? Number(station.longitude).toFixed(4) : "Monitored";
  document.getElementById("drawer-loc-id").textContent = `#${station.location_id || 1}`;
  document.getElementById("drawer-sync-time").textContent = formatFriendlyTime(station.recorded_at);

  drawer.classList.remove("hidden");

  try {
    const res = await fetch(`${API_BASE}/api/weather/history?city=${encodeURIComponent(station.city_name)}&limit=24`);
    if (res.ok) {
      const records = await res.json();
      renderDrawerChart(records.reverse());
    }
  } catch (e) {
    console.error("Drawer chart trend fetch failed:", e);
  }
}

function renderDrawerChart(records) {
  const canvas = document.getElementById("chart-drawer-trend");
  if (!canvas) return;

  if (drawerTrendChart) {
    drawerTrendChart.destroy();
    drawerTrendChart = null;
  }

  const labels = records.map((r) => {
    const d = new Date(r.recorded_at);
    return isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  });
  const temps = records.map((r) => r.temperature_c);

  const ctx = canvas.getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 0, 160);
  gradient.addColorStop(0, "rgba(56, 189, 248, 0.45)");
  gradient.addColorStop(1, "rgba(56, 189, 248, 0.0)");

  drawerTrendChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Temperature (°C)",
          data: temps,
          borderColor: "#38bdf8",
          backgroundColor: gradient,
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointRadius: 3,
          pointBackgroundColor: "#38bdf8",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0d1527",
          titleColor: "#38bdf8",
          bodyColor: "#ffffff",
          borderColor: "rgba(56, 189, 248, 0.3)",
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          ticks: { color: "#64748b", font: { size: 10 } },
          grid: { display: false },
        },
        y: {
          ticks: { color: "#64748b", font: { size: 10 } },
          grid: { color: "rgba(255, 255, 255, 0.05)" },
        },
      },
    },
  });
}

// ----------------------------------------------------------------------------
// Global Command Palette (Ctrl+K)
// ----------------------------------------------------------------------------
let cmdActiveIndex = 0;
let cmdItems = [];

function setupCommandPalette() {
  const modal = document.getElementById("command-palette-modal");
  const input = document.getElementById("cmd-palette-input");
  const btnOpen = document.getElementById("btn-open-cmd");
  const btnClose = document.getElementById("btn-close-cmd");
  const backdrop = document.getElementById("cmd-palette-backdrop");

  if (btnOpen) btnOpen.addEventListener("click", openCommandPalette);
  if (btnClose) btnClose.addEventListener("click", closeCommandPalette);
  if (backdrop) backdrop.addEventListener("click", closeCommandPalette);

  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (modal && modal.classList.contains("hidden")) {
        openCommandPalette();
      } else {
        closeCommandPalette();
      }
    } else if (e.key === "Escape") {
      closeCommandPalette();
      closeStationDrawer();
    }
  });

  if (input) {
    input.addEventListener("input", () => {
      renderCommandPaletteResults(input.value.trim());
    });

    input.addEventListener("keydown", (e) => {
      const list = document.getElementById("cmd-palette-list");
      const items = list ? list.querySelectorAll(".cmd-item") : [];

      if (e.key === "ArrowDown") {
        e.preventDefault();
        cmdActiveIndex = (cmdActiveIndex + 1) % items.length;
        updateCmdActiveItem(items);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        cmdActiveIndex = (cmdActiveIndex - 1 + items.length) % items.length;
        updateCmdActiveItem(items);
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (cmdItems[cmdActiveIndex]) {
          executeCommandItem(cmdItems[cmdActiveIndex]);
        }
      }
    });
  }
}

function openCommandPalette() {
  const modal = document.getElementById("command-palette-modal");
  const input = document.getElementById("cmd-palette-input");
  if (!modal) return;
  modal.classList.remove("hidden");
  if (input) {
    input.value = "";
    input.focus();
  }
  renderCommandPaletteResults("");
}

function closeCommandPalette() {
  const modal = document.getElementById("command-palette-modal");
  if (modal) modal.classList.add("hidden");
}

function renderCommandPaletteResults(query) {
  const list = document.getElementById("cmd-palette-list");
  if (!list) return;

  const defaultCommands = [
    { type: "nav", id: "section-dashboard", icon: "🏠", label: "Go to Dashboard Overview", badge: "Navigation" },
    { type: "nav", id: "section-history", icon: "📜", label: "Go to Weather Warehouse History", badge: "Navigation" },
    { type: "nav", id: "section-analytics", icon: "📊", label: "Go to Meteorological Analytics & Trends", badge: "Navigation" },
    { type: "nav", id: "section-pipeline", icon: "⚡", label: "Go to ETL Pipeline Monitor", badge: "Navigation" },
    { type: "nav", id: "section-genai", icon: "🤖", label: "Go to GenAI Natural Language Assistant", badge: "Navigation" },
    { type: "action", action: "run-etl", icon: "▶", label: "Trigger Real-Time ETL Pipeline", badge: "Action" },
    { type: "action", action: "export-csv", icon: "⬇", label: "Export Filtered Weather History to CSV", badge: "Action" },
    { type: "action", action: "export-json", icon: "⬇", label: "Export Filtered Weather History to JSON", badge: "Action" },
    { type: "action", action: "refresh-data", icon: "🔄", label: "Refresh All Monitored Stations", badge: "Action" },
    { type: "link", url: "/json-to-ui", icon: "✨", label: "Open Universal JSON to UI Studio", badge: "Portal" },
    { type: "link", url: "/links", icon: "🌐", label: "Open All Links Directory Portal", badge: "Portal" },
    { type: "link", url: "/docs", icon: "📖", label: "Open Swagger Interactive API Docs", badge: "Portal" },
  ];

  const q = query.toLowerCase();
  let results = defaultCommands.filter((c) => c.label.toLowerCase().includes(q) || c.badge.toLowerCase().includes(q));

  if (q.length >= 2) {
    (state.latestWeather || []).forEach((w) => {
      if (w.city_name.toLowerCase().includes(q)) {
        results.unshift({
          type: "city",
          cityName: w.city_name,
          icon: "📍",
          label: `Inspect Station: ${w.city_name} (${w.temperature_c}°C, ${w.weather_condition})`,
          badge: "Station",
        });
      }
    });

    results.push({
      type: "search-ingest",
      cityQuery: query,
      icon: "🌐",
      label: `Live Search & Ingest "${query}" from Global Weather API`,
      badge: "Ingestion",
    });
  }

  cmdItems = results.slice(0, 8);
  cmdActiveIndex = 0;

  if (cmdItems.length === 0) {
    list.innerHTML = '<div style="padding: 1rem; color: #64748b; text-align: center;">No matching actions found.</div>';
    return;
  }

  list.innerHTML = cmdItems
    .map(
      (it, idx) => `
      <div class="cmd-item ${idx === 0 ? "active" : ""}" data-index="${idx}">
        <div class="cmd-item-left">
          <span class="cmd-item-icon">${it.icon}</span>
          <span class="cmd-item-text">${it.label}</span>
        </div>
        <span class="cmd-item-badge">${it.badge}</span>
      </div>
    `
    )
    .join("");

  list.querySelectorAll(".cmd-item").forEach((el) => {
    el.addEventListener("click", () => {
      const idx = parseInt(el.getAttribute("data-index"), 10);
      if (cmdItems[idx]) executeCommandItem(cmdItems[idx]);
    });
  });
}

function updateCmdActiveItem(items) {
  items.forEach((it, idx) => {
    if (idx === cmdActiveIndex) {
      it.classList.add("active");
      it.scrollIntoView({ block: "nearest" });
    } else {
      it.classList.remove("active");
    }
  });
}

function executeCommandItem(item) {
  closeCommandPalette();
  if (item.type === "nav") {
    const btn = document.querySelector(`.nav-btn[data-target="${item.id}"]`);
    if (btn) btn.click();
  } else if (item.type === "action") {
    if (item.action === "run-etl") triggerETLPipeline(false);
    if (item.action === "export-csv") exportHistoryCSV();
    if (item.action === "export-json") exportHistoryJSON();
    if (item.action === "refresh-data") fetchAllData();
  } else if (item.type === "link") {
    window.open(item.url, "_blank");
  } else if (item.type === "city") {
    openStationDrawerByCity(item.cityName);
  } else if (item.type === "search-ingest") {
    searchAndIngestCity(item.cityQuery);
  }
}

// ----------------------------------------------------------------------------
// Live Auto-Refresh Controller
// ----------------------------------------------------------------------------
function setupAutoRefresh() {
  const select = document.getElementById("select-auto-refresh");
  const badge = document.getElementById("badge-refresh-countdown");
  if (!select || !badge) return;

  select.addEventListener("change", () => {
    if (state.autoRefresh.timerId) {
      clearInterval(state.autoRefresh.timerId);
      state.autoRefresh.timerId = null;
    }

    const interval = parseInt(select.value, 10);
    state.autoRefresh.intervalSec = interval;
    state.autoRefresh.remainingSec = interval;

    if (interval === 0) {
      badge.textContent = "Sync: Idle";
      showToast("Auto-refresh disabled.", "info");
      return;
    }

    badge.textContent = `Sync in ${interval}s`;
    showToast(`✓ Auto-sync enabled: refreshing every ${interval}s`, "info");

    state.autoRefresh.timerId = setInterval(async () => {
      state.autoRefresh.remainingSec--;
      if (state.autoRefresh.remainingSec <= 0) {
        state.autoRefresh.remainingSec = state.autoRefresh.intervalSec;
        badge.textContent = "Syncing...";
        await fetchAllData();
        showToast("✓ Warehouse observations auto-synchronized.", "info");
      }
      badge.textContent = `Sync in ${state.autoRefresh.remainingSec}s`;
    }, 1000);
  });
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

  const dataset = (latestData && latestData.length > 0) ? latestData : state.latestWeather;
  if (!dataset || dataset.length === 0) return;
  if (cityDistChart) cityDistChart.destroy();

  const labels = dataset.map((d) => d.city_name);
  const temps = dataset.map((d) => d.temperature_c);
  const humidities = dataset.map((d) => d.humidity_percent);

  cityDistChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Current Temperature (°C)",
          data: temps,
          backgroundColor: "rgba(249, 115, 22, 0.75)",
          borderColor: "#f97316",
          borderWidth: 1.5,
          borderRadius: 4,
        },
        {
          label: "Relative Humidity (%)",
          data: humidities,
          backgroundColor: "rgba(6, 182, 212, 0.75)",
          borderColor: "#06b6d4",
          borderWidth: 1.5,
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#cbd5e1" } },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y !== null ? ctx.parsed.y + (ctx.datasetIndex === 0 ? "°C" : "%") : "--"}`,
          },
        },
      },
      scales: {
        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
      },
    },
  });
}

// ============================================================================
// Advanced Analytics Suite: Multi-Chart Visualization Engine
// ============================================================================
async function fetchAdvancedAnalytics() {
  try {
    const [condRes, metricsRes, trendRes, corrRes] = await Promise.all([
      fetch(`${API_BASE}/api/analytics/conditions`),
      fetch(`${API_BASE}/api/analytics/city-metrics`),
      fetch(`${API_BASE}/api/analytics/temperature-trend?days=7`),
      fetch(`${API_BASE}/api/analytics/correlation?limit=200`),
    ]);

    const conditions = condRes.ok ? await condRes.json() : [];
    const cityMetrics = metricsRes.ok ? await metricsRes.json() : [];
    const trendData = trendRes.ok ? await trendRes.json() : [];
    const correlationData = corrRes.ok ? await corrRes.json() : [];

    const badge = document.getElementById("badge-analytics-records");
    if (badge && correlationData.length > 0) {
      badge.textContent = `${correlationData.length}+ Observations Ingested`;
    }

    renderCityDistributionChart(state.latestWeather);
    renderConditionDonut(conditions);
    renderStationPolar(cityMetrics);
    renderMultiStationTrend(trendData);
    renderCityRadar(cityMetrics);
    renderCorrelationScatter(correlationData);
    renderThermalRanked(cityMetrics);
  } catch (err) {
    console.error("fetchAdvancedAnalytics error:", err);
  }
}

function renderConditionDonut(conditions) {
  const canvas = document.getElementById("chart-condition-donut");
  if (!canvas || !conditions || conditions.length === 0) return;
  if (chartConditionDonut) chartConditionDonut.destroy();

  const labels = conditions.map((c) => c.condition);
  const counts = conditions.map((c) => c.record_count);
  const palette = [
    "#38bdf8", "#0ea5e9", "#06b6d4", "#10b981", "#34d399",
    "#f59e0b", "#fbbf24", "#f97316", "#ef4444", "#a855f7",
    "#8b5cf6", "#6366f1", "#ec4899", "#14b8a6", "#94a3b8", "#64748b"
  ];

  chartConditionDonut = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: counts,
          backgroundColor: palette.slice(0, conditions.length),
          borderColor: "#0f172a",
          borderWidth: 2,
          hoverOffset: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "65%",
      plugins: {
        legend: {
          position: "right",
          labels: {
            color: "#cbd5e1",
            font: { size: 11 },
            boxWidth: 12,
            padding: 8,
          },
        },
        tooltip: {
          callbacks: {
            label: function (ctx) {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const val = ctx.parsed;
              const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
              return ` ${ctx.label}: ${val} records (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

function renderStationPolar(cityMetrics) {
  const canvas = document.getElementById("chart-station-polar");
  if (!canvas || !cityMetrics || cityMetrics.length === 0) return;
  if (chartStationPolar) chartStationPolar.destroy();

  const labels = cityMetrics.map((c) => c.city_name);
  const counts = cityMetrics.map((c) => c.total_records);
  const bgColors = cityMetrics.map(
    (_, i) => `hsla(${(i * 360) / cityMetrics.length}, 80%, 60%, 0.65)`
  );

  chartStationPolar = new Chart(canvas, {
    type: "polarArea",
    data: {
      labels,
      datasets: [
        {
          data: counts,
          backgroundColor: bgColors,
          borderColor: "rgba(15, 23, 42, 0.8)",
          borderWidth: 1.5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          grid: { color: "rgba(255, 255, 255, 0.08)" },
          angleLines: { color: "rgba(255, 255, 255, 0.1)" },
          ticks: { color: "#94a3b8", backdropColor: "transparent", font: { size: 10 } },
        },
      },
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#cbd5e1", font: { size: 11 }, boxWidth: 10, padding: 6 },
        },
      },
    },
  });
}

function renderMultiStationTrend(trendData) {
  const canvas = document.getElementById("chart-multicity-trend");
  if (!canvas || !trendData || trendData.length === 0) return;
  if (chartMultiCityTrend) chartMultiCityTrend.destroy();

  // Distinct dates sorted
  const dates = Array.from(new Set(trendData.map((t) => t.date))).sort();

  // Top 5 cities by frequency
  const cityCounts = {};
  trendData.forEach((t) => (cityCounts[t.city_name] = (cityCounts[t.city_name] || 0) + 1));
  const topCities = Object.keys(cityCounts)
    .sort((a, b) => cityCounts[b] - cityCounts[a])
    .slice(0, 5);

  const colors = ["#38bdf8", "#f97316", "#10b981", "#a855f7", "#fbbf24"];

  const datasets = topCities.map((cityName, idx) => {
    const cityRows = trendData.filter((t) => t.city_name === cityName);
    const rowMap = new Map(cityRows.map((r) => [r.date, r.avg_temperature]));
    const data = dates.map((d) => (rowMap.has(d) ? rowMap.get(d) : null));
    const col = colors[idx % colors.length];

    return {
      label: cityName,
      data,
      borderColor: col,
      backgroundColor: col + "20",
      tension: 0.35,
      borderWidth: 2.2,
      pointRadius: 3,
      pointHoverRadius: 6,
      spanGaps: true,
    };
  });

  chartMultiCityTrend = new Chart(canvas, {
    type: "line",
    data: { labels: dates, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#cbd5e1", boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y !== null ? ctx.parsed.y + "°C" : "No Data"}`,
          },
        },
      },
      scales: {
        x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255, 255, 255, 0.05)" } },
        y: {
          ticks: { color: "#64748b", callback: (v) => `${v}°C` },
          grid: { color: "rgba(255, 255, 255, 0.05)" },
        },
      },
    },
  });
}

function renderCityRadar(cityMetrics) {
  const canvas = document.getElementById("chart-city-radar");
  if (!canvas || !cityMetrics || cityMetrics.length === 0) return;
  if (chartCityRadar) chartCityRadar.destroy();

  // Select 4 contrasting cities
  const candidateNames = ["Mumbai", "Bangalore", "Delhi", "Dubai", "London", "Cairo", "Tokyo"];
  const selectedCities = cityMetrics
    .filter((c) => candidateNames.includes(c.city_name))
    .slice(0, 4);

  if (selectedCities.length === 0) {
    selectedCities.push(...cityMetrics.slice(0, 4));
  }

  const radarColors = [
    { border: "#38bdf8", bg: "rgba(56, 189, 248, 0.25)" },
    { border: "#f97316", bg: "rgba(249, 115, 22, 0.25)" },
    { border: "#10b981", bg: "rgba(16, 185, 129, 0.25)" },
    { border: "#a855f7", bg: "rgba(168, 85, 247, 0.25)" },
  ];

  const datasets = selectedCities.map((c, idx) => {
    const col = radarColors[idx % radarColors.length];
    return {
      label: c.city_name,
      data: [
        c.avg_temp,
        c.avg_humidity,
        c.avg_wind,
        c.max_temp,
        Math.min(c.total_records * 4, 100),
      ],
      borderColor: col.border,
      backgroundColor: col.bg,
      borderWidth: 2,
      pointBackgroundColor: col.border,
      pointRadius: 3,
    };
  });

  chartCityRadar = new Chart(canvas, {
    type: "radar",
    data: {
      labels: ["Avg Temp (°C)", "Humidity (%)", "Wind (km/h)", "Max Temp (°C)", "Records Vol."],
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          angleLines: { color: "rgba(255, 255, 255, 0.1)" },
          grid: { color: "rgba(255, 255, 255, 0.08)" },
          pointLabels: { color: "#cbd5e1", font: { size: 10.5, weight: "bold" } },
          ticks: { display: false },
        },
      },
      plugins: {
        legend: { labels: { color: "#cbd5e1", boxWidth: 10 } },
      },
    },
  });
}

function renderCorrelationScatter(correlationData) {
  const canvas = document.getElementById("chart-correlation-scatter");
  if (!canvas || !correlationData || correlationData.length === 0) return;
  if (chartCorrelationScatter) chartCorrelationScatter.destroy();

  const points = correlationData.map((d) => ({
    x: d.temperature_c,
    y: d.humidity_percent,
    city: d.city_name,
    wind: d.wind_speed_kmh,
    condition: d.weather_condition,
  }));

  chartCorrelationScatter = new Chart(canvas, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Warehouse Observations",
          data: points,
          backgroundColor: "rgba(56, 189, 248, 0.65)",
          borderColor: "#38bdf8",
          borderWidth: 1,
          pointRadius: 5.5,
          pointHoverRadius: 9,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#cbd5e1" } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const p = ctx.raw;
              return ` ${p.city}: ${p.x}°C, ${p.y}% Humidity (${p.condition}, Wind: ${p.wind} km/h)`;
            },
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Temperature (°C)", color: "#94a3b8", font: { weight: "bold" } },
          ticks: { color: "#64748b" },
          grid: { color: "rgba(255, 255, 255, 0.05)" },
        },
        y: {
          title: { display: true, text: "Relative Humidity (%)", color: "#94a3b8", font: { weight: "bold" } },
          ticks: { color: "#64748b" },
          grid: { color: "rgba(255, 255, 255, 0.05)" },
        },
      },
    },
  });
}

function renderThermalRanked(cityMetrics) {
  const canvas = document.getElementById("chart-thermal-ranked");
  if (!canvas || !cityMetrics || cityMetrics.length === 0) return;
  if (chartThermalRanked) chartThermalRanked.destroy();

  const sorted = [...cityMetrics].sort((a, b) => b.avg_temp - a.avg_temp);
  const labels = sorted.map((c) => c.city_name);
  const avgTemps = sorted.map((c) => c.avg_temp);
  const maxTemps = sorted.map((c) => c.max_temp);

  const barColors = avgTemps.map((t) => {
    if (t >= 32) return "rgba(239, 68, 68, 0.85)"; // Red
    if (t >= 28) return "rgba(249, 115, 22, 0.85)"; // Orange
    if (t >= 22) return "rgba(245, 158, 11, 0.85)"; // Amber
    return "rgba(56, 189, 248, 0.85)"; // Cyan
  });

  chartThermalRanked = new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Mean Temperature (°C)",
          data: avgTemps,
          backgroundColor: barColors,
          borderRadius: 4,
          borderWidth: 0,
        },
        {
          label: "Peak Recorded Temperature (°C)",
          data: maxTemps,
          backgroundColor: "rgba(255, 255, 255, 0.15)",
          borderColor: "rgba(255, 255, 255, 0.3)",
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#cbd5e1" } },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.x}°C`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#64748b", callback: (v) => `${v}°C` },
          grid: { color: "rgba(255, 255, 255, 0.05)" },
        },
        y: {
          ticks: { color: "#e2e8f0", font: { weight: "bold" } },
          grid: { display: false },
        },
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

  // Clear AI Query Cache Button
  const btnClearCache = document.getElementById("btn-clear-ai-cache");
  if (btnClearCache) {
    btnClearCache.addEventListener("click", async () => {
      try {
        btnClearCache.disabled = true;
        btnClearCache.textContent = "Clearing...";
        const res = await fetch(`${API_BASE}/api/genai/clear-cache`, { method: "POST" });
        if (res.ok) {
          showToast("GenAI query cache purged successfully!", "success");
          loadAiConfig();
        }
      } catch (e) {
        console.error("Failed to clear cache:", e);
      } finally {
        btnClearCache.disabled = false;
        btnClearCache.textContent = "🧹 Clear Cache";
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

    const cacheIndicator = document.getElementById("ai-cache-indicator");
    if (cacheIndicator && cfg.cache_stats) {
      cacheIndicator.textContent = `Cache: ${cfg.cache_stats.cached_entries} items (${cfg.cache_stats.hit_rate} hit rate)`;
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
  btn.innerHTML = '<span class="btn-icon">⚡</span> Executing Query...';

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

    // Display latency and cache telemetry
    const speedPill = document.getElementById("genai-speed-pill");
    const modelPill = document.getElementById("genai-model-pill");
    if (speedPill) {
      if (data.cached) {
        speedPill.textContent = `⚡ Cached (${data.latency_ms || 0.8}ms)`;
        speedPill.style.color = "#38bdf8";
        speedPill.style.background = "rgba(56, 189, 248, 0.15)";
        speedPill.style.borderColor = "rgba(56, 189, 248, 0.35)";
      } else {
        const ms = data.latency_ms || 250;
        const sec = (ms / 1000).toFixed(2);
        speedPill.textContent = ms < 1000 ? `⚡ ${ms}ms` : `⚡ ${sec}s`;
        speedPill.style.color = "#10b981";
        speedPill.style.background = "rgba(16, 185, 129, 0.15)";
        speedPill.style.borderColor = "rgba(16, 185, 129, 0.35)";
      }
    }
    if (modelPill) {
      modelPill.textContent = data.model || data.provider || "Gemini Flash Lite";
    }

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
    loadAiConfig();
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
  const suggestionsBox = document.getElementById("search-suggestions-box");
  if (!searchInput || !searchBtn) return;

  let debounceTimer = null;
  let activeSuggestionIndex = -1;
  let currentSuggestions = [];

  // Live Auto-Suggest as user types (e.g. 'mum' -> 'Mumbai')
  searchInput.addEventListener("input", () => {
    const q = searchInput.value.trim();
    clearTimeout(debounceTimer);
    activeSuggestionIndex = -1;

    if (q.length < 2) {
      hideSuggestions();
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/weather/suggest?q=${encodeURIComponent(q)}`);
        if (!res.ok) return;
        const suggestions = await res.json();
        currentSuggestions = suggestions;
        renderSuggestions(suggestions, q);
      } catch (err) {
        console.error("Auto-suggest error:", err);
      }
    }, 180);
  });

  // Keyboard navigation on suggestions
  searchInput.addEventListener("keydown", (e) => {
    if (!suggestionsBox || suggestionsBox.classList.contains("hidden")) {
      if (e.key === "Enter") {
        const q = searchInput.value.trim();
        if (q) searchAndIngestCity(q);
      }
      return;
    }

    const items = suggestionsBox.querySelectorAll(".suggestion-item");
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeSuggestionIndex = (activeSuggestionIndex + 1) % items.length;
      updateActiveSuggestion(items);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeSuggestionIndex = (activeSuggestionIndex - 1 + items.length) % items.length;
      updateActiveSuggestion(items);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeSuggestionIndex >= 0 && activeSuggestionIndex < currentSuggestions.length) {
        selectSuggestion(currentSuggestions[activeSuggestionIndex]);
      } else {
        hideSuggestions();
        const q = searchInput.value.trim();
        if (q) searchAndIngestCity(q);
      }
    } else if (e.key === "Escape") {
      hideSuggestions();
    }
  });

  function updateActiveSuggestion(items) {
    items.forEach((it, idx) => {
      if (idx === activeSuggestionIndex) {
        it.classList.add("active");
        it.scrollIntoView({ block: "nearest" });
      } else {
        it.classList.remove("active");
      }
    });
  }

  function renderSuggestions(suggestions, query) {
    if (!suggestionsBox) return;
    if (!suggestions || suggestions.length === 0) {
      hideSuggestions();
      return;
    }

    const regex = new RegExp(`(${query})`, "gi");
    suggestionsBox.innerHTML = suggestions
      .map((item, idx) => {
        const highlightedName = item.name.replace(regex, "<mark>$1</mark>");
        const sub = item.region ? `${item.region}, ${item.country}` : item.country;
        const badgeClass = item.source === "warehouse" ? "suggestion-badge warehouse" : "suggestion-badge";
        const badgeLabel = item.source === "warehouse" ? "Saved" : "Global";

        return `
          <div class="suggestion-item" data-index="${idx}">
            <div class="suggestion-main">
              <span class="suggestion-icon">📍</span>
              <div>
                <span class="suggestion-name">${highlightedName}</span>
                <span class="suggestion-sub">${sub || ""}</span>
              </div>
            </div>
            <span class="${badgeClass}">${badgeLabel}</span>
          </div>
        `;
      })
      .join("");

    suggestionsBox.querySelectorAll(".suggestion-item").forEach((el) => {
      el.addEventListener("click", () => {
        const idx = parseInt(el.getAttribute("data-index"), 10);
        if (currentSuggestions[idx]) {
          selectSuggestion(currentSuggestions[idx]);
        }
      });
    });

    suggestionsBox.classList.remove("hidden");
  }

  function selectSuggestion(item) {
    searchInput.value = item.name;
    hideSuggestions();
    searchAndIngestCity(item.name);
  }

  function hideSuggestions() {
    if (suggestionsBox) suggestionsBox.classList.add("hidden");
    activeSuggestionIndex = -1;
  }

  // Close suggestions when clicking outside
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-capsule-wrapper")) {
      hideSuggestions();
    }
  });

  searchBtn.addEventListener("click", () => {
    hideSuggestions();
    const q = searchInput.value.trim();
    if (q) searchAndIngestCity(q);
  });

  // Quick Ingest City Chips
  document.querySelectorAll(".city-chip-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const city = btn.getAttribute("data-city");
      searchInput.value = city;
      hideSuggestions();
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

    // Also update synoptic atmospheric hero card & forecasts
    fetchSynopticWeather(data.city_name);

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
    btn.innerHTML = '<span>Search & Ingest</span> &rarr;';
  }
}

// ============================================================================
// SKYCAST SYNOPTIC METEOROLOGICAL INTELLIGENCE & GEOLOCATION
// ============================================================================

let currentSynopticCity = "Chennai";

async function fetchSynopticWeather(query) {
  if (!query) return;
  try {
    const res = await fetch(`${API_BASE}/api/weather/synoptic?q=${encodeURIComponent(query)}&days=5`);
    if (!res.ok) throw new Error(`Synoptic query failed (${res.status})`);
    const data = await res.json();
    if (!data.success) throw new Error("Could not parse synoptic weather payload");

    renderSynopticUI(data);
    currentSynopticCity = data.location.name;
    saveSearchHistory(data.location.name);
    updateFavoriteButtonState();
    renderFavorites();
  } catch (err) {
    console.error("fetchSynopticWeather error:", err);
  }
}

function renderSynopticUI(data) {
  const loc = data.location;
  const cur = data.current;
  const astro = data.astro;

  // 1. Hero Card
  const cityNameEl = document.getElementById("syn-city-name");
  const condTextEl = document.getElementById("syn-condition-text");
  const tempMainEl = document.getElementById("syn-temp-main");
  const feelsLikeEl = document.getElementById("syn-feels-like");
  const windSummaryEl = document.getElementById("syn-wind-summary");
  const iconEl = document.getElementById("syn-weather-icon");
  const obsTimeEl = document.getElementById("syn-obs-time");

  if (cityNameEl) cityNameEl.textContent = `${loc.name}${loc.country ? `, ${loc.country}` : ""}`;
  if (condTextEl) condTextEl.textContent = cur.condition;
  if (tempMainEl) tempMainEl.textContent = `${cur.temp_c}°C`;
  if (feelsLikeEl) feelsLikeEl.textContent = `Feels Like ${cur.feelslike_c}°C`;
  if (windSummaryEl) windSummaryEl.textContent = `Wind: ${cur.wind_kph} km/h ${cur.wind_dir}`;
  if (iconEl && cur.icon) iconEl.src = cur.icon;
  if (obsTimeEl) obsTimeEl.textContent = `Synoptic Stream • ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;

  // 2. 8 Gauges
  const tempEl = document.getElementById("syn-temp");
  const humEl = document.getElementById("syn-humidity");
  const windEl = document.getElementById("syn-wind");
  const visEl = document.getElementById("syn-visibility");
  const uvEl = document.getElementById("syn-uv");
  const uvBadgeEl = document.getElementById("syn-uv-badge");
  const pressEl = document.getElementById("syn-pressure");
  const aqiEl = document.getElementById("syn-aqi");
  const aqiBadgeEl = document.getElementById("syn-aqi-badge");
  const astroEl = document.getElementById("syn-astro");

  if (tempEl) tempEl.textContent = `${cur.temp_c}°C`;
  if (humEl) humEl.textContent = `${cur.humidity}%`;
  if (windEl) windEl.textContent = `${cur.wind_kph} km/h`;
  if (visEl) visEl.textContent = `${cur.vis_km} km`;

  if (uvEl) uvEl.textContent = cur.uv;
  if (uvBadgeEl) {
    const uvVal = parseFloat(cur.uv) || 0;
    uvBadgeEl.className = "syn-badge badge-uv";
    if (uvVal < 3) {
      uvBadgeEl.textContent = "Low";
      uvBadgeEl.classList.add("low");
    } else if (uvVal < 6) {
      uvBadgeEl.textContent = "Moderate";
      uvBadgeEl.classList.add("moderate");
    } else {
      uvBadgeEl.textContent = "High Risk";
      uvBadgeEl.classList.add("high");
    }
  }

  if (pressEl) pressEl.textContent = `${cur.pressure_mb} mb`;

  if (aqiEl) aqiEl.textContent = cur.aqi;
  if (aqiBadgeEl) {
    aqiBadgeEl.textContent = cur.aqi_desc || "Moderate";
    aqiBadgeEl.className = "syn-badge badge-aqi";
    if (cur.aqi === 1) aqiBadgeEl.classList.add("good");
    else if (cur.aqi === 2) aqiBadgeEl.classList.add("moderate");
    else aqiBadgeEl.classList.add("unhealthy");
  }

  if (astroEl && astro) {
    astroEl.textContent = `↑ ${astro.sunrise || "06:00 AM"}  ↓ ${astro.sunset || "06:15 PM"}`;
  }

  // 3. Hourly Forecast Carousel
  const hourlyCarousel = document.getElementById("syn-hourly-carousel");
  if (hourlyCarousel && data.hourly && data.hourly.length > 0) {
    hourlyCarousel.innerHTML = data.hourly.map((h) => `
      <div class="syn-hour-card">
        <span class="syn-hour-time">${h.time}</span>
        <img class="syn-hour-icon" src="${h.icon}" alt="${h.condition}">
        <span class="syn-hour-temp">${h.temp_c}°C</span>
        ${h.chance_of_rain > 0 ? `<span class="syn-hour-rain">💧 ${h.chance_of_rain}%</span>` : `<span style="font-size:0.68rem;color:#64748b;">${h.condition.slice(0, 10)}</span>`}
      </div>
    `).join("");
  }

  // 4. 5-Day Outlook Grid
  const forecastGrid = document.getElementById("syn-forecast-grid");
  if (forecastGrid && data.forecast && data.forecast.length > 0) {
    forecastGrid.innerHTML = data.forecast.map((d) => `
      <div class="syn-day-card">
        <span class="syn-day-name">${d.day_name}</span>
        <span class="syn-day-date">${d.date.slice(5)}</span>
        <img class="syn-day-icon" src="${d.icon}" alt="${d.condition}">
        <div class="syn-day-temps">
          <span class="syn-day-max">${d.max_temp_c}°C</span>
          <span class="syn-day-min">${d.min_temp_c}°C</span>
        </div>
        <span class="syn-day-cond">${d.condition}</span>
      </div>
    `).join("");
  }

  // 5. Weather Alerts Banner
  const alertBanner = document.getElementById("syn-alerts-banner");
  const alertTitle = document.getElementById("syn-alert-title");
  const alertDesc = document.getElementById("syn-alert-desc");
  if (alertBanner) {
    if (data.alerts && data.alerts.length > 0) {
      const a = data.alerts[0];
      if (alertTitle) alertTitle.textContent = `⚠️ ${a.headline || "Severe Weather Advisory"}`;
      if (alertDesc) alertDesc.textContent = a.desc || "Active weather alert in effect for this region.";
      alertBanner.classList.remove("hidden");
    } else {
      alertBanner.classList.add("hidden");
    }
  }
}

// ----------------------------------------------------------------------------
// Geolocation (📍 My Location)
// ----------------------------------------------------------------------------
function setupMyLocation() {
  const btn = document.getElementById("btn-my-location");
  if (!btn) return;

  btn.addEventListener("click", () => {
    if (!navigator.geolocation) {
      showAlert("Geolocation is not supported by your browser.", "error");
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span>Acquiring...</span>';
    showAlert("📍 Acquiring GPS coordinates via HTML5 Geolocation...", "info");

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const lat = pos.coords.latitude.toFixed(4);
          const lon = pos.coords.longitude.toFixed(4);
          showAlert(`📍 GPS coordinates locked: ${lat}, ${lon}. Ingesting local station...`, "info");

          await fetchSynopticWeather(`${lat},${lon}`);
          await fetchAllData();
          showAlert(`✓ Station synchronized to your location: ${currentSynopticCity}!`, "success");
        } catch (e) {
          showAlert(`Geolocation error: ${e.message}`, "error");
        } finally {
          btn.disabled = false;
          btn.innerHTML = '<span class="btn-icon">📍</span><span>My Location</span>';
        }
      },
      (err) => {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">📍</span><span>My Location</span>';
        showAlert("Location access denied or timed out.", "error");
      },
      { timeout: 8000, maximumAge: 60000 }
    );
  });
}

// ----------------------------------------------------------------------------
// Favorites & Search History
// ----------------------------------------------------------------------------
function getFavorites() {
  try {
    return JSON.parse(localStorage.getItem("skycast_favorites")) || ["Chennai", "Dubai", "Singapore", "London", "Tokyo"];
  } catch (e) {
    return ["Chennai", "Dubai", "Singapore"];
  }
}

function saveFavoritesList(list) {
  localStorage.setItem("skycast_favorites", JSON.stringify(list));
  renderFavorites();
  updateFavoriteButtonState();
}

function toggleCurrentFavorite() {
  const list = getFavorites();
  const idx = list.findIndex((c) => c.toLowerCase() === currentSynopticCity.toLowerCase());
  if (idx >= 0) {
    list.splice(idx, 1);
    saveFavoritesList(list);
    showAlert(`Removed ${currentSynopticCity} from favorites.`, "info");
  } else {
    list.push(currentSynopticCity);
    saveFavoritesList(list);
    showAlert(`⭐ Added ${currentSynopticCity} to favorites!`, "success");
  }
}

function updateFavoriteButtonState() {
  const btn = document.getElementById("btn-toggle-favorite");
  const starIcon = document.getElementById("fav-star-icon");
  const textEl = document.getElementById("fav-btn-text");
  if (!btn) return;

  const list = getFavorites();
  const isFav = list.some((c) => c.toLowerCase() === currentSynopticCity.toLowerCase());

  if (isFav) {
    if (starIcon) starIcon.textContent = "★";
    if (textEl) textEl.textContent = "Favorited Station";
    btn.classList.add("favorited");
    btn.style.background = "rgba(245, 158, 11, 0.25)";
    btn.style.borderColor = "#f59e0b";
    btn.style.color = "#fbbf24";
  } else {
    if (starIcon) starIcon.textContent = "⭐";
    if (textEl) textEl.textContent = "Add to Favorites";
    btn.classList.remove("favorited");
    btn.style.background = "rgba(255, 255, 255, 0.08)";
    btn.style.borderColor = "rgba(255, 255, 255, 0.18)";
    btn.style.color = "#ffffff";
  }
}

function renderFavorites() {
  const container = document.getElementById("favorites-list");
  if (!container) return;

  const favs = getFavorites();
  if (favs.length === 0) {
    container.innerHTML = '<span class="empty-hint" style="font-size: 0.75rem; color: #64748b;">No favorites pinned yet.</span>';
    return;
  }

  container.innerHTML = favs.map((city) => `
    <button class="fav-chip ${city.toLowerCase() === currentSynopticCity.toLowerCase() ? 'active' : ''}" data-city="${city}">
      <span>⭐</span> ${city}
    </button>
  `).join("");

  container.querySelectorAll(".fav-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const city = chip.getAttribute("data-city");
      fetchSynopticWeather(city);
    });
  });
}

function getSearchHistory() {
  try {
    return JSON.parse(localStorage.getItem("skycast_history")) || ["Chennai", "Bangalore", "Dubai"];
  } catch (e) {
    return [];
  }
}

function saveSearchHistory(city) {
  if (!city) return;
  let history = getSearchHistory().filter((c) => c.toLowerCase() !== city.toLowerCase());
  history.unshift(city);
  if (history.length > 7) history.pop();
  localStorage.setItem("skycast_history", JSON.stringify(history));
  renderSearchHistory();
}

function clearSearchHistory() {
  localStorage.removeItem("skycast_history");
  renderSearchHistory();
  showAlert("Search history cleared.", "info");
}

function renderSearchHistory() {
  const container = document.getElementById("history-list");
  if (!container) return;

  const history = getSearchHistory();
  if (history.length === 0) {
    container.innerHTML = '<span style="font-size: 0.72rem; color: #64748b;">No recent searches</span>';
    return;
  }

  container.innerHTML = history.map((city) => `
    <button class="history-chip" data-city="${city}">
      ${city}
    </button>
  `).join("");

  container.querySelectorAll(".history-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const city = chip.getAttribute("data-city");
      fetchSynopticWeather(city);
    });
  });
}

function setupFavoritesAndHistory() {
  renderFavorites();
  renderSearchHistory();

  const favBtn = document.getElementById("btn-toggle-favorite");
  if (favBtn) favBtn.addEventListener("click", toggleCurrentFavorite);

  const clearBtn = document.getElementById("btn-clear-history");
  if (clearBtn) clearBtn.addEventListener("click", clearSearchHistory);
}
