import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import pandas as pd
from backend.api_client import WeatherApiClient
from backend.data_validator import WeatherDataValidator
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
api_client = WeatherApiClient()


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


@router.get("/weather/search")
@router.post("/weather/search")
def search_and_ingest_city(
    city: str = Query(..., min_length=1, description="City name to search (e.g., Dubai, Singapore)"),
    refresh: bool = Query(False, description="Force fresh fetch from live API"),
    db: Session = Depends(get_db),
):
    """
    Dynamic City Weather Search & Ingestion:
    1. If city exists in warehouse, returns latest weather (or refreshes if requested).
    2. If city is not in warehouse, dynamically looks up coordinates, saves location,
       extracts live weather, validates, loads into SQL Server, and returns observations!
    """
    city_clean = city.strip()
    try:
        existing_loc = WeatherRepository.get_location_by_city(db, city_clean)

        # Case 1: Location already registered
        if existing_loc and not refresh:
            history = WeatherRepository.get_weather_history(db, city_name=existing_loc.city_name, limit=1)
            if history:
                return {
                    "success": True,
                    "is_new": False,
                    "location_id": existing_loc.location_id,
                    "city_name": existing_loc.city_name,
                    "country": existing_loc.country,
                    "latitude": float(existing_loc.latitude),
                    "longitude": float(existing_loc.longitude),
                    "weather": history[0],
                    "message": f"Retrieved latest observation for {existing_loc.city_name} from warehouse.",
                }

        # Case 2: Ingest from live API (or refresh)
        if existing_loc:
            # Refresh existing location
            res = api_client.fetch_weather(
                latitude=float(existing_loc.latitude),
                longitude=float(existing_loc.longitude),
                location_id=existing_loc.location_id,
                city_name=existing_loc.city_name,
                country=existing_loc.country or "",
            )
            loc_id = existing_loc.location_id
            city_name = existing_loc.city_name
            country = existing_loc.country
            is_new = False
        else:
            # Dynamic lookup for new city
            res = api_client.fetch_by_query(city_clean)
            if not res.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=res.get("error", f"City '{city_clean}' not found across weather providers."),
                )
            # Create location dimension in SQL Server
            new_loc = WeatherRepository.add_location(
                db,
                city_name=res["city_name"],
                country=res.get("country"),
                latitude=res["latitude"],
                longitude=res["longitude"],
            )
            loc_id = new_loc.location_id
            city_name = new_loc.city_name
            country = new_loc.country
            is_new = True

        # Clean, validate, and load record into weather_records
        rec_data = {
            "location_id": loc_id,
            "recorded_at": res.get("recorded_at"),
            "temperature_c": res.get("temperature_c"),
            "humidity_percent": res.get("humidity_percent"),
            "wind_speed_kmh": res.get("wind_speed_kmh"),
            "weather_code": res.get("weather_code"),
            "weather_condition": res.get("weather_condition"),
            "source": res.get("source", "weather_api"),
        }
        df = pd.DataFrame([rec_data])
        clean_df, issues = WeatherDataValidator.validate_weather_dataframe(df)

        if not clean_df.empty:
            WeatherRepository.insert_weather_records_incremental(db, clean_df)

        return {
            "success": True,
            "is_new": is_new,
            "location_id": loc_id,
            "city_name": city_name,
            "country": country,
            "latitude": float(res.get("latitude", 0.0)),
            "longitude": float(res.get("longitude", 0.0)),
            "weather": {
                "temperature_c": res.get("temperature_c"),
                "humidity_percent": res.get("humidity_percent"),
                "wind_speed_kmh": res.get("wind_speed_kmh"),
                "weather_condition": res.get("weather_condition"),
                "recorded_at": res.get("recorded_at"),
                "source": res.get("source"),
            },
            "message": f"Successfully {'ingested new' if is_new else 'updated'} weather observation for {city_name} into SQL Server.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching weather for {city_clean}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching weather for {city_clean}: {str(e)}",
        )

