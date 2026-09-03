"""
WEATHERDATA Platform — Universal JSON-to-UI HTML Generator
Converts any API JSON response into a modern, production-grade interactive Web UI.
Includes live table filtering, KPI metric cards, JSON syntax inspector, and CSV export.
"""

import json
import re
from typing import Any, Dict, List


def generate_json_to_ui_html(path: str, json_str: str, status_code: int = 200) -> str:
    """Generate a clean, standalone, responsive HTML page that visualizes JSON data."""
    try:
        data = json.loads(json_str)
    except Exception:
        data = {"raw": json_str}

    # Derive clean title from path
    title_map = {
        "/api/weather/latest": "⛅ Latest Weather Observations",
        "/api/weather/history": "📜 Warehouse Historical Weather Records",
        "/api/locations": "📍 Monitored Station Coordinates Dimension",
        "/api/analytics/summary": "📊 Warehouse Analytics KPI Summary",
        "/api/analytics/temperature-trend": "📈 7-Day Temperature Trend Aggregates",
        "/api/analytics/humidity-trend": "💧 7-Day Relative Humidity Trend Aggregates",
        "/api/pipeline/runs": "🚀 ETL Pipeline Execution Telemetry",
        "/health": "🩺 System Health & Database Liveness Check",
    }

    endpoint_title = title_map.get(path.split("?")[0], f"API Explorer — {path.split('?')[0]}")
    pretty_json = json.dumps(data, indent=2)

    # Determine if array of objects or single object
    is_array = isinstance(data, list)
    item_count = len(data) if is_array else (len(data.keys()) if isinstance(data, dict) else 1)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{endpoint_title} — WEATHERDATA API UI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-primary: #090d16;
      --bg-secondary: #0f172a;
      --bg-card: #131d33;
      --border-color: rgba(255, 255, 255, 0.08);
      --accent-blue: #38bdf8;
      --accent-cyan: #06b6d4;
      --accent-green: #10b981;
      --accent-purple: #8b5cf6;
      --accent-amber: #f59e0b;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --text-muted: #64748b;
      --font-main: 'Inter', -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: var(--font-main);
      background-color: var(--bg-primary);
      color: var(--text-primary);
      line-height: 1.5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    .navbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 2rem;
      background-color: rgba(15, 23, 42, 0.85);
      border-bottom: 1px solid var(--border-color);
      position: sticky;
      top: 0;
      z-index: 100;
      backdrop-filter: blur(12px);
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      text-decoration: none;
      color: inherit;
    }}
    .brand-icon {{
      font-size: 1.3rem;
      background: linear-gradient(135deg, #38bdf8, #6366f1);
      padding: 0.35rem 0.55rem;
      border-radius: 6px;
    }}
    .brand-title {{
      font-weight: 800;
      letter-spacing: 0.04em;
      color: #ffffff;
      font-size: 1.15rem;
    }}
    .nav-links {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}
    .nav-link {{
      color: var(--text-secondary);
      text-decoration: none;
      font-size: 0.85rem;
      font-weight: 500;
      padding: 0.4rem 0.8rem;
      border-radius: 6px;
      transition: all 0.2s;
    }}
    .nav-link:hover {{
      color: #ffffff;
      background-color: rgba(255, 255, 255, 0.05);
    }}
    .nav-link.primary {{
      background-color: var(--accent-blue);
      color: #0b0f19;
      font-weight: 600;
    }}
    .container {{
      max-width: 1400px;
      width: 100%;
      margin: 1.5rem auto;
      padding: 0 1.5rem;
      flex: 1;
    }}
    .hero-banner {{
      background: linear-gradient(135deg, #111a2e, #17243c);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 1.5rem 2rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 1rem;
      margin-bottom: 1rem;
    }}
    .hero-title {{
      font-size: 1.6rem;
      font-weight: 800;
      color: #ffffff;
      margin-bottom: 0.35rem;
    }}
    .endpoint-path-box {{
      display: inline-flex;
      align-items: center;
      gap: 0.6rem;
      font-family: var(--font-mono);
      font-size: 0.88rem;
      color: var(--accent-blue);
      background-color: rgba(56, 189, 248, 0.1);
      padding: 0.35rem 0.75rem;
      border-radius: 6px;
      border: 1px solid rgba(56, 189, 248, 0.25);
    }}
    .badge {{
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0.25rem 0.65rem;
      border-radius: 9999px;
      font-family: var(--font-mono);
    }}
    .badge-get {{ background-color: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #059669; }}
    .badge-status {{ background-color: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #059669; }}
    .action-buttons {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.82rem;
      font-weight: 600;
      padding: 0.45rem 0.9rem;
      border-radius: 6px;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s;
      border: 1px solid var(--border-color);
      background-color: var(--bg-secondary);
      color: var(--text-primary);
    }}
    .btn:hover {{
      background-color: rgba(255, 255, 255, 0.08);
      color: #ffffff;
      border-color: var(--accent-blue);
    }}
    .btn.primary {{
      background-color: var(--accent-blue);
      color: #0b0f19;
      border-color: var(--accent-blue);
    }}
    .tabs-bar {{
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.25rem;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 0.25rem;
    }}
    .tab-btn {{
      background: transparent;
      border: none;
      border-bottom: 2px solid transparent;
      color: var(--text-secondary);
      padding: 0.5rem 1rem;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .tab-btn.active {{
      color: #ffffff;
      border-bottom-color: var(--accent-blue);
    }}
    .tab-btn:hover:not(.active) {{ color: #ffffff; }}
    .tab-view {{ display: none; animation: fadeIn 0.2s ease; }}
    .tab-view.active {{ display: block; }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    
    /* Table Styling */
    .table-container {{
      background: #111a2e;
      border: 1px solid var(--border-color);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }}
    .table-toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1rem 1.25rem;
      background-color: rgba(15, 23, 42, 0.5);
      border-bottom: 1px solid var(--border-color);
      gap: 1rem;
      flex-wrap: wrap;
    }}
    .search-filter-input {{
      padding: 0.5rem 1rem;
      background-color: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      color: #ffffff;
      font-size: 0.85rem;
      width: 280px;
      outline: none;
    }}
    .search-filter-input:focus {{
      border-color: var(--accent-blue);
      box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
    }}
    .table-scroll {{
      overflow-x: auto;
      max-height: 70vh;
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.86rem;
    }}
    .data-table th {{
      padding: 0.75rem 1rem;
      background-color: #0f172a;
      color: var(--text-secondary);
      font-weight: 600;
      border-bottom: 1px solid var(--border-color);
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    .data-table td {{
      padding: 0.75rem 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-primary);
    }}
    .data-table tr:hover td {{
      background-color: rgba(255, 255, 255, 0.03);
    }}
    .temp-badge {{
      display: inline-block;
      font-weight: 700;
      color: var(--accent-amber);
    }}
    .hum-badge {{
      color: var(--accent-cyan);
      font-weight: 600;
    }}

    /* KPI Grid for single object */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.25rem;
      margin-bottom: 1.5rem;
    }}
    .kpi-card {{
      background: linear-gradient(135deg, #111a2e, #17243c);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 1.25rem;
    }}
    .kpi-label {{
      font-size: 0.78rem;
      text-transform: uppercase;
      color: var(--text-muted);
      font-weight: 600;
      letter-spacing: 0.05em;
    }}
    .kpi-value {{
      font-size: 1.8rem;
      font-weight: 800;
      color: #ffffff;
      margin-top: 0.25rem;
    }}

    /* JSON Code Box */
    .json-wrapper {{
      background-color: #080c16;
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 1.25rem;
      position: relative;
    }}
    .json-code {{
      font-family: var(--font-mono);
      font-size: 0.85rem;
      color: #38bdf8;
      overflow-x: auto;
      max-height: 70vh;
      white-space: pre;
    }}
    .footer {{
      margin-top: auto;
      padding: 1.5rem 2rem;
      text-align: center;
      border-top: 1px solid var(--border-color);
      color: var(--text-muted);
      font-size: 0.8rem;
    }}
  </style>
</head>
<body>
  <header class="navbar">
    <a href="/" class="brand">
      <div class="brand-icon">⚡</div>
      <div class="brand-title">WEATHERDATA</div>
    </a>
    <nav class="nav-links">
      <a href="/" class="nav-link">🏠 Main Dashboard</a>
      <a href="/links" class="nav-link">🌐 All Links</a>
      <a href="/docs" class="nav-link">📖 Swagger Docs</a>
      <a href="{path}{'&' if '?' in path else '?'}format=json" class="nav-link" target="_blank">↗ Raw JSON</a>
    </nav>
  </header>

  <main class="container">
    <div class="hero-banner">
      <div class="hero-top">
        <div>
          <h1 class="hero-title">{endpoint_title}</h1>
          <div class="endpoint-path-box">
            <span class="badge badge-get">GET</span>
            <span>{path}</span>
          </div>
        </div>
        <div class="action-buttons">
          <button id="btn-copy-json" class="btn">📋 Copy JSON</button>
          <button id="btn-export-csv" class="btn">📥 Export CSV</button>
          <a href="{path}" class="btn primary">🔄 Refresh</a>
        </div>
      </div>
      <div style="display: flex; gap: 0.75rem; align-items: center; font-size: 0.82rem; color: var(--text-secondary);">
        <span class="badge badge-status">HTTP {status_code} OK</span>
        <span>• Content-Type: application/json</span>
        <span>• <strong>{item_count}</strong> {('records' if is_array else 'properties')} loaded</span>
      </div>
    </div>

    <div class="tabs-bar">
      <button class="tab-btn active" data-tab="tab-ui">📊 Formatted UI View</button>
      <button class="tab-btn" data-tab="tab-json">{{ }} Raw JSON Inspector</button>
    </div>

    <!-- TAB 1: FORMATTED UI -->
    <div id="tab-ui" class="tab-view active">
      <div id="ui-content-rendered">
        <!-- Rendered via JavaScript -->
      </div>
    </div>

    <!-- TAB 2: RAW JSON -->
    <div id="tab-json" class="tab-view">
      <div class="json-wrapper">
        <pre class="json-code" id="raw-json-box">{pretty_json}</pre>
      </div>
    </div>
  </main>

  <footer class="footer">
    WEATHERDATA &bull; Automated JSON to UI Engine &bull; Microsoft SQL Server &bull; FastAPI
  </footer>

  <script>
    const rawData = {json_str};

    document.addEventListener("DOMContentLoaded", () => {{
      // Setup tabs
      document.querySelectorAll(".tab-btn").forEach(btn => {{
        btn.addEventListener("click", () => {{
          document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
          document.querySelectorAll(".tab-view").forEach(v => v.classList.remove("active"));
          btn.classList.add("active");
          document.getElementById(btn.getAttribute("data-tab")).classList.add("active");
        }});
      }});

      // Copy JSON
      document.getElementById("btn-copy-json").addEventListener("click", () => {{
        navigator.clipboard.writeText(JSON.stringify(rawData, null, 2)).then(() => {{
          const b = document.getElementById("btn-copy-json");
          b.textContent = "✓ Copied!";
          setTimeout(() => {{ b.textContent = "📋 Copy JSON"; }}, 2000);
        }});
      }});

      // Export CSV
      document.getElementById("btn-export-csv").addEventListener("click", () => {{
        exportToCSV(rawData);
      }});

      // Render UI
      renderDataToUI(rawData);
    }});

    function renderDataToUI(data) {{
      const container = document.getElementById("ui-content-rendered");

      // Case A: Array of records (e.g. weather records, history, locations, pipeline runs)
      if (Array.isArray(data)) {{
        if (data.length === 0) {{
          container.innerHTML = '<div style="padding: 3rem; text-align: center; color: var(--text-muted);">Zero records found.</div>';
          return;
        }}

        const cols = Object.keys(data[0]);
        let html = `
          <div class="table-container">
            <div class="table-toolbar">
              <div style="font-weight: 600; color: #fff;">Displaying ${{data.length}} Records</div>
              <input type="text" id="table-filter-input" class="search-filter-input" placeholder="🔎 Filter table rows in real time...">
            </div>
            <div class="table-scroll">
              <table class="data-table" id="interactive-data-table">
                <thead>
                  <tr>${{cols.map(c => `<th>${{c.replace(/_/g, " ").toUpperCase()}}</th>`).join("")}}</tr>
                </thead>
                <tbody>
                  ${{data.map(row => `
                    <tr>
                      ${{cols.map(col => {{
                        const val = row[col];
                        if (val === null || val === undefined) return '<td style="color: var(--text-muted);">--</td>';
                        if (col === "temperature_c" || col === "avg_temperature") return `<td><span class="temp-badge">${{val}}°C</span></td>`;
                        if (col === "humidity_percent" || col === "avg_humidity") return `<td><span class="hum-badge">${{val}}%</span></td>`;
                        if (col === "wind_speed_kmh") return `<td>${{val}} km/h</td>`;
                        if (col === "status") return `<td><span class="badge badge-status">${{val}}</span></td>`;
                        if (typeof val === "object") return `<td>${{JSON.stringify(val)}}</td>`;
                        return `<td>${{val}}</td>`;
                      }}).join("")}}
                    </tr>
                  `).join("")}}
                </tbody>
              </table>
            </div>
          </div>
        `;
        container.innerHTML = html;

        // Instant filter
        const input = document.getElementById("table-filter-input");
        if (input) {{
          input.addEventListener("input", (e) => {{
            const q = e.target.value.toLowerCase().trim();
            const rows = document.querySelectorAll("#interactive-data-table tbody tr");
            rows.forEach(r => {{
              r.style.display = (!q || r.textContent.toLowerCase().includes(q)) ? "" : "none";
            }});
          }});
        }}
        return;
      }}

      // Case B: Summary / Single Object
      if (typeof data === "object" && data !== null) {{
        const entries = Object.entries(data);
        const numEntries = entries.filter(([k, v]) => typeof v === "number" || typeof v === "string" && !isNaN(parseFloat(v)));

        let kpiHtml = "";
        if (numEntries.length > 0) {{
          kpiHtml = `
            <div class="kpi-grid">
              ${{numEntries.slice(0, 6).map(([k, v]) => `
                <div class="kpi-card">
                  <div class="kpi-label">${{k.replace(/_/g, " ")}}</div>
                  <div class="kpi-value">${{v}}</div>
                </div>
              `).join("")}}
            </div>
          `;
        }}

        let tableHtml = `
          <div class="table-container">
            <div class="table-toolbar">
              <div style="font-weight: 600; color: #fff;">Properties Overview</div>
            </div>
            <div class="table-scroll">
              <table class="data-table">
                <thead><tr><th>PROPERTY</th><th>VALUE</th></tr></thead>
                <tbody>
                  ${{entries.map(([k, v]) => `
                    <tr>
                      <td><strong>${{k.replace(/_/g, " ").toUpperCase()}}</strong></td>
                      <td>${{typeof v === "object" ? `<pre style="font-family: var(--font-mono); color: #38bdf8;">${{JSON.stringify(v, null, 2)}}</pre>` : v}}</td>
                    </tr>
                  `).join("")}}
                </tbody>
              </table>
            </div>
          </div>
        `;
        container.innerHTML = kpiHtml + tableHtml;
        return;
      }}

      container.innerHTML = `<div style="padding: 2rem;">${{String(data)}}</div>`;
    }}

    function exportToCSV(data) {{
      if (!Array.isArray(data) || data.length === 0) {{
        alert("Export to CSV is only available for tabular array datasets.");
        return;
      }}
      const cols = Object.keys(data[0]);
      const csvRows = [cols.join(",")];
      data.forEach(row => {{
        const values = cols.map(c => {{
          const v = row[c] !== null && row[c] !== undefined ? String(row[c]).replace(/"/g, '""') : "";
          return `"${{v}}"`;
        }});
        csvRows.push(values.join(","));
      }});
      const blob = new Blob([csvRows.join("\\n")], {{ type: "text/csv;charset=utf-8;" }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "weatherdata_export.csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }}
  </script>
</body>
</html>
"""
