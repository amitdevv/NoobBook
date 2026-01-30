"""
Business Report Job Management - Tracks business report generation jobs.

Educational Note: Business reports combine AI-generated content with data analysis.
This job tracker handles reports that may include:
- Written analysis and insights
- Charts/graphs from CSV data analysis (via csv_analyzer_agent)
- Context from multiple source types
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "business_report"


def create_business_report_job(
    project_id: str,
    job_id: str,
    source_id: str,
    source_name: str,
    direction: str,
    report_type: str,
    csv_source_ids: List[str],
    context_source_ids: List[str],
    focus_areas: List[str]
) -> Dict[str, Any]:
    job_data = {
        "id": job_id,
        "source_id": source_id,
        "source_name": source_name,
        "direction": direction,
        "status": "pending",
        "progress": "Initializing...",
        "error": None,
        "report_type": report_type,
        "csv_source_ids": csv_source_ids,
        "context_source_ids": context_source_ids,
        "focus_areas": focus_areas,
        "status_message": "Initializing...",
        "error_message": None,
        "title": None,
        "executive_summary": None,
        "sections": [],
        "analyses": [],
        "charts": [],
        "markdown_file": None,
        "markdown_url": None,
        "preview_url": None,
        "word_count": None,
        "iterations": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_business_report_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_business_report_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_business_report_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_business_report_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
