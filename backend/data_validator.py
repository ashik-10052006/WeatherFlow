import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple
import pandas as pd

logger = logging.getLogger("weatherdata.data_validator")


class WeatherDataValidator:
    """
    Validates meteorological observations against data quality rules.
    Detects anomalies, logs quality issues, and filters out invalid records.
    """

    TEMP_MIN = -60.0
    TEMP_MAX = 60.0
    HUMIDITY_MIN = 0
    HUMIDITY_MAX = 100
    WIND_SPEED_MIN = 0.0

    @classmethod
    def validate_weather_dataframe(
        cls, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Validate a transformed Pandas DataFrame of weather records.

        Returns:
            Tuple: (clean_df, list_of_quality_issues)
            Where each quality issue is:
                {"table_name": "weather_records", "issue_type": str, "issue_count": int}
        """
        if df.empty:
            logger.warning("Validator received an empty DataFrame.")
            return df, []

        quality_issues: List[Dict[str, Any]] = []
        valid_mask = pd.Series(True, index=df.index)

        # Rule 1: Check required fields (location_id and recorded_at must be non-null)
        null_required = df["location_id"].isna() | df["recorded_at"].isna()
        null_count = int(null_required.sum())
        if null_count > 0:
            logger.warning(f"Validation failed: {null_count} records missing required location_id or recorded_at.")
            quality_issues.append(
                {
                    "table_name": "weather_records",
                    "issue_type": "MISSING_REQUIRED_FIELDS",
                    "issue_count": null_count,
                }
            )
            valid_mask &= ~null_required

        # Rule 2: Temperature Range Validation (-60°C to +60°C)
        if "temperature_c" in df.columns:
            temp_out_of_bounds = (
                df["temperature_c"].notna()
                & ((df["temperature_c"] < cls.TEMP_MIN) | (df["temperature_c"] > cls.TEMP_MAX))
            )
            temp_issue_count = int(temp_out_of_bounds.sum())
            if temp_issue_count > 0:
                logger.warning(f"Validation: {temp_issue_count} records with out-of-range temperature ({cls.TEMP_MIN} to {cls.TEMP_MAX}°C).")
                quality_issues.append(
                    {
                        "table_name": "weather_records",
                        "issue_type": "OUT_OF_RANGE_TEMPERATURE",
                        "issue_count": temp_issue_count,
                    }
                )
                valid_mask &= ~temp_out_of_bounds

        # Rule 3: Humidity Range Validation (0% to 100%)
        if "humidity_percent" in df.columns:
            humidity_invalid = (
                df["humidity_percent"].notna()
                & ((df["humidity_percent"] < cls.HUMIDITY_MIN) | (df["humidity_percent"] > cls.HUMIDITY_MAX))
            )
            humidity_issue_count = int(humidity_invalid.sum())
            if humidity_issue_count > 0:
                logger.warning(f"Validation: {humidity_issue_count} records with invalid humidity (0-100%).")
                quality_issues.append(
                    {
                        "table_name": "weather_records",
                        "issue_type": "INVALID_HUMIDITY_RANGE",
                        "issue_count": humidity_issue_count,
                    }
                )
                valid_mask &= ~humidity_invalid

        # Rule 4: Wind Speed Validation (>= 0 km/h)
        if "wind_speed_kmh" in df.columns:
            wind_invalid = df["wind_speed_kmh"].notna() & (df["wind_speed_kmh"] < cls.WIND_SPEED_MIN)
            wind_issue_count = int(wind_invalid.sum())
            if wind_issue_count > 0:
                logger.warning(f"Validation: {wind_issue_count} records with negative wind speed.")
                quality_issues.append(
                    {
                        "table_name": "weather_records",
                        "issue_type": "NEGATIVE_WIND_SPEED",
                        "issue_count": wind_issue_count,
                    }
                )
                valid_mask &= ~wind_invalid

        # Rule 5: Future Timestamp Validation
        if "recorded_at" in df.columns:
            # Allow up to 24h into future for local timezone skew in ISO strings
            cutoff = datetime.now(timezone.utc) + timedelta(days=1)
            future_mask = df["recorded_at"].notna() & (
                pd.to_datetime(df["recorded_at"], utc=True) > cutoff
            )
            future_count = int(future_mask.sum())
            if future_count > 0:
                logger.warning(f"Validation: {future_count} records with unreasonable future timestamp.")
                quality_issues.append(
                    {
                        "table_name": "weather_records",
                        "issue_type": "FUTURE_TIMESTAMP",
                        "issue_count": future_count,
                    }
                )
                valid_mask &= ~future_mask

        # Rule 6: Duplicate Detection in batch
        dup_mask = df.duplicated(subset=["location_id", "recorded_at"], keep="first")
        dup_count = int(dup_mask.sum())
        if dup_count > 0:
            logger.info(f"Deduplication: {dup_count} duplicate records found within batch.")
            quality_issues.append(
                {
                    "table_name": "weather_records",
                    "issue_type": "BATCH_DUPLICATE_RECORDS",
                    "issue_count": dup_count,
                }
            )
            valid_mask &= ~dup_mask

        clean_df = df[valid_mask].copy()
        logger.info(
            f"Validation complete: {len(clean_df)} / {len(df)} records valid. "
            f"Quality issues recorded: {len(quality_issues)}"
        )
        return clean_df, quality_issues
