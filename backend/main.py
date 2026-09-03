import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import test_connection
from backend.json_to_ui import generate_json_to_ui_html
from backend.routes.weather_routes import router as weather_router
from backend.routes.analytics_routes import router as analytics_router
from backend.routes.pipeline_routes import router as pipeline_router
from backend.routes.genai_routes import router as genai_router

# Configure root logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("weatherdata.main")

app = FastAPI(
    title="WeatherFlow — Weather API Data Warehouse & Analytics Platform",
    description="Production-grade Weather Data Warehouse & ETL Analytics API.",
    version="1.0.0",
    docs_url=None,  # Custom enhanced Swagger UI served at /docs
    redoc_url=None,  # Custom enhanced ReDoc UI served at /redoc
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def json_to_ui_browser_middleware(request: Request, call_next):
    """
    Universal JSON-to-UI Browser Middleware:
    When a user directly navigates to an API endpoint in their web browser,
    automatically renders a clean interactive UI instead of raw JSON text.
    Maintains 100% pure JSON for automated tests, programmatic fetch, curl, and ?format=json.
    """
    accept = request.headers.get("accept", "")
    dest = request.headers.get("sec-fetch-dest", "")
    mode = request.headers.get("sec-fetch-mode", "")
    format_param = request.query_params.get("format", "").lower()
    view_param = request.query_params.get("view", "").lower()

    is_browser = (
        dest == "document"
        or mode == "navigate"
        or ("text/html" in accept and "application/json" not in accept)
        or view_param == "ui"
        or format_param == "ui"
    )

    response = await call_next(request)

    path = request.url.path
    if (
        is_browser
        and format_param != "json"
        and request.method == "GET"
        and (path.startswith("/api/") or path == "/health")
        and response.status_code == 200
        and "application/json" in response.headers.get("content-type", "")
    ):
        try:
            body = [chunk async for chunk in response.body_iterator]
            body_bytes = b"".join(body)
            json_str = body_bytes.decode("utf-8")
            html_content = generate_json_to_ui_html(
                path=str(request.url).replace(str(request.base_url).rstrip("/"), ""),
                json_str=json_str,
                status_code=response.status_code,
            )
            return HTMLResponse(content=html_content, status_code=response.status_code)
        except Exception as e:
            logger.error(f"Error converting JSON to UI for {path}: {e}")
            return Response(content=body_bytes, status_code=response.status_code, headers=dict(response.headers))

    return response


# Register API routers
app.include_router(weather_router)
app.include_router(analytics_router)
app.include_router(pipeline_router)
app.include_router(genai_router)

# Mount frontend directory for static assets (CSS, JS)
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/", tags=["Health & WebUI"])
def root_endpoint(request: Request):
    """
    Root endpoint:
    - Serves the production HTML Dashboard by default for all visits.
    - If explicitly requested via ?format=json or pure application/json accept, returns health check JSON.
    """
    format_param = request.query_params.get("format", "").lower()
    accept_header = request.headers.get("accept", "")
    index_file = frontend_dir / "index.html"

    # Only return JSON if explicitly requested via ?format=json
    if format_param == "json" or ("application/json" in accept_header and "text/html" not in accept_header and "*/*" not in accept_header):
        db_status = test_connection()
        return {
            "status": "healthy" if db_status.get("connected") else "degraded",
            "service": "WeatherFlow Platform",
            "version": "1.0.0",
            "database": db_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # By default, ALWAYS serve the interactive dashboard
    if index_file.exists():
        return FileResponse(index_file)

    return HTMLResponse("<h1>WeatherFlow Dashboard</h1><p>index.html not found</p>")


@app.get("/dashboard", tags=["Health & WebUI"], include_in_schema=False)
def dashboard_endpoint():
    """Explicit /dashboard route serving the interactive HTML dashboard."""
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>WeatherFlow Dashboard</h1><p>index.html not found</p>")


@app.get("/health", tags=["Health & WebUI"])
def explicit_health_check():
    """Dedicated health check endpoint returning service and database status."""
    db_status = test_connection()
    return {
        "status": "healthy" if db_status.get("connected") else "degraded",
        "service": "WeatherFlow Platform",
        "version": "1.0.0",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/links", tags=["Health & WebUI"])
@app.get("/portal", tags=["Health & WebUI"])
def all_links_directory(request: Request):
    """
    Centralized One-Link-to-All-Links Directory:
    - Returns visual Portal page in browser (text/html).
    - Returns complete catalog of all application links in JSON format.
    """
    accept_header = request.headers.get("accept", "")
    links_file = frontend_dir / "links.html"

    if "text/html" in accept_header and links_file.exists():
        return FileResponse(links_file)

    base = f"http://{settings.app_host}:{settings.app_port}"
    return {
        "platform": "WEATHERFLOW Platform",
        "one_link_portal": f"{base}/links",
        "portals_and_ui": {
            "web_dashboard": f"{base}/",
            "all_links_portal": f"{base}/links",
            "swagger_docs": f"{base}/docs",
            "redoc_docs": f"{base}/redoc",
            "health_check": f"{base}/health",
        },
        "weather_apis": {
            "latest_weather": f"{base}/api/weather/latest",
            "weather_history": f"{base}/api/weather/history",
            "weather_history_by_city": f"{base}/api/weather/history/Bangalore",
            "locations": f"{base}/api/locations",
        },
        "analytics_apis": {
            "summary_kpis": f"{base}/api/analytics/summary",
            "temperature_trend": f"{base}/api/analytics/temperature-trend",
            "humidity_trend": f"{base}/api/analytics/humidity-trend",
        },
        "pipeline_and_genai": {
            "pipeline_runs": f"{base}/api/pipeline/runs",
            "pipeline_run_details": f"{base}/api/pipeline/runs/1",
            "trigger_pipeline_post": f"{base}/api/pipeline/run",
            "genai_assistant_post": f"{base}/api/genai/ask",
        },
    }


@app.get("/json-to-ui", tags=["Health & WebUI"])
def json_to_ui_studio(request: Request):
    """
    Universal JSON-to-UI Studio:
    Interactive tool to paste any raw JSON and convert it into responsive tables, KPI cards, and CSV export.
    """
    studio_file = frontend_dir / "json_to_ui.html"
    if studio_file.exists():
        return FileResponse(studio_file)
    return HTMLResponse("<h1>JSON to UI Studio</h1><p>frontend/json_to_ui.html not found</p>")


@app.get("/docs", include_in_schema=False)
def custom_swagger_docs(request: Request):
    """
    Enhanced, High-End Custom Swagger UI:
    - Sleek dark theme matching WeatherData design language.
    - Top navigation bar linking to Dashboard, All Links, and JSON to UI Studio.
    - Live keyword search/filter bar enabled by default.
    - Auto-enabled 1-click 'Try it out' execution without multi-step clicking.
    - Request latency counter in milliseconds.
    - Reduced clutter with collapsed schemas.
    """
    base_res = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="WEATHERFLOW — Interactive API Console & Documentation",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_ui_parameters={
            "filter": True,
            "tryItOutEnabled": True,
            "defaultModelsExpandDepth": -1,
            "docExpansion": "list",
            "displayRequestDuration": True,
            "syntaxHighlight.theme": "monokai",
        },
    )
    html = base_res.body.decode("utf-8")

    # Inject modern Google fonts & custom dark theme stylesheet
    custom_head = """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/static/swagger.css">
    """
    html = html.replace("</head>", f"{custom_head}</head>")

    # Inject top navigation bar
    custom_nav = """
    <nav class="custom-docs-navbar">
      <a href="/" class="custom-docs-brand">
        <div class="custom-docs-brand-icon">⚡</div>
        <div class="custom-docs-brand-title">WEATHERFLOW API EXPLORER</div>
      </a>
      <div class="custom-docs-nav-links">
        <a href="/" class="custom-docs-nav-btn primary">🏠 Main Dashboard</a>
        <a href="/links" class="custom-docs-nav-btn">🌐 All Links Portal</a>
        <a href="/json-to-ui" class="custom-docs-nav-btn">✨ JSON to UI</a>
      </div>
    </nav>
    """
    html = html.replace("<body>", f'<body class="swagger-section">{custom_nav}')

    return HTMLResponse(content=html)


@app.get("/redoc", tags=["Health & WebUI"], include_in_schema=False)
def custom_redoc_ui():
    """
    Enhanced, High-End Custom ReDoc API Reference:
    - Sleek dark theme matching WeatherFlow design language.
    - Custom top navigation bar linking to Dashboard, Swagger, All Links, and JSON to UI.
    - Deep slate dark background, custom scrollbars, and styled search box.
    - Auto-expanded responses and alphabetical schema sorting.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>WEATHERFLOW &mdash; Technical API Reference &amp; Specifications</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/redoc.css">
  <link rel="icon" type="image/x-icon" href="https://fastapi.tiangolo.com/img/favicon.png">
</head>
<body class="redoc-body">
  <!-- Top Navigation Header -->
  <header class="redoc-custom-navbar">
    <div class="redoc-brand-group">
      <a href="/" class="redoc-brand">
        <span class="redoc-brand-icon">⚡</span>
        <span class="redoc-brand-title">WEATHERFLOW</span>
      </a>
      <span class="redoc-badge">SPECIFICATION</span>
      <span class="redoc-badge-env">PROD</span>
    </div>

    <nav class="redoc-nav-links">
      <a href="/" class="redoc-btn primary">🏠 Main Dashboard</a>
      <a href="/docs" class="redoc-btn accent">📖 Swagger Console</a>
      <a href="/links" class="redoc-btn">🌐 All Links Directory</a>
      <a href="/json-to-ui" class="redoc-btn">✨ JSON to UI</a>
      <a href="/openapi.json" class="redoc-btn outline" target="_blank">⬇ OpenAPI JSON</a>
    </nav>
  </header>

  <!-- ReDoc Target Mount Container -->
  <div id="redoc-container"></div>

  <!-- ReDoc Standalone Engine -->
  <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js"></script>
  <script>
    Redoc.init('/openapi.json', {
      theme: {
        colors: {
          primary: { main: '#38bdf8' },
          success: { main: '#10b981' },
          warning: { main: '#f59e0b' },
          error: { main: '#ef4444' },
          text: { primary: '#f8fafc', secondary: '#94a3b8' },
          http: {
            get: '#38bdf8',
            post: '#10b981',
            put: '#f59e0b',
            delete: '#ef4444'
          },
          responses: {
            success: { color: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.08)' },
            error: { color: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.08)' }
          }
        },
        typography: {
          fontSize: '14px',
          fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
          headings: {
            fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
            fontWeight: '700'
          },
          code: {
            fontFamily: "'JetBrains Mono', Consolas, monospace",
            backgroundColor: '#1e293b',
            color: '#38bdf8'
          }
        },
        sidebar: {
          backgroundColor: '#090d16',
          textColor: '#cbd5e1',
          activeTextColor: '#38bdf8',
          width: '290px'
        },
        rightPanel: {
          backgroundColor: '#0b0f19',
          textColor: '#e2e8f0',
          width: '42%'
        },
        codeBlock: {
          backgroundColor: '#020617'
        }
      },
      hideDownloadButton: false,
      expandResponses: '200,201',
      requiredPropsFirst: true,
      sortPropsAlphabetically: true,
      nativeScrollbars: true,
      pathInMiddlePanel: true
    }, document.getElementById('redoc-container'));
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
