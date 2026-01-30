"""
Flow Diagram Job Management - Tracks flow diagram generation jobs.

Educational Note: Flow diagrams use Mermaid.js syntax which is rendered
directly by the frontend Mermaid library, unlike mind maps which use
a custom node structure with React Flow.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "flow_diagram"


def create_flow_diagram_job(
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
        "mermaid_syntax": None,
        "diagram_type": None,
        "title": None,
        "description": None,
        "generation_time_seconds": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_flow_diagram_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_flow_diagram_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_flow_diagram_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_flow_diagram_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
