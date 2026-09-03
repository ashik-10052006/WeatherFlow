import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import test_connection
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
    title="WeatherData — Weather API Data Warehouse & Analytics Platform",
    description="Production-grade Weather Data Warehouse & ETL Analytics API.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    - Returns interactive HTML Dashboard for browser visits (text/html).
    - Returns health check JSON for API requests (application/json or curl).
    """
    accept_header = request.headers.get("accept", "")
    index_file = frontend_dir / "index.html"

    # If browser requests HTML and index.html exists, serve the dashboard
    if "text/html" in accept_header and index_file.exists():
        return FileResponse(index_file)

    # Otherwise return Health Check JSON
    db_status = test_connection()
    return {
        "status": "healthy" if db_status.get("connected") else "degraded",
        "service": "WeatherData Platform",
        "version": "1.0.0",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health", tags=["Health & WebUI"])
def explicit_health_check():
    """Dedicated health check endpoint returning service and database status."""
    db_status = test_connection()
    return {
        "status": "healthy" if db_status.get("connected") else "degraded",
        "service": "WeatherData Platform",
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
        "platform": "WEATHERDATA Platform",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
