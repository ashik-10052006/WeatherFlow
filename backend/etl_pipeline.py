import logging
import traceback
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Session

from backend.api_client import WeatherApiClient
from backend.data_validator import WeatherDataValidator
from backend.repositories.weather_repository import WeatherRepository
from backend.repositories.pipeline_repository import PipelineRepository

logger = logging.getLogger("weatherdata.etl_pipeline")


class WeatherETLPipeline:
    """
    End-to-end meteorological ETL pipeline orchestrator.
    Performs Extract -> Transform -> Validate -> Load -> Log.
    """

    def __init__(self, api_client: Optional[WeatherApiClient] = None):
        self.api_client = api_client or WeatherApiClient()

    def extract(self, db: Session, use_sample_data: bool = False) -> List[Dict[str, Any]]:
        """
        Extract weather data for all configured locations.
        Can toggle live REST API calls or offline sample dataset for testing.
        """
        locations = WeatherRepository.get_all_locations(db)
        if not locations:
            logger.warning("Extract: No locations found in warehouse.")
            return []

        logger.info(f"Extract: Ingesting weather data for {len(locations)} locations.")

        if use_sample_data:
            logger.info("Extract: Using sample offline weather dataset.")
            sample_data = self.api_client.load_sample_data()
            loc_map = {l.city_name.lower(): l.location_id for l in locations}
            for item in sample_data:
                city = item.get("city_name", "").lower()
                if city in loc_map:
                    item["location_id"] = loc_map[city]
            return sample_data

        # Live REST API Extraction
        extracted_data: List[Dict[str, Any]] = []
        for loc in locations:
            res = self.api_client.fetch_weather(
                latitude=float(loc.latitude),
                longitude=float(loc.longitude),
                location_id=loc.location_id,
                city_name=loc.city_name,
                country=loc.country or "",
            )
            extracted_data.append(res)

        return extracted_data

    def transform(self, raw_records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Transform raw JSON extraction into a clean, typed Pandas DataFrame.
        Handles data types, missing fields, timestamp parsing, and batch deduplication.
        """
        if not raw_records:
            return pd.DataFrame()

        # Filter to only records where HTTP request succeeded
        successful_records = [r for r in raw_records if r.get("success")]
        if not successful_records:
            logger.warning("Transform: Zero successful responses to process.")
            return pd.DataFrame()

        df = pd.DataFrame(successful_records)

        # Standardize and select target columns
        required_cols = [
            "location_id",
            "recorded_at",
            "temperature_c",
            "humidity_percent",
            "wind_speed_kmh",
            "weather_code",
            "weather_condition",
        ]
        for col in required_cols:
            if col not in df.columns:
                df[col] = None

        # Type Conversions
        df["location_id"] = pd.to_numeric(df["location_id"], errors="coerce")
        df["temperature_c"] = pd.to_numeric(df["temperature_c"], errors="coerce").round(2)
        df["humidity_percent"] = pd.to_numeric(df["humidity_percent"], errors="coerce").astype("Int64")
        df["wind_speed_kmh"] = pd.to_numeric(df["wind_speed_kmh"], errors="coerce").round(2)
        df["weather_code"] = pd.to_numeric(df["weather_code"], errors="coerce").astype("Int64")
        df["weather_condition"] = df["weather_condition"].fillna("Unknown").astype(str)
        df["source"] = "weather_api"

        # Timestamp normalization: ensure valid ISO format string
        df["recorded_at"] = pd.to_datetime(df["recorded_at"], errors="coerce")

        logger.info(f"Transform: Transformed {len(df)} records into clean Pandas DataFrame.")
        return df

    def validate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Run business validation checks against the DataFrame.
        Identifies out-of-range metrics and logs quality anomalies.
        """
        return WeatherDataValidator.validate_weather_dataframe(df)

    def load(self, db: Session, df: pd.DataFrame) -> tuple[int, int]:
        """
        Incrementally load validated records into SQL Server.
        Prevents duplicate entries and ensures transactional integrity.
        """
        return WeatherRepository.insert_weather_records_incremental(db, df)

    def run(self, db: Session, use_sample_data: bool = False) -> Dict[str, Any]:
        """
        Execute end-to-end ETL workflow:
        1. Telemetry start
        2. Extract (REST API)
        3. Transform (Pandas)
        4. Validate (Quality Rules)
        5. Load (SQL Server)
        6. Telemetry complete & Log
        """
        pipeline_name = "Weather_ETL_Mock" if use_sample_data else "Weather_ETL_Live"
        run_record = PipelineRepository.start_pipeline_run(db, pipeline_name=pipeline_name)
        run_id = run_record.run_id

        try:
            # 1. EXTRACT
            raw_data = self.extract(db, use_sample_data=use_sample_data)
            records_extracted = len(raw_data)
            failed_extractions = [r for r in raw_data if not r.get("success")]
            if failed_extractions:
                logger.warning(
                    f"{len(failed_extractions)} locations failed during extraction."
                )

            # 2. TRANSFORM
            df = self.transform(raw_data)
            if df.empty:
                err_msg = "Extraction produced zero valid records to transform."
                PipelineRepository.complete_pipeline_run(
                    db,
                    run_id=run_id,
                    status="FAILED",
                    records_extracted=records_extracted,
                    records_loaded=0,
                    error_message=err_msg,
                )
                return {
                    "run_id": run_id,
                    "status": "FAILED",
                    "records_extracted": records_extracted,
                    "records_loaded": 0,
                    "duplicates_skipped": 0,
                    "error": err_msg,
                }

            # 3. VALIDATE
            clean_df, quality_issues = self.validate(df)
            if quality_issues:
                PipelineRepository.log_quality_issues(db, run_id=run_id, quality_issues=quality_issues)

            # 4. LOAD
            records_loaded, duplicates_skipped = self.load(db, clean_df)

            # Determine run status
            status = "SUCCESS"
            if len(failed_extractions) > 0 or len(clean_df) < len(df):
                status = "PARTIAL"

            # 5. LOG / COMPLETE RUN
            PipelineRepository.complete_pipeline_run(
                db,
                run_id=run_id,
                status=status,
                records_extracted=records_extracted,
                records_loaded=records_loaded,
                error_message=None,
            )

            return {
                "run_id": run_id,
                "status": status,
                "records_extracted": records_extracted,
                "records_loaded": records_loaded,
                "duplicates_skipped": duplicates_skipped,
                "quality_issues_found": len(quality_issues),
                "error": None,
            }

        except Exception as e:
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"ETL Pipeline execution failed: {error_details}")
            PipelineRepository.complete_pipeline_run(
                db,
                run_id=run_id,
                status="FAILED",
                records_extracted=0,
                records_loaded=0,
                error_message=str(e),
            )
            return {
                "run_id": run_id,
                "status": "FAILED",
                "records_extracted": 0,
                "records_loaded": 0,
                "duplicates_skipped": 0,
                "error": str(e),
            }
