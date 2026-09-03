import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.genai_service import WeatherGenAIAssistant

logger = logging.getLogger("weatherdata.genai_routes")
router = APIRouter(prefix="/api/genai", tags=["GenAI Weather Assistant"])

genai_assistant = WeatherGenAIAssistant()


class GenAIQuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        examples=["Which city has the highest temperature?"],
        description="Natural language question about warehouse weather records",
    )


class GenAIResponse(BaseModel):
    question: str
    sql: str
    success: bool
    row_count: int = 0
    rows: List[Dict[str, Any]] = []
    explanation: str
    error: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class GenAIConfigUpdate(BaseModel):
    provider: str = Field(..., examples=["gemini", "openai", "groq", "deepseek", "anthropic", "ollama", "rule_based"])
    api_key: Optional[str] = Field(default=None, description="Secret API key for the AI provider")
    model: Optional[str] = Field(default=None, description="Model identifier (e.g. gemini-1.5-flash, gpt-4o-mini)")
    base_url: Optional[str] = Field(default=None, description="Custom base URL for Ollama / LocalAI")


@router.get("/config")
def get_genai_config():
    """Get active AI provider and list of supported LLM platforms."""
    return genai_assistant.get_config()


@router.post("/config")
def update_genai_config(payload: GenAIConfigUpdate):
    """
    Dynamically update or test any AI API key (Gemini, OpenAI, Groq, DeepSeek, Claude, Ollama).
    Changes take effect immediately in memory.
    """
    updated = genai_assistant.update_config(
        provider=payload.provider,
        api_key=payload.api_key,
        model=payload.model,
        base_url=payload.base_url,
    )
    return {"success": True, "message": f"AI provider updated to {payload.provider}", "config": updated}


@router.post("/ask", response_model=GenAIResponse)
def ask_genai_weather_assistant(
    payload: GenAIQuestionRequest,
    db: Session = Depends(get_db),
):
    """
    GenAI Natural Language to Safe SQL Assistant.
    1. Parses natural language question
    2. Generates read-only SQL query (via LLM or Rule-Based fallback)
    3. Validates SQL safety (blocks DDL/DML)
    4. Executes query on SQL Server
    5. Formulates human-readable explanation
    """
    try:
        result = genai_assistant.ask(db=db, question=payload.question)
        return result
    except Exception as e:
        logger.error(f"GenAI processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GenAI processing failed: {str(e)}",
        )
