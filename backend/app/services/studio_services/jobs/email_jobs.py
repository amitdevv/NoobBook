"""
Email Template Job Management - Tracks email template generation jobs.

Educational Note: Email jobs use an AI agent with iterative refinement to
generate responsive HTML email templates with AI-generated images.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "email"


def create_email_job(
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
        "template_name": None,
        "template_type": None,
        "color_scheme": None,
        "sections": [],
        "layout_notes": None,
        "images": [],
        "html_file": None,
        "html_url": None,
        "preview_url": None,
        "subject_line": None,
        "preheader_text": None,
        "iterations": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_email_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_email_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_email_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_email_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
