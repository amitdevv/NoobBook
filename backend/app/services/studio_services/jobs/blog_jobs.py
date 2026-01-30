"""
Blog Post Job Management - Tracks blog post generation jobs.

Educational Note: Blog jobs use an AI agent with image generation capabilities
to create comprehensive, SEO-optimized blog posts in Markdown format.
The agent can generate images to embed within the blog content.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.studio_services.studio_index_service import (
    create_job, update_job, get_job, list_jobs, delete_job
)

JOB_TYPE = "blog"


def create_blog_job(
    project_id: str,
    job_id: str,
    source_id: str,
    source_name: str,
    direction: str,
    target_keyword: str,
    blog_type: str
) -> Dict[str, Any]:
    job_data = {
        "id": job_id,
        "source_id": source_id,
        "source_name": source_name,
        "direction": direction,
        "status": "pending",
        "progress": "Initializing...",
        "error": None,
        "target_keyword": target_keyword,
        "blog_type": blog_type,
        "status_message": "Initializing...",
        "error_message": None,
        "title": None,
        "meta_description": None,
        "outline": [],
        "target_word_count": 3000,
        "tone": None,
        "images": [],
        "markdown_file": None,
        "markdown_url": None,
        "preview_url": None,
        "word_count": None,
        "iterations": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    return create_job(project_id, JOB_TYPE, job_data)


def update_blog_job(project_id: str, job_id: str, **updates) -> Optional[Dict[str, Any]]:
    return update_job(project_id, job_id, **updates)


def get_blog_job(project_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_job(project_id, job_id)


def list_blog_jobs(project_id: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_jobs(project_id, JOB_TYPE, source_id)


def delete_blog_job(project_id: str, job_id: str) -> bool:
    return delete_job(project_id, job_id)
