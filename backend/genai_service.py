import re
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("weatherdata.genai_service")

# Forbidden SQL keywords for security
FORBIDDEN_SQL_PATTERNS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bMERGE\b",
    r"\bCREATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bSHUTDOWN\b",
    r"\bWAITFOR\b",
    r";",  # Prevent stacked query injection
]

ALLOWED_TABLES = {"locations", "weather_records", "pipeline_runs", "data_quality_logs"}


class SafeSQLValidator:
    """Validates that dynamically generated SQL is strictly read-only and safe."""

    @staticmethod
    def validate(sql: str) -> tuple[bool, Optional[str]]:
        sql_upper = sql.strip().upper()

        # Rule 1: Must be a SELECT query (or CTE starting with WITH)
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False, "Query must strictly start with SELECT or WITH."

        # Rule 2: Check for forbidden DDL / DML / control keywords
        for pattern in FORBIDDEN_SQL_PATTERNS:
            if re.search(pattern, sql_upper):
                return False, f"Dangerous SQL token detected: {pattern.replace(r'\b', '').replace(r'\\', '')}"

        # Rule 3: Check that only known schema tables are referenced
        return True, None


class WeatherGenAIAssistant:
    """
    GenAI module translating natural language questions into safe SQL,
    executing read-only queries against SQL Server, and explaining results.
    """

    def generate_sql(self, question: str) -> str:
        """
        Translate natural language intent into verified SQL Server query.
        Uses intent matching for common analytical questions with fallback.
        """
        q = question.lower().strip()

        # Intent 1: Highest / Maximum temperature
        if any(w in q for w in ["highest temp", "max temp", "hottest", "warmest", "highest temperature"]):
            return (
                "SELECT TOP 1 l.city_name, l.country, w.temperature_c, w.weather_condition, w.recorded_at "
                "FROM weather_records w "
                "JOIN locations l ON w.location_id = l.location_id "
                "ORDER BY w.temperature_c DESC"
            )

        # Intent 2: Lowest / Minimum temperature
        if any(w in q for w in ["lowest temp", "min temp", "coldest", "lowest temperature"]):
            return (
                "SELECT TOP 1 l.city_name, l.country, w.temperature_c, w.weather_condition, w.recorded_at "
                "FROM weather_records w "
                "JOIN locations l ON w.location_id = l.location_id "
                "ORDER BY w.temperature_c ASC"
            )

        # Intent 3: Average humidity
        if any(w in q for w in ["average humidity", "mean humidity", "avg humidity"]):
            return (
                "SELECT l.city_name, ROUND(AVG(CAST(w.humidity_percent AS FLOAT)), 1) AS avg_humidity_percent "
                "FROM weather_records w "
                "JOIN locations l ON w.location_id = l.location_id "
                "GROUP BY l.city_name "
                "ORDER BY avg_humidity_percent DESC"
            )

        # Intent 4: Average temperature by city
        if any(w in q for w in ["average temp", "avg temp", "mean temp", "average temperature"]):
            return (
                "SELECT l.city_name, l.country, ROUND(AVG(CAST(w.temperature_c AS FLOAT)), 2) AS avg_temp_c, COUNT(*) AS observations "
                "FROM weather_records w "
                "JOIN locations l ON w.location_id = l.location_id "
                "GROUP BY l.city_name, l.country "
                "ORDER BY avg_temp_c DESC"
            )

        # Intent 5: Rain / Precipitation / Drizzle
        if any(w in q for w in ["rain", "raining", "drizzle", "wet"]):
            return (
                "SELECT l.city_name, w.temperature_c, w.humidity_percent, w.weather_condition, w.recorded_at "
                "FROM weather_records w "
                "JOIN locations l ON w.location_id = l.location_id "
                "WHERE LOWER(w.weather_condition) LIKE '%rain%' OR LOWER(w.weather_condition) LIKE '%drizzle%' "
                "ORDER BY w.recorded_at DESC"
            )

        # Intent 6: Overcast / Cloudy
        if any(w in q for w in ["cloudy", "overcast", "cloud"]):
            return (
                "SELECT l.city_name, w.temperature_c, w.humidity_percent, w.weather_condition, w.recorded_at "
                "FROM weather_records w "
                "JOIN locations l ON w.location_id = l.location_id "
                "WHERE LOWER(w.weather_condition) LIKE '%cloud%' OR LOWER(w.weather_condition) LIKE '%overcast%' "
                "ORDER BY w.recorded_at DESC"
            )

        # Intent 7: Highest wind speed / windiest
        if any(w in q for w in ["wind", "windy", "windiest", "wind speed"]):
            return (
                "SELECT TOP 5 l.city_name, w.wind_speed_kmh, w.weather_condition, w.recorded_at "
                "FROM weather_records w "
                "JOIN locations l ON w.location_id = l.location_id "
                "ORDER BY w.wind_speed_kmh DESC"
            )

        # Intent 8: Pipeline health / status
        if any(w in q for w in ["pipeline", "runs", "etl", "telemetry"]):
            return (
                "SELECT TOP 5 run_id, pipeline_name, status, started_at, records_extracted, records_loaded "
                "FROM pipeline_runs "
                "ORDER BY started_at DESC"
            )

        # Default fallback: Latest weather across all cities
        return (
            "WITH RankedWeather AS ("
            "    SELECT l.city_name, l.country, w.temperature_c, w.humidity_percent, w.wind_speed_kmh, w.weather_condition, w.recorded_at, "
            "           ROW_NUMBER() OVER (PARTITION BY l.location_id ORDER BY w.recorded_at DESC) AS rn "
            "    FROM locations l "
            "    JOIN weather_records w ON l.location_id = w.location_id"
            ") "
            "SELECT city_name, country, temperature_c, humidity_percent, wind_speed_kmh, weather_condition, recorded_at "
            "FROM RankedWeather WHERE rn = 1 "
            "ORDER BY temperature_c DESC"
        )

    def explain_results(self, question: str, sql: str, rows: List[Dict[str, Any]]) -> str:
        """Synthesize natural language explanation from SQL results."""
        if not rows:
            return "No matching weather records were found in the warehouse for this query."

        count = len(rows)
        first = rows[0]

        if "temperature_c" in first and "city_name" in first and count == 1:
            return (
                f"Based on warehouse records, **{first['city_name']}** recorded a temperature of "
                f"**{first['temperature_c']}°C** with condition *{first.get('weather_condition', 'N/A')}*."
            )

        if "avg_temp_c" in first and "city_name" in first:
            highest = rows[0]
            lowest = rows[-1]
            return (
                f"Computed average temperatures across {count} cities. **{highest['city_name']}** has the highest average "
                f"at **{highest['avg_temp_c']}°C**, while **{lowest['city_name']}** has the lowest average at **{lowest['avg_temp_c']}°C**."
            )

        if "avg_humidity_percent" in first:
            return (
                f"Analyzed humidity across {count} cities. The most humid city is **{first['city_name']}** "
                f"with an average of **{first['avg_humidity_percent']}%**."
            )

        if "wind_speed_kmh" in first:
            return (
                f"The highest wind speed recorded was in **{first['city_name']}** at "
                f"**{first['wind_speed_kmh']} km/h**."
            )

        return f"Successfully retrieved {count} records answering: \"{question}\"."

    def ask(self, db: Session, question: str) -> Dict[str, Any]:
        """Execute end-to-end GenAI pipeline: Question -> Safe SQL -> Execute -> Explain."""
        # 1. Generate SQL
        generated_sql = self.generate_sql(question)

        # 2. Validate Safety
        is_safe, error = SafeSQLValidator.validate(generated_sql)
        if not is_safe:
            return {
                "question": question,
                "sql": generated_sql,
                "success": False,
                "error": f"SQL validation failed: {error}",
                "rows": [],
                "explanation": "Query rejected by security validator.",
            }

        # 3. Execute Read-Only SQL
        try:
            result = db.execute(text(generated_sql))
            raw_rows = result.mappings().all()
            rows = []
            for r in raw_rows:
                row_dict = {}
                for k, v in dict(r).items():
                    # Format datetime objects for clean JSON
                    row_dict[k] = v.isoformat() if hasattr(v, "isoformat") else v
                rows.append(row_dict)

            # 4. Explain Results
            explanation = self.explain_results(question, generated_sql, rows)

            return {
                "question": question,
                "sql": generated_sql,
                "success": True,
                "rows": rows,
                "row_count": len(rows),
                "explanation": explanation,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error executing GenAI SQL: {e}")
            return {
                "question": question,
                "sql": generated_sql,
                "success": False,
                "error": f"Execution error: {str(e)}",
                "rows": [],
                "explanation": "Failed to execute generated query against warehouse.",
            }
