import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.repositories.weather_repository import WeatherRepository
from backend.schemas import (
    LocationResponse,
    LocationCreate,
    LatestWeatherResponse,
    WeatherRecordResponse,
)

logger = logging.getLogger("weatherdata.weather_routes")
router = APIRouter(prefix="/api", tags=["Weather"])


@router.get("/locations", response_model=List[LocationResponse])
def list_locations(db: Session = Depends(get_db)):
    """Retrieve all monitored geographic locations."""
    try:
        return WeatherRepository.get_all_locations(db)
    except Exception as e:
        logger.error(f"Error fetching locations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve locations from data warehouse.",
        )


@router.post("/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
def create_location(location_in: LocationCreate, db: Session = Depends(get_db)):
    """Add a new geographic location to be monitored by the ETL pipeline."""
    try:
        existing = WeatherRepository.get_location_by_city(db, location_in.city_name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"City '{location_in.city_name}' is already monitored.",
            )
        new_loc = WeatherRepository.add_location(
            db,
            city_name=location_in.city_name,
            country=location_in.country,
            latitude=location_in.latitude,
            longitude=location_in.longitude,
        )
        return new_loc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating location: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save location to database.",
        )


@router.get("/weather/latest", response_model=List[LatestWeatherResponse])
def get_latest_weather(db: Session = Depends(get_db)):
    """Retrieve the most recent meteorological observation for every monitored location."""
    try:
        return WeatherRepository.get_latest_weather_all(db)
    except Exception as e:
        logger.error(f"Error fetching latest weather: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve latest weather observations.",
        )


@router.get("/weather/history", response_model=List[WeatherRecordResponse])
def get_weather_history(
    city: Optional[str] = Query(None, description="Filter by city name"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """Retrieve historical weather records with optional city and date filters."""
    try:
        return WeatherRepository.get_weather_history(
            db=db,
            city_name=city,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching weather history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve historical weather records.",
        )


@router.get("/weather/history/{city}", response_model=List[WeatherRecordResponse])
def get_weather_history_by_city(
    city: str,
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    db: Session = Depends(get_db),
):
    """Retrieve historical weather observations for a specific city."""
    try:
        records = WeatherRepository.get_weather_history(db=db, city_name=city, limit=limit)
        return records
    except Exception as e:
        logger.error(f"Error fetching weather history for {city}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve weather history for {city}.",
        )
