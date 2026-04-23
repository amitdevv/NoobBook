"""
Mixpanel service-account credentials validator.

Validates Mixpanel Service Account creds by calling /api/query/events/names
with Basic Auth. All three values (username, secret, project_id) are required.
Error messages are human-readable so users can fix issues from the UI without
reading server logs — see backend/docs/mixpanel-fix.md for the full guide.
"""
import logging
from typing import Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth

from app.services.integrations.knowledge_bases.mixpanel.mixpanel_service import MixpanelService

logger = logging.getLogger(__name__)

REGION_HOSTS = MixpanelService.REGION_HOSTS


def _extract_mixpanel_error(response: requests.Response) -> str:
    """Pull the human error out of Mixpanel's JSON body, falling back to raw text."""
    try:
        body = response.json()
        if isinstance(body, dict):
            for key in ("error", "message", "detail"):
                val = body.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
    except ValueError:
        pass
    return (response.text or "").strip()


def _translate_400(err: str) -> str:
    """Map common Mixpanel 400 error strings to actionable UI messages."""
    low = err.lower()
    if "invalid project" in low or "project_id" in low:
        return (
            "Mixpanel rejected the project ID. Check that MIXPANEL_PROJECT_ID is the "
            "numeric ID from Project Settings, and that MIXPANEL_REGION matches where "
            "the project lives (us / eu / in)."
        )
    if "invalid auth" in low or "authentication" in low or "unauthorized" in low:
        return "Mixpanel rejected the service account credentials. Double-check the username and secret."
    if "no such project" in low or "not found" in low:
        return "Mixpanel could not find a project with this ID in the selected region."
    if "rate" in low and "limit" in low:
        return "Mixpanel rate limit hit during validation. Wait a minute and try again."
    return f"Mixpanel returned 400: {err}"


def validate_mixpanel_key(
    secret: str,
    username: Optional[str] = None,
    project_id: Optional[str] = None,
    region: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Verify Mixpanel Service Account credentials by hitting /events/names.

    Returns (is_valid, message). The message is user-facing — keep it short
    and actionable.
    """
    if not secret:
        return False, "Service account secret is empty"

    if not username:
        return False, "Save the Mixpanel Service Account Username first, then validate the secret"

    if not project_id:
        return False, "Save the Mixpanel Project ID first, then validate the secret"

    region_key = (region or "us").lower()
    if region_key not in REGION_HOSTS:
        return False, f"Unknown Mixpanel region '{region}'. Use us, eu, or in."

    host = REGION_HOSTS[region_key]
    url = f"{host}/api/query/events/names"

    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(username, secret),
            params={"project_id": project_id, "type": "general", "limit": 1},
            headers={"Accept": "application/json"},
            timeout=10,
        )

        if response.status_code == 200:
            return True, "Valid Mixpanel Service Account credentials"

        err = _extract_mixpanel_error(response)

        if response.status_code == 400:
            return False, _translate_400(err)
        if response.status_code == 401:
            return False, (
                "Invalid service account username or secret. Generate a new secret in "
                "Mixpanel → Organization Settings → Service Accounts if you've lost it."
            )
        if response.status_code == 403:
            return False, (
                "Service account does not have access to this Mixpanel project. "
                "In Mixpanel → Organization Settings → Service Accounts, open the "
                "service account and grant it Analyst (or higher) access to this project."
            )
        if response.status_code == 404:
            return False, (
                "Project not found. Confirm MIXPANEL_PROJECT_ID is the numeric ID "
                "shown in Project Settings, and MIXPANEL_REGION matches the project's region."
            )
        if response.status_code == 429:
            return False, "Mixpanel rate limit hit. Wait a minute and try again."

        # Fallback for unexpected codes — show the real Mixpanel error, not truncated noise.
        short = err[:200] if err else f"HTTP {response.status_code}"
        return False, f"Mixpanel returned {response.status_code}: {short}"

    except requests.exceptions.Timeout:
        return False, "Mixpanel API timed out. Try again, or check your network."
    except requests.exceptions.ConnectionError:
        return False, "Could not reach Mixpanel. Check your internet connection and MIXPANEL_REGION."
    except Exception as e:
        logger.error("Mixpanel validation error: %s: %s", type(e).__name__, e)
        return False, f"Validation failed: {str(e)[:100]}"
