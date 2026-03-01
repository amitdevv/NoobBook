"""
Path Utils - Centralized path management for project directories.

Educational Note: This utility provides a single source of truth for all
project-related local paths. Most user data lives in Supabase (PostgreSQL +
Storage), but some local directories are still used for:
- Prompt configurations (data/prompts/)
- Agent debug logs (data/projects/{id}/agents/)
- Temp file staging during source processing
- Background task tracking (data/tasks/)

Local Directory Structure:
    data/
    ├── projects/
    │   ├── {project_id}.json          # Project prompt config
    │   └── {project_id}/
    │       └── agents/
    │           └── web_agent/         # Agent execution logs (debug)
    │               └── {execution_id}.json
    ├── prompts/                       # AI prompt configurations
    └── tasks/                         # Background task tracking

User data (projects, sources, chats, messages, memory, costs) is stored
in Supabase. Files (raw uploads, processed text, chunks) are stored in
Supabase Storage.
"""
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)


# =============================================================================
# Base Directories
# =============================================================================

def get_data_dir() -> Path:
    """
    Get the main data directory.

    Educational Note: This is the root for all persistent data.
    Auto-creates if it doesn't exist.
    """
    path = Config.DATA_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_projects_base_dir() -> Path:
    """
    Get the base projects directory (contains all project folders).

    Educational Note: This holds individual project directories.
    Auto-creates if it doesn't exist.
    """
    path = Config.PROJECTS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_prompts_dir() -> Path:
    """
    Get the prompts directory.

    Educational Note: Contains JSON files with prompt configurations
    for different AI tasks (default, pdf_extraction, memory, etc.)
    """
    path = Config.DATA_DIR / "prompts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_tasks_dir() -> Path:
    """
    Get the tasks directory for background task tracking.
    """
    path = Config.DATA_DIR / "tasks"
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# Project-Level Directories
# =============================================================================

def get_project_dir(project_id: str) -> Path:
    """
    Get a project's directory.

    Args:
        project_id: The project UUID

    Returns:
        Path to project directory (auto-created)
    """
    path = get_projects_base_dir() / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_file(project_id: str) -> Path:
    """
    Get a project's local config file path (used by prompt_loader for custom prompts).

    Educational Note: Project metadata lives in Supabase, but custom prompt
    config is stored locally in this file.

    Args:
        project_id: The project UUID

    Returns:
        Path to {project_id}.json file
    """
    return get_projects_base_dir() / f"{project_id}.json"


# =============================================================================
# Source Directories
# =============================================================================

def get_sources_dir(project_id: str) -> Path:
    """
    Get a project's sources directory.

    Args:
        project_id: The project UUID

    Returns:
        Path to sources directory (auto-created)
    """
    path = get_project_dir(project_id) / "sources"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_raw_dir(project_id: str) -> Path:
    """
    Get the raw files directory for a project.

    Educational Note: Original uploaded files are stored here.
    These are preserved even if processing fails, allowing retry.

    Args:
        project_id: The project UUID

    Returns:
        Path to raw/ directory (auto-created)
    """
    path = get_sources_dir(project_id) / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_processed_dir(project_id: str) -> Path:
    """
    Get the processed files directory for a project.

    Educational Note: Extracted text from PDFs, images, audio, etc.
    is saved here as .txt files with page markers.

    Args:
        project_id: The project UUID

    Returns:
        Path to processed/ directory (auto-created)
    """
    path = get_sources_dir(project_id) / "processed"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_chunks_dir(project_id: str) -> Path:
    """
    Get the chunks directory for a project.

    Educational Note: For large sources that need embedding,
    text is split into chunks stored in per-source subdirectories.

    Args:
        project_id: The project UUID

    Returns:
        Path to chunks/ directory (auto-created)
    """
    path = get_sources_dir(project_id) / "chunks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_source_chunks_dir(project_id: str, source_id: str) -> Path:
    """
    Get the chunks directory for a specific source.

    Args:
        project_id: The project UUID
        source_id: The source UUID

    Returns:
        Path to chunks/{source_id}/ directory (auto-created)
    """
    path = get_chunks_dir(project_id) / source_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_sources_index_path(project_id: str) -> Path:
    """
    Get the sources index JSON file path (legacy - source metadata now in Supabase).

    Note: Source metadata is now stored in the Supabase sources table.
    This function is kept for backwards compatibility but should not be
    used for new code.

    Args:
        project_id: The project UUID

    Returns:
        Path to sources_index.json file
    """
    return get_sources_dir(project_id) / "sources_index.json"


# =============================================================================
# Chat Directories
# =============================================================================

def get_chats_dir(project_id: str) -> Path:
    """
    Get the chats directory for a project (legacy - chat data now in Supabase).

    Educational Note: Chat data is stored in Supabase (chats and messages tables).
    This directory may still be used for debug logs.

    Args:
        project_id: The project UUID

    Returns:
        Path to chats/ directory (auto-created)
    """
    path = get_project_dir(project_id) / "chats"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_chat_file(project_id: str, chat_id: str) -> Path:
    """
    Get a chat's JSON file path (legacy - chat data now in Supabase).

    Note: Chat messages are stored in the Supabase messages table.
    This function is kept for backwards compatibility but should not be
    used for new code.

    Args:
        project_id: The project UUID
        chat_id: The chat UUID

    Returns:
        Path to {chat_id}.json file
    """
    return get_chats_dir(project_id) / f"{chat_id}.json"


# =============================================================================
# AI Outputs Directories
# =============================================================================

def get_ai_outputs_dir(project_id: str) -> Path:
    """
    Get the AI outputs directory for a project.

    Educational Note: Stores outputs generated by AI agents
    like plots, charts, and other generated content.

    Args:
        project_id: The project UUID

    Returns:
        Path to ai_outputs/ directory (auto-created)
    """
    path = get_project_dir(project_id) / "ai_outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_ai_images_dir(project_id: str) -> Path:
    """
    Get the AI-generated images directory for a project.

    Educational Note: Stores plots, charts, and visualizations
    generated by the analysis agent.

    Args:
        project_id: The project UUID

    Returns:
        Path to ai_outputs/images/ directory (auto-created)
    """
    path = get_ai_outputs_dir(project_id) / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# Studio Directories
# =============================================================================

def get_studio_dir(project_id: str) -> Path:
    """
    Get the studio outputs directory for a project.

    Educational Note: Stores all studio-generated content
    (audio overviews, scripts, documents, etc.)

    Args:
        project_id: The project UUID

    Returns:
        Path to studio/ directory (auto-created)
    """
    path = get_project_dir(project_id) / "studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# Agent Directories
# =============================================================================

def get_agents_dir(project_id: str) -> Path:
    """
    Get the agents directory for a project.

    Educational Note: Stores execution logs for agent runs
    (web_agent, etc.) for debugging purposes.

    Args:
        project_id: The project UUID

    Returns:
        Path to agents/ directory (auto-created)
    """
    path = get_project_dir(project_id) / "agents"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_web_agent_dir(project_id: str) -> Path:
    """
    Get the web agent logs directory.

    Args:
        project_id: The project UUID

    Returns:
        Path to agents/web_agent/ directory (auto-created)
    """
    path = get_agents_dir(project_id) / "web_agent"
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# Initialization
# =============================================================================

def ensure_base_directories() -> None:
    """
    Ensure all base directories exist.

    Educational Note: Call this on app startup to create the
    directory structure before any files are accessed.
    This prevents FileNotFoundError on first use.
    """
    get_data_dir()
    get_projects_base_dir()
    get_prompts_dir()
    get_tasks_dir()
    logger.info("Base directories initialized")
