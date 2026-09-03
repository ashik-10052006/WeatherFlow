import logging
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("weatherdata.main")

app = FastAPI(
    title="WeatherData — Weather API Data Warehouse & Analytics Platform",
    description="Production-grade Weather Data Warehouse & ETL Analytics API.",
    version="1.0.0",
)

# Enable CORS for local development and frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
def health_check():
    """Application health check endpoint."""
    return {
        "status": "healthy",
        "service": "WeatherData Platform",
        "version": "1.0.0",
        "database": settings.db_database,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
