import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import pandas as pd
import requests
from backend.api_client import WeatherApiClient
from backend.config import settings
from backend.data_validator import WeatherDataValidator
from backend.database import get_db
from backend.models import Location
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


# Curated high-population Indian and Global cities for instant prefix suggestion
TOP_CITIES = [
    {"name": "Mumbai", "region": "Maharashtra", "country": "India"},
    {"name": "Delhi", "region": "Delhi", "country": "India"},
    {"name": "Bangalore", "region": "Karnataka", "country": "India"},
    {"name": "Chennai", "region": "Tamil Nadu", "country": "India"},
    {"name": "Kolkata", "region": "West Bengal", "country": "India"},
    {"name": "Hyderabad", "region": "Telangana", "country": "India"},
    {"name": "Ahmedabad", "region": "Gujarat", "country": "India"},
    {"name": "Pune", "region": "Maharashtra", "country": "India"},
    {"name": "Surat", "region": "Gujarat", "country": "India"},
    {"name": "Jaipur", "region": "Rajasthan", "country": "India"},
    {"name": "Lucknow", "region": "Uttar Pradesh", "country": "India"},
    {"name": "Kanpur", "region": "Uttar Pradesh", "country": "India"},
    {"name": "Nagpur", "region": "Maharashtra", "country": "India"},
    {"name": "Indore", "region": "Madhya Pradesh", "country": "India"},
    {"name": "Thane", "region": "Maharashtra", "country": "India"},
    {"name": "Bhopal", "region": "Madhya Pradesh", "country": "India"},
    {"name": "Visakhapatnam", "region": "Andhra Pradesh", "country": "India"},
    {"name": "Pudukkottai", "region": "Tamil Nadu", "country": "India"},
    {"name": "Coimbatore", "region": "Tamil Nadu", "country": "India"},
    {"name": "Madurai", "region": "Tamil Nadu", "country": "India"},
    {"name": "Tiruchirappalli", "region": "Tamil Nadu", "country": "India"},
    {"name": "Salem", "region": "Tamil Nadu", "country": "India"},
    {"name": "Patna", "region": "Bihar", "country": "India"},
    {"name": "Vadodara", "region": "Gujarat", "country": "India"},
    {"name": "Ghaziabad", "region": "Uttar Pradesh", "country": "India"},
    {"name": "Ludhiana", "region": "Punjab", "country": "India"},
    {"name": "Agra", "region": "Uttar Pradesh", "country": "India"},
    {"name": "Nashik", "region": "Maharashtra", "country": "India"},
    {"name": "Faridabad", "region": "Haryana", "country": "India"},
    {"name": "Meerut", "region": "Uttar Pradesh", "country": "India"},
    {"name": "Rajkot", "region": "Gujarat", "country": "India"},
    {"name": "Varanasi", "region": "Uttar Pradesh", "country": "India"},
    {"name": "Srinagar", "region": "Jammu and Kashmir", "country": "India"},
    {"name": "Amritsar", "region": "Punjab", "country": "India"},
    {"name": "Navi Mumbai", "region": "Maharashtra", "country": "India"},
    {"name": "Allahabad", "region": "Uttar Pradesh", "country": "India"},
    {"name": "Ranchi", "region": "Jharkhand", "country": "India"},
    {"name": "Chandigarh", "region": "Chandigarh", "country": "India"},
    {"name": "Mysore", "region": "Karnataka", "country": "India"},
    {"name": "Noida", "region": "Uttar Pradesh", "country": "India"},
    {"name": "Kochi", "region": "Kerala", "country": "India"},
    {"name": "Thiruvananthapuram", "region": "Kerala", "country": "India"},
    {"name": "Dubai", "region": "Dubai", "country": "United Arab Emirates"},
    {"name": "Abu Dhabi", "region": "Abu Dhabi", "country": "United Arab Emirates"},
    {"name": "Sharjah", "region": "Sharjah", "country": "United Arab Emirates"},
    {"name": "Doha", "region": "Ad Dawhah", "country": "Qatar"},
    {"name": "Riyadh", "region": "Ar Riyad", "country": "Saudi Arabia"},
    {"name": "Singapore", "region": "Singapore", "country": "Singapore"},
    {"name": "Kuala Lumpur", "region": "Kuala Lumpur", "country": "Malaysia"},
    {"name": "Bangkok", "region": "Bangkok", "country": "Thailand"},
    {"name": "London", "region": "City of London", "country": "United Kingdom"},
    {"name": "Manchester", "region": "Greater Manchester", "country": "United Kingdom"},
    {"name": "Paris", "region": "Ile-de-France", "country": "France"},
    {"name": "Berlin", "region": "Berlin", "country": "Germany"},
    {"name": "Munich", "region": "Bavaria", "country": "Germany"},
    {"name": "Frankfurt", "region": "Hesse", "country": "Germany"},
    {"name": "Amsterdam", "region": "North Holland", "country": "Netherlands"},
    {"name": "Zurich", "region": "Zurich", "country": "Switzerland"},
    {"name": "Rome", "region": "Lazio", "country": "Italy"},
    {"name": "Milan", "region": "Lombardy", "country": "Italy"},
    {"name": "Madrid", "region": "Madrid", "country": "Spain"},
    {"name": "Barcelona", "region": "Catalonia", "country": "Spain"},
    {"name": "Tokyo", "region": "Tokyo", "country": "Japan"},
    {"name": "Osaka", "region": "Osaka", "country": "Japan"},
    {"name": "Seoul", "region": "Seoul", "country": "South Korea"},
    {"name": "Sydney", "region": "New South Wales", "country": "Australia"},
    {"name": "Melbourne", "region": "Victoria", "country": "Australia"},
    {"name": "Brisbane", "region": "Queensland", "country": "Australia"},
    {"name": "Toronto", "region": "Ontario", "country": "Canada"},
    {"name": "Vancouver", "region": "British Columbia", "country": "Canada"},
    {"name": "Montreal", "region": "Quebec", "country": "Canada"},
    {"name": "New York", "region": "New York", "country": "United States"},
    {"name": "Los Angeles", "region": "California", "country": "United States"},
    {"name": "Chicago", "region": "Illinois", "country": "United States"},
    {"name": "San Francisco", "region": "California", "country": "United States"},
    {"name": "Miami", "region": "Florida", "country": "United States"},
    {"name": "Seattle", "region": "Washington", "country": "United States"},
    {"name": "Cairo", "region": "Al Qahirah", "country": "Egypt"},
    {"name": "Johannesburg", "region": "Gauteng", "country": "South Africa"},
    {"name": "Cape Town", "region": "Western Cape", "country": "South Africa"},
]


@router.get("/weather/suggest")
def get_city_suggestions(
    q: str = Query(..., min_length=1, description="Prefix or partial city search term (e.g. mum, chen, dub)"),
    db: Session = Depends(get_db),
):
    """
    Real-Time City Autocomplete Suggestions:
    Combines:
    1. Curated world & Indian metropolitan cities (e.g. 'mum' -> Mumbai).
    2. SQL Server registered warehouse locations.
    3. Live WeatherAPI search endpoint.
    """
    term = q.strip().lower()
    if not term:
        return []

    results = []
    seen = set()

    def add_match(name: str, region: Optional[str], country: Optional[str], source: str):
        key = f"{name.lower().strip()}_{country.lower().strip() if country else ''}"
        if key not in seen:
            seen.add(key)
            display_parts = [name]
            if region and region.lower() != name.lower():
                display_parts.append(region)
            if country:
                display_parts.append(country)
            results.append({
                "name": name,
                "region": region or "",
                "country": country or "",
                "display": ", ".join(display_parts),
                "source": source,
            })

    # 1. Check curated high-population list (prefix first, then contains)
    for c in TOP_CITIES:
        c_name = c["name"].lower()
        if c_name.startswith(term):
            add_match(c["name"], c.get("region"), c.get("country"), "curated")

    for c in TOP_CITIES:
        c_name = c["name"].lower()
        if term in c_name and not c_name.startswith(term):
            add_match(c["name"], c.get("region"), c.get("country"), "curated")

    # 2. Check local database registered locations
    try:
        db_locs = (
            db.query(Location)
            .filter(Location.city_name.ilike(f"%{term}%"))
            .limit(10)
            .all()
        )
        for loc in db_locs:
            add_match(loc.city_name, None, loc.country, "warehouse")
    except Exception as e:
        logger.warning(f"Error querying locations for suggest: {e}")

    # 3. Query WeatherAPI live search for worldwide coverage
    if settings.weather_api_key:
        try:
            url = f"http://api.weatherapi.com/v1/search.json?key={settings.weather_api_key}&q={term}"
            res = requests.get(url, timeout=2.5)
            if res.ok:
                for item in res.json():
                    add_match(
                        item.get("name"),
                        item.get("region"),
                        item.get("country"),
                        "weatherapi",
                    )
        except Exception as e:
            logger.debug(f"Live WeatherAPI suggest query skipped: {e}")

    return results[:8]

