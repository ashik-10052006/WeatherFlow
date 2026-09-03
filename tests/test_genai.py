import pytest
from backend.genai_service import SafeSQLValidator, WeatherGenAIAssistant
from backend.database import SessionLocal


def test_safe_sql_validator_accepts_select():
    """Verify read-only SELECT queries are allowed."""
    valid, err = SafeSQLValidator.validate("SELECT * FROM weather_records")
    assert valid is True
    assert err is None

    valid_cte, err2 = SafeSQLValidator.validate("WITH Cte AS (SELECT 1 AS x) SELECT * FROM Cte")
    assert valid_cte is True


def test_safe_sql_validator_blocks_ddl_and_dml():
    """Verify destructive SQL statements are strictly rejected."""
    dangerous = [
        "DROP TABLE weather_records",
        "DELETE FROM locations WHERE location_id = 1",
        "UPDATE weather_records SET temperature_c = 100",
        "INSERT INTO locations VALUES ('HackCity', 'Nowhere', 0, 0)",
        "ALTER TABLE locations DROP COLUMN country",
        "SELECT 1; DROP TABLE locations",  # Stacked injection
        "TRUNCATE TABLE weather_records",
        "EXEC sp_msforeachtable 'DROP TABLE ?'",
    ]
    for stmt in dangerous:
        valid, err = SafeSQLValidator.validate(stmt)
        assert valid is False, f"Failed to reject: {stmt}"


def test_genai_sql_generation():
    """Verify natural language intents generate proper SQL queries."""
    assistant = WeatherGenAIAssistant()
    assistant.provider = "rule_based"

    sql1 = assistant.generate_sql("Which city has the highest temperature?")
    assert "ORDER BY w.temperature_c DESC" in sql1

    sql2 = assistant.generate_sql("What is the average humidity?")
    assert "AVG(CAST(w.humidity_percent AS FLOAT))" in sql2

    sql3 = assistant.generate_sql("Which cities have rainy weather?")
    assert "LIKE '%rain%'" in sql3


def test_genai_ask_end_to_end():
    """Verify end-to-end question processing against SQL Server database."""
    db = SessionLocal()
    try:
        assistant = WeatherGenAIAssistant()
        res = assistant.ask(db, "Which city has the highest temperature?")
        assert res["success"] is True
        assert res["sql"].startswith("SELECT")
        assert len(res["rows"]) >= 1
        assert "Delhi" in res["rows"][0]["city_name"] or len(res["rows"]) > 0
        assert "explanation" in res
    finally:
        db.close()
