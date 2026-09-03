import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from sqlalchemy import text, func, and_
from sqlalchemy.orm import Session
from backend.models import Location, WeatherRecord

logger = logging.getLogger("weatherdata.weather_repository")


class WeatherRepository:
    """Data access layer for locations, weather records, and analytical queries."""

    @staticmethod
    def get_all_locations(db: Session) -> List[Location]:
        """Fetch all configured locations."""
        return db.query(Location).order_by(Location.city_name.asc()).all()

    @staticmethod
    def get_location_by_id(db: Session, location_id: int) -> Optional[Location]:
        """Fetch single location by primary key."""
        return db.query(Location).filter(Location.location_id == location_id).first()

    @staticmethod
    def get_location_by_city(db: Session, city_name: str) -> Optional[Location]:
        """Fetch location by city name (case-insensitive)."""
        return db.query(Location).filter(
            func.lower(Location.city_name) == city_name.strip().lower()
        ).first()

    @staticmethod
    def add_location(
        db: Session,
        city_name: str,
        country: Optional[str],
        latitude: float,
        longitude: float,
    ) -> Location:
        """Add a new geographic location."""
        loc = Location(
            city_name=city_name.strip(),
            country=country.strip() if country else None,
            latitude=latitude,
            longitude=longitude,
        )
        db.add(loc)
        db.commit()
        db.refresh(loc)
        return loc

    @staticmethod
    def insert_weather_records_incremental(
        db: Session, df: pd.DataFrame
    ) -> Tuple[int, int]:
        """
        Incremental load: insert records that do not already exist in the database.
        Uses composite key (location_id, recorded_at) to detect and skip duplicates.

        Returns:
            Tuple[int, int]: (inserted_count, duplicates_skipped)
        """
        if df.empty:
            return 0, 0

        # Extract unique (location_id, recorded_at) pairs from dataframe
        candidates = df[["location_id", "recorded_at"]].drop_duplicates()
        location_ids = candidates["location_id"].unique().tolist()

        # Query existing (location_id, recorded_at) for these locations
        existing_records = (
            db.query(WeatherRecord.location_id, WeatherRecord.recorded_at)
            .filter(WeatherRecord.location_id.in_(location_ids))
            .all()
        )
        existing_set = {
            (r[0], r[1].strftime("%Y-%m-%d %H:%M:%S") if isinstance(r[1], datetime) else str(r[1]))
            for r in existing_records
        }

        records_to_insert: List[WeatherRecord] = []
        duplicates_skipped = 0

        for _, row in df.iterrows():
            rec_dt = pd.to_datetime(row["recorded_at"])
            rec_str = rec_dt.strftime("%Y-%m-%d %H:%M:%S")
            key = (int(row["location_id"]), rec_str)

            if key in existing_set:
                duplicates_skipped += 1
                continue

            # Add to existing_set so batch duplicates aren't double-inserted
            existing_set.add(key)

            record = WeatherRecord(
                location_id=int(row["location_id"]),
                recorded_at=rec_dt.to_pydatetime(),
                temperature_c=float(row["temperature_c"]) if pd.notna(row.get("temperature_c")) else None,
                humidity_percent=int(row["humidity_percent"]) if pd.notna(row.get("humidity_percent")) else None,
                wind_speed_kmh=float(row["wind_speed_kmh"]) if pd.notna(row.get("wind_speed_kmh")) else None,
                weather_code=int(row["weather_code"]) if pd.notna(row.get("weather_code")) else None,
                weather_condition=str(row["weather_condition"]) if pd.notna(row.get("weather_condition")) else None,
                source=str(row.get("source", "weather_api")),
            )
            records_to_insert.append(record)

        if records_to_insert:
            try:
                db.bulk_save_objects(records_to_insert)
                db.commit()
                logger.info(
                    f"Incrementally loaded {len(records_to_insert)} new records. "
                    f"Skipped {duplicates_skipped} duplicates."
                )
            except Exception as e:
                db.rollback()
                logger.error(f"Transaction rollback during weather_records insert: {e}")
                raise e

        return len(records_to_insert), duplicates_skipped

    @staticmethod
    def get_latest_weather_all(db: Session) -> List[Dict[str, Any]]:
        """Get the most recent weather record for each configured location."""
        sql = text("""
            WITH RankedWeather AS (
                SELECT 
                    w.weather_id,
                    l.location_id,
                    l.city_name,
                    l.country,
                    l.latitude,
                    l.longitude,
                    w.recorded_at,
                    w.temperature_c,
                    w.humidity_percent,
                    w.wind_speed_kmh,
                    w.weather_code,
                    w.weather_condition,
                    w.source,
                    ROW_NUMBER() OVER (PARTITION BY l.location_id ORDER BY w.recorded_at DESC) AS rn
                FROM locations l
                LEFT JOIN weather_records w ON l.location_id = w.location_id
            )
            SELECT * FROM RankedWeather WHERE rn = 1 OR rn IS NULL
            ORDER BY city_name ASC;
        """)
        rows = db.execute(sql).mappings().all()
        return [dict(r) for r in rows]

    @staticmethod
    def get_weather_history(
        db: Session,
        city_name: Optional[str] = None,
        limit: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query historical weather observations with optional city and date filtering."""
        query = (
            db.query(
                WeatherRecord.weather_id,
                WeatherRecord.recorded_at,
                WeatherRecord.temperature_c,
                WeatherRecord.humidity_percent,
                WeatherRecord.wind_speed_kmh,
                WeatherRecord.weather_code,
                WeatherRecord.weather_condition,
                WeatherRecord.source,
                WeatherRecord.created_at,
                Location.location_id,
                Location.city_name,
                Location.country,
            )
            .join(Location, WeatherRecord.location_id == Location.location_id)
        )

        if city_name:
            clean_name = city_name.strip().split(",")[0].strip().lower()
            query = query.filter(
                (func.lower(Location.city_name) == clean_name)
                | (func.lower(Location.city_name).like(f"%{clean_name}%"))
            )
        if start_date:
            query = query.filter(WeatherRecord.recorded_at >= start_date)
        if end_date:
            query = query.filter(WeatherRecord.recorded_at <= end_date)

        results = query.order_by(WeatherRecord.recorded_at.desc()).limit(limit).all()
        return [
            {
                "weather_id": r.weather_id,
                "city_name": r.city_name,
                "country": r.country,
                "location_id": r.location_id,
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                "temperature_c": float(r.temperature_c) if r.temperature_c is not None else None,
                "humidity_percent": r.humidity_percent,
                "wind_speed_kmh": float(r.wind_speed_kmh) if r.wind_speed_kmh is not None else None,
                "weather_code": r.weather_code,
                "weather_condition": r.weather_condition,
                "source": r.source,
            }
            for r in results
        ]

    @staticmethod
    def get_analytics_summary(db: Session) -> Dict[str, Any]:
        """Fetch warehouse aggregate KPI metrics."""
        sql = text("""
            SELECT 
                COUNT(*) AS total_records,
                COUNT(DISTINCT location_id) AS total_locations,
                ROUND(AVG(CAST(temperature_c AS FLOAT)), 2) AS avg_temperature_c,
                MAX(temperature_c) AS max_temperature_c,
                MIN(temperature_c) AS min_temperature_c,
                ROUND(AVG(CAST(humidity_percent AS FLOAT)), 2) AS avg_humidity_percent,
                MAX(recorded_at) AS latest_record_time
            FROM weather_records;
        """)
        row = db.execute(sql).mappings().first()
        if not row or row["total_records"] == 0:
            return {
                "total_records": 0,
                "total_locations": 0,
                "avg_temperature_c": None,
                "max_temperature_c": None,
                "min_temperature_c": None,
                "avg_humidity_percent": None,
                "latest_record_time": None,
            }
        return {
            "total_records": row["total_records"],
            "total_locations": row["total_locations"],
            "avg_temperature_c": float(row["avg_temperature_c"]) if row["avg_temperature_c"] is not None else None,
            "max_temperature_c": float(row["max_temperature_c"]) if row["max_temperature_c"] is not None else None,
            "min_temperature_c": float(row["min_temperature_c"]) if row["min_temperature_c"] is not None else None,
            "avg_humidity_percent": float(row["avg_humidity_percent"]) if row["avg_humidity_percent"] is not None else None,
            "latest_record_time": row["latest_record_time"].isoformat() if row["latest_record_time"] else None,
        }

    @staticmethod
    def get_temperature_trend(db: Session, days: int = 7) -> List[Dict[str, Any]]:
        """Fetch daily average, max, and min temperatures for trend chart."""
        sql = text("""
            SELECT 
                CAST(w.recorded_at AS DATE) AS observation_date,
                l.city_name,
                ROUND(AVG(CAST(w.temperature_c AS FLOAT)), 2) AS avg_temperature,
                MAX(w.temperature_c) AS max_temperature,
                MIN(w.temperature_c) AS min_temperature,
                COUNT(*) AS sample_count
            FROM weather_records w
            INNER JOIN locations l ON w.location_id = l.location_id
            WHERE w.recorded_at >= DATEADD(DAY, -:days, SYSUTCDATETIME())
            GROUP BY CAST(w.recorded_at AS DATE), l.city_name
            ORDER BY observation_date ASC, l.city_name ASC;
        """)
        rows = db.execute(sql, {"days": days}).mappings().all()
        return [
            {
                "date": str(r["observation_date"]),
                "city_name": r["city_name"],
                "avg_temperature": float(r["avg_temperature"]) if r["avg_temperature"] is not None else None,
                "max_temperature": float(r["max_temperature"]) if r["max_temperature"] is not None else None,
                "min_temperature": float(r["min_temperature"]) if r["min_temperature"] is not None else None,
                "sample_count": r["sample_count"],
            }
            for r in rows
        ]

    @staticmethod
    def get_humidity_trend(db: Session, days: int = 7) -> List[Dict[str, Any]]:
        """Fetch daily average humidity for trend chart."""
        sql = text("""
            SELECT 
                CAST(w.recorded_at AS DATE) AS observation_date,
                l.city_name,
                ROUND(AVG(CAST(w.humidity_percent AS FLOAT)), 2) AS avg_humidity,
                MAX(w.humidity_percent) AS max_humidity,
                MIN(w.humidity_percent) AS min_humidity,
                COUNT(*) AS sample_count
            FROM weather_records w
            INNER JOIN locations l ON w.location_id = l.location_id
            WHERE w.recorded_at >= DATEADD(DAY, -:days, SYSUTCDATETIME())
            GROUP BY CAST(w.recorded_at AS DATE), l.city_name
            ORDER BY observation_date ASC, l.city_name ASC;
        """)
        rows = db.execute(sql, {"days": days}).mappings().all()
        return [
            {
                "date": str(r["observation_date"]),
                "city_name": r["city_name"],
                "avg_humidity": float(r["avg_humidity"]) if r["avg_humidity"] is not None else None,
                "max_humidity": r["max_humidity"],
                "min_humidity": r["min_humidity"],
                "sample_count": r["sample_count"],
            }
            for r in rows
        ]

    @staticmethod
    def get_conditions_distribution(db: Session) -> List[Dict[str, Any]]:
        """Fetch count and percentage of observations by weather condition for donut/pie charts."""
        sql = text("""
            SELECT 
                ISNULL(weather_condition, 'Clear') AS condition,
                COUNT(*) AS record_count,
                ROUND(AVG(CAST(temperature_c AS FLOAT)), 1) AS avg_temp,
                ROUND(AVG(CAST(humidity_percent AS FLOAT)), 1) AS avg_humidity
            FROM weather_records
            GROUP BY weather_condition
            ORDER BY record_count DESC;
        """)
        rows = db.execute(sql).mappings().all()
        return [
            {
                "condition": r["condition"],
                "record_count": r["record_count"],
                "avg_temp": float(r["avg_temp"]) if r["avg_temp"] is not None else None,
                "avg_humidity": float(r["avg_humidity"]) if r["avg_humidity"] is not None else None,
            }
            for r in rows
        ]

    @staticmethod
    def get_city_metrics_comparison(db: Session) -> List[Dict[str, Any]]:
        """Fetch multi-variable comparison metrics across cities for radar and polar area charts."""
        sql = text("""
            SELECT 
                l.city_name,
                l.country,
                ROUND(AVG(CAST(w.temperature_c AS FLOAT)), 2) AS avg_temp,
                ROUND(AVG(CAST(w.humidity_percent AS FLOAT)), 2) AS avg_humidity,
                ROUND(AVG(CAST(w.wind_speed_kmh AS FLOAT)), 2) AS avg_wind,
                MAX(w.temperature_c) AS max_temp,
                MIN(w.temperature_c) AS min_temp,
                COUNT(w.weather_id) AS total_records
            FROM locations l
            LEFT JOIN weather_records w ON l.location_id = w.location_id
            GROUP BY l.city_name, l.country
            ORDER BY avg_temp DESC;
        """)
        rows = db.execute(sql).mappings().all()
        return [
            {
                "city_name": r["city_name"],
                "country": r["country"],
                "avg_temp": float(r["avg_temp"]) if r["avg_temp"] is not None else 0.0,
                "avg_humidity": float(r["avg_humidity"]) if r["avg_humidity"] is not None else 0.0,
                "avg_wind": float(r["avg_wind"]) if r["avg_wind"] is not None else 0.0,
                "max_temp": float(r["max_temp"]) if r["max_temp"] is not None else 0.0,
                "min_temp": float(r["min_temp"]) if r["min_temp"] is not None else 0.0,
                "total_records": r["total_records"],
            }
            for r in rows
        ]

    @staticmethod
    def get_correlation_scatter(db: Session, limit: int = 200) -> List[Dict[str, Any]]:
        """Fetch observation pairs for temperature vs humidity scatter plot."""
        sql = text("""
            SELECT TOP (:limit)
                l.city_name,
                w.temperature_c,
                w.humidity_percent,
                w.wind_speed_kmh,
                ISNULL(w.weather_condition, 'Clear') AS weather_condition,
                w.recorded_at
            FROM weather_records w
            INNER JOIN locations l ON w.location_id = l.location_id
            WHERE w.temperature_c IS NOT NULL AND w.humidity_percent IS NOT NULL
            ORDER BY w.recorded_at DESC;
        """)
        rows = db.execute(sql, {"limit": limit}).mappings().all()
        return [
            {
                "city_name": r["city_name"],
                "temperature_c": float(r["temperature_c"]),
                "humidity_percent": float(r["humidity_percent"]),
                "wind_speed_kmh": float(r["wind_speed_kmh"]) if r["wind_speed_kmh"] is not None else 0.0,
                "weather_condition": r["weather_condition"],
                "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else "",
            }
            for r in rows
        ]
