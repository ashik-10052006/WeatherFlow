import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.models import PipelineRun, DataQualityLog

logger = logging.getLogger("weatherdata.pipeline_repository")


class PipelineRepository:
    """Data access layer for pipeline telemetry and data quality audits."""

    @staticmethod
    def start_pipeline_run(db: Session, pipeline_name: str = "Weather_ETL_Pipeline") -> PipelineRun:
        """Create a new pipeline execution entry with 'RUNNING' status."""
        run = PipelineRun(
            pipeline_name=pipeline_name,
            started_at=datetime.now(timezone.utc),
            status="RUNNING",
            records_extracted=0,
            records_loaded=0,
            error_message=None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.info(f"Started pipeline run #{run.run_id} ({pipeline_name})")
        return run

    @staticmethod
    def complete_pipeline_run(
        db: Session,
        run_id: int,
        status: str,
        records_extracted: int = 0,
        records_loaded: int = 0,
        error_message: Optional[str] = None,
    ) -> Optional[PipelineRun]:
        """Mark a pipeline run as completed (SUCCESS, FAILED, or PARTIAL)."""
        run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if not run:
            logger.error(f"Pipeline run #{run_id} not found for completion.")
            return None

        run.completed_at = datetime.now(timezone.utc)
        run.status = status
        run.records_extracted = records_extracted
        run.records_loaded = records_loaded
        run.error_message = error_message
        db.commit()
        db.refresh(run)
        logger.info(
            f"Completed pipeline run #{run_id}: status={status}, "
            f"extracted={records_extracted}, loaded={records_loaded}"
        )
        return run

    @staticmethod
    def log_quality_issues(
        db: Session,
        run_id: Optional[int],
        quality_issues: List[Dict[str, Any]],
    ) -> None:
        """Persist data quality issues to data_quality_logs table."""
        if not quality_issues:
            return

        for issue in quality_issues:
            log_entry = DataQualityLog(
                run_id=run_id,
                table_name=issue.get("table_name", "weather_records"),
                issue_type=issue.get("issue_type", "UNKNOWN_ISSUE"),
                issue_count=int(issue.get("issue_count", 1)),
                created_at=datetime.now(timezone.utc),
            )
            db.add(log_entry)
        db.commit()
        logger.info(f"Recorded {len(quality_issues)} quality issues for run #{run_id}")

    @staticmethod
    def get_runs(db: Session, limit: int = 20) -> List[PipelineRun]:
        """Fetch recent pipeline execution logs ordered by most recent."""
        return (
            db.query(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_run_by_id(db: Session, run_id: int) -> Optional[PipelineRun]:
        """Retrieve details of a single pipeline run."""
        return db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()

    @staticmethod
    def get_quality_logs(db: Session, run_id: Optional[int] = None, limit: int = 50) -> List[DataQualityLog]:
        """Retrieve quality logs, optionally filtered by pipeline run_id."""
        query = db.query(DataQualityLog)
        if run_id is not None:
            query = query.filter(DataQualityLog.run_id == run_id)
        return query.order_by(DataQualityLog.created_at.desc()).limit(limit).all()
