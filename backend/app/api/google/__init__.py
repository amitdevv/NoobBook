"""
Google Drive Integration API Blueprint.

Educational Note: This blueprint demonstrates OAuth 2.0 integration with
external services. Google Drive integration allows users to import files
directly from their cloud storage.

Key OAuth Concepts:
1. Authorization URL - Where we send users to grant permission
2. Callback URL - Where Google redirects after user grants/denies
3. Authorization Code - Temporary code exchanged for tokens
4. Access Token - Short-lived token for API calls
5. Refresh Token - Long-lived token to get new access tokens

The flow:
1. User clicks "Connect Google Drive"
2. Frontend calls /google/auth to get authorization URL
3. User is redirected to Google, grants permission
4. Google redirects to /google/callback with auth code
5. We exchange code for tokens, store them
6. User can now list and import files
"""
from flask import Blueprint, request

# Create blueprint for Google Drive integration
google_bp = Blueprint('google', __name__)


# Verify project ownership for Google import endpoint (has project_id)
# Skips non-project routes like /google/auth, /google/files, etc.
from app.utils.auth_middleware import verify_project_access  # noqa: E402

@google_bp.before_request
def check_project_access():
    if request.method == 'OPTIONS':
        return None
    project_id = request.view_args.get('project_id') if request.view_args else None
    if project_id:
        denied = verify_project_access(project_id)
        if denied:
            return denied


# Import routes to register them with the blueprint
from app.api.google import oauth  # noqa: F401
from app.api.google import drive  # noqa: F401
