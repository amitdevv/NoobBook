"""
Messages API Blueprint.

Educational Note: This blueprint handles the core AI interaction - sending
messages to Claude and receiving responses. This is where the RAG pipeline
and tool-use loop happens (delegated to main_chat_service).

The message flow:
1. User sends message via POST endpoint
2. main_chat_service builds context (sources, memory, system prompt)
3. Claude API is called with tools (search_sources, store_memory)
4. Tool use loop executes until Claude returns final response
5. Both user message and assistant response are stored and returned
"""
from flask import Blueprint, request

# Create blueprint for message operations
messages_bp = Blueprint('messages', __name__)


# Verify project ownership for all message routes
from app.utils.auth_middleware import verify_project_access  # noqa: E402

@messages_bp.before_request
def check_project_access():
    project_id = request.view_args.get('project_id') if request.view_args else None
    if project_id:
        denied = verify_project_access(project_id)
        if denied:
            return denied


# Import routes to register them with the blueprint
from app.api.messages import routes  # noqa: F401
