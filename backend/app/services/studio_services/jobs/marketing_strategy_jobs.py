"""
Marketing Strategy Job Management - Tracks marketing strategy document generation jobs.

Educational Note: Marketing strategy jobs use an agentic loop pattern where Claude:
1. Plans the document structure (sections to write)
2. Writes sections incrementally to a markdown file
3. Signals completion via is_last_section flag

The markdown output can be rendered nicely on frontend and exported to PDF.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "marketing_strategy"


def create_marketing_strategy_job(
    project_id: str,
    job_id: str,
    source_id: str,
    source_name: str,
    direction: str
) -> Dict[str, Any]:
    job_data = {
        "id": job_id,
        "source_id": source_id,
        "source_name": source_name,
        "direction": direction,
        "status": "pending",
        "progress": "Initializing...",
        "error": None,
        "status_message": "Initializing...",
        "error_message": None,
        "document_title": None,
        "product_name": None,
        "target_market": None,
        "planned_sections": [],
        "planning_notes": None,
        "sections_written": 0,
        "total_sections": 0,
        "current_section": None,
        "markdown_file": None,
        "markdown_filename": None,
        "preview_url": None,
        "download_url": None,
        "iterations": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_marketing_strategy_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_marketing_strategy_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_marketing_strategy_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_marketing_strategy_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
