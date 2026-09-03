import re
import json
import logging
from typing import Any, Dict, List, Optional
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings

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

SCHEMA_DEFINITION = """
Database Schema: Microsoft SQL Server (Transact-SQL)
Tables:
1. locations (
    location_id INT PRIMARY KEY,
    city_name NVARCHAR(100) NOT NULL,
    country NVARCHAR(100),
    latitude FLOAT,
    longitude FLOAT
)
2. weather_records (
    weather_id INT PRIMARY KEY IDENTITY,
    location_id INT FOREIGN KEY REFERENCES locations(location_id),
    recorded_at DATETIME NOT NULL,
    temperature_c FLOAT,
    humidity_percent INT,
    wind_speed_kmh FLOAT,
    weather_code INT,
    weather_condition NVARCHAR(100),
    source NVARCHAR(50)
)
3. pipeline_runs (
    run_id INT PRIMARY KEY IDENTITY,
    pipeline_name NVARCHAR(100),
    status NVARCHAR(20), -- 'SUCCESS', 'FAILED'
    started_at DATETIME,
    completed_at DATETIME,
    records_extracted INT,
    records_loaded INT
)
"""


class SafeSQLValidator:
    """Validates that dynamically generated SQL is strictly read-only and safe."""

    @staticmethod
    def validate(sql: str) -> tuple[bool, Optional[str]]:
        sql_clean = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        sql_clean = re.sub(r"--.*", "", sql_clean)
        sql_upper = sql_clean.strip().upper()

        # Rule 1: Must be a SELECT query (or CTE starting with WITH)
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False, "Query must strictly start with SELECT or WITH."

        # Rule 2: Check for forbidden DDL / DML / control keywords
        for pattern in FORBIDDEN_SQL_PATTERNS:
            if re.search(pattern, sql_upper):
                return False, f"Dangerous SQL token detected: {pattern.replace(r'\\b', '').replace(r'\\\\', '')}"

        return True, None


class WeatherGenAIAssistant:
    """
    GenAI module translating natural language questions into safe SQL,
    executing read-only queries against SQL Server, and explaining results.
    Supports any AI API key (Gemini, OpenAI, Groq, DeepSeek, Claude, Ollama, Rule-Based).
    """

    def __init__(self):
        # Determine provider and key from config or specific env vars
        self.provider = settings.ai_provider.lower() if settings.ai_provider else "rule_based"
        self.api_key = settings.ai_api_key
        self.model = settings.ai_model
        self.base_url = settings.ai_base_url

        # Auto-detect specific provider keys if general key not specified
        if not self.api_key:
            if settings.gemini_api_key:
                self.provider = "gemini"
                self.api_key = settings.gemini_api_key
            elif settings.openai_api_key:
                self.provider = "openai"
                self.api_key = settings.openai_api_key
            elif settings.groq_api_key:
                self.provider = "groq"
                self.api_key = settings.groq_api_key
            elif settings.deepseek_api_key:
                self.provider = "deepseek"
                self.api_key = settings.deepseek_api_key
            elif settings.anthropic_api_key:
                self.provider = "anthropic"
                self.api_key = settings.anthropic_api_key

        self._set_default_model()

    def _set_default_model(self):
        if not self.model:
            defaults = {
                "gemini": "gemini-1.5-flash",
                "openai": "gpt-4o-mini",
                "groq": "llama-3.3-70b-versatile",
                "deepseek": "deepseek-chat",
                "anthropic": "claude-3-5-haiku-20241022",
                "ollama": "llama3",
            }
            self.model = defaults.get(self.provider, "default-model")

    def update_config(
        self,
        provider: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dynamically update AI configuration at runtime."""
        self.provider = provider.lower().strip()
        if api_key is not None:
            self.api_key = api_key.strip() or None
        if model is not None:
            self.model = model.strip() or None
        if base_url is not None:
            self.base_url = base_url.strip() or None

        self._set_default_model()
        logger.info(f"Updated AI Provider: {self.provider} (Model: {self.model}, Has Key: {bool(self.api_key)})")
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return active AI provider and sanitized configuration."""
        masked_key = None
        if self.api_key:
            if len(self.api_key) > 8:
                masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}"
            else:
                masked_key = "***configured***"

        return {
            "provider": self.provider,
            "model": self.model,
            "has_api_key": bool(self.api_key),
            "masked_key": masked_key,
            "base_url": self.base_url,
            "supported_providers": [
                {"id": "gemini", "name": "Google Gemini", "default_model": "gemini-1.5-flash"},
                {"id": "openai", "name": "OpenAI (ChatGPT)", "default_model": "gpt-4o-mini"},
                {"id": "groq", "name": "Groq (Ultra-Fast Llama)", "default_model": "llama-3.3-70b-versatile"},
                {"id": "deepseek", "name": "DeepSeek", "default_model": "deepseek-chat"},
                {"id": "anthropic", "name": "Anthropic Claude", "default_model": "claude-3-5-haiku-20241022"},
                {"id": "ollama", "name": "Local Ollama / LMStudio", "default_model": "llama3"},
                {"id": "rule_based", "name": "Built-in Rule-Based (No Key Needed)", "default_model": "safe-intent-v1"},
            ],
        }

    def _call_llm(self, user_prompt: str, system_prompt: str) -> Optional[str]:
        """Send prompt to the configured AI API provider."""
        if not self.api_key and self.provider != "ollama":
            return None

        try:
            if self.provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\nUser Request: {user_prompt}"}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 600},
                }
                res = requests.post(url, json=payload, timeout=12)
                if res.ok:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                logger.warning(f"Gemini API error ({res.status_code}): {res.text}")

            elif self.provider in ("openai", "groq", "deepseek", "ollama", "custom"):
                urls = {
                    "openai": "https://api.openai.com/v1/chat/completions",
                    "groq": "https://api.groq.com/openai/v1/chat/completions",
                    "deepseek": "https://api.deepseek.com/chat/completions",
                    "ollama": (self.base_url or "http://localhost:11434/v1") + "/chat/completions",
                    "custom": (self.base_url or "https://api.openai.com/v1") + "/chat/completions",
                }
                url = urls.get(self.provider, urls["openai"])
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                }
                res = requests.post(url, json=payload, headers=headers, timeout=12)
                if res.ok:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                logger.warning(f"{self.provider} API error ({res.status_code}): {res.text}")

            elif self.provider == "anthropic":
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "max_tokens": 600,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                }
                res = requests.post(url, json=payload, headers=headers, timeout=12)
                if res.ok:
                    data = res.json()
                    return data["content"][0]["text"]
                logger.warning(f"Anthropic API error ({res.status_code}): {res.text}")

        except Exception as e:
            logger.warning(f"LLM API invocation failed for {self.provider}: {e}")

        return None

    def generate_sql(self, question: str) -> str:
        """
        Translate natural language intent into verified SQL Server query.
        Uses LLM if API key is configured, with seamless rule-based fallback.
        """
        if self.provider != "rule_based" and (self.api_key or self.provider == "ollama"):
            system_prompt = (
                f"{SCHEMA_DEFINITION}\n"
                "You are an expert T-SQL Data Warehouse Architect. Convert the user's natural language question into a "
                "safe, valid Microsoft SQL Server SELECT query. Follow these strict rules:\n"
                "1. Output ONLY the raw SQL query. Do not wrap in explanation or markdown.\n"
                "2. The query MUST strictly be a read-only SELECT or WITH statement.\n"
                "3. Use SQL Server syntax (TOP N, DATEADD, GETUTCDATE(), ROUND).\n"
                "4. Never write DDL or DML statements (no DROP, INSERT, UPDATE, DELETE, etc.).\n"
                "5. Do NOT terminate with a semicolon."
            )
            llm_result = self._call_llm(question, system_prompt)
            if llm_result:
                # Clean any markdown tags if model included them
                cleaned = re.sub(r"```sql\s*", "", llm_result, flags=re.IGNORECASE)
                cleaned = re.sub(r"```\s*", "", cleaned)
                cleaned = cleaned.strip().rstrip(";")
                is_safe, err = SafeSQLValidator.validate(cleaned)
                if is_safe:
                    logger.info(f"AI ({self.provider}) generated valid SQL: {cleaned}")
                    return cleaned
                else:
                    logger.warning(f"AI generated query failed safety validator: {err}. Using rule-based fallback.")

        # Built-in Rule-Based Intent Engine (High precision fallback)
        return self._generate_rule_based_sql(question)

    def _generate_rule_based_sql(self, question: str) -> str:
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

        # Intent 9: Specific city search (e.g. "Dubai", "Chennai", "Tokyo")
        for city in ["bangalore", "mumbai", "delhi", "london", "new york", "tokyo", "paris", "sydney", "dubai", "singapore", "cairo", "chennai", "pudukkottai"]:
            if city in q:
                return (
                    f"SELECT TOP 5 l.city_name, l.country, w.temperature_c, w.humidity_percent, w.wind_speed_kmh, w.weather_condition, w.recorded_at "
                    f"FROM weather_records w "
                    f"JOIN locations l ON w.location_id = l.location_id "
                    f"WHERE LOWER(l.city_name) LIKE '%{city}%' "
                    f"ORDER BY w.recorded_at DESC"
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

        # If LLM is active, use it to synthesize rich contextual insights
        if self.provider != "rule_based" and (self.api_key or self.provider == "ollama"):
            system_prompt = (
                "You are an executive weather analytics AI assistant. "
                "Synthesize a concise, engaging, professional insight (2-3 sentences max) answering the user's question "
                "based ONLY on the query results provided. Use bold markdown for key metrics and city names."
            )
            user_prompt = (
                f"Question: {question}\n"
                f"SQL Query: {sql}\n"
                f"Query Results: {json.dumps(rows[:10], default=str)}"
            )
            llm_explanation = self._call_llm(user_prompt, system_prompt)
            if llm_explanation:
                return llm_explanation.strip()

        # Rule-based fallback explanation
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
                "provider": self.provider,
                "model": self.model,
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
