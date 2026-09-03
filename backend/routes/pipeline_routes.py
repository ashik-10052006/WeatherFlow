import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.etl_pipeline import WeatherETLPipeline
from backend.repositories.pipeline_repository import PipelineRepository
from backend.schemas import (
    PipelineRunRequest,
    PipelineExecutionResult,
    PipelineRunResponse,
    PipelineRunDetailResponse,
)

logger = logging.getLogger("weatherdata.pipeline_routes")
router = APIRouter(prefix="/api/pipeline", tags=["Pipeline Monitor"])

# Singleton instance of the ETL pipeline orchestrator
pipeline_service = WeatherETLPipeline()


@router.post("/run", response_model=PipelineExecutionResult)
def trigger_pipeline_run(
    payload: PipelineRunRequest = PipelineRunRequest(use_sample_data=False),
    db: Session = Depends(get_db),
):
    """
    Manually trigger the Weather ETL pipeline.
    Optionally pass `use_sample_data: true` to run with offline sample data.
    """
    try:
        result = pipeline_service.run(db=db, use_sample_data=payload.use_sample_data)
        
        # Invalidate GenAI query cache so responses immediately reflect freshly loaded records
        try:
            from backend.routes.genai_routes import genai_assistant
            genai_assistant.clear_cache()
        except Exception:
            pass

        success = result.get("status") in ("SUCCESS", "PARTIAL")
        message = (
            f"ETL completed with status '{result.get('status')}'. "
            f"Extracted {result.get('records_extracted')}, "
            f"Loaded {result.get('records_loaded')}, "
            f"Skipped {result.get('duplicates_skipped')} duplicates."
        )
        return {
            "success": success,
            "run_id": result.get("run_id"),
            "status": result.get("status"),
            "records_extracted": result.get("records_extracted", 0),
            "records_loaded": result.get("records_loaded", 0),
            "duplicates_skipped": result.get("duplicates_skipped", 0),
            "quality_issues_found": result.get("quality_issues_found", 0),
            "message": message,
        }
    except Exception as e:
        logger.error(f"Error executing manual pipeline run: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {str(e)}",
        )


@router.get("/runs", response_model=List[PipelineRunResponse])
def get_pipeline_runs(
    limit: int = Query(20, ge=1, le=100, description="Max runs to return"),
    db: Session = Depends(get_db),
):
    """Retrieve historical pipeline runs ordered by execution timestamp."""
    try:
        return PipelineRepository.get_runs(db, limit=limit)
    except Exception as e:
        logger.error(f"Error fetching pipeline runs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pipeline run history.",
        )


@router.get("/runs/{run_id}", response_model=PipelineRunDetailResponse)
def get_pipeline_run_details(run_id: int, db: Session = Depends(get_db)):
    """Retrieve comprehensive details of a single pipeline run including quality logs."""
    try:
        run = PipelineRepository.get_run_by_id(db, run_id=run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline run #{run_id} not found.",
            )

        quality_logs = PipelineRepository.get_quality_logs(db, run_id=run_id)
        return {
            "run_id": run.run_id,
            "pipeline_name": run.pipeline_name,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "status": run.status,
            "records_extracted": run.records_extracted,
            "records_loaded": run.records_loaded,
            "error_message": run.error_message,
            "quality_logs": quality_logs,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching run #{run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch details for pipeline run #{run_id}.",
        )
