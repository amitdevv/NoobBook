"""
Mixpanel service-account credentials validator.

Educational Note: Validates Mixpanel Service Account creds by calling
/api/query/events/names with Basic Auth. All three values (username, secret,
project_id) are required — if any are missing the validator returns a helpful
hint telling the user to save the other fields first.
"""
import logging
from typing import Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

REGION_HOSTS = {
    "us": "https://mixpanel.com",
    "eu": "https://eu.mixpanel.com",
    "in": "https://in.mixpanel.com",
}


def validate_mixpanel_key(
    secret: str,
    username: Optional[str] = None,
    project_id: Optional[str] = None,
    region: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Verify Mixpanel Service Account credentials by hitting /events/names.

    Args:
        secret: MIXPANEL_SERVICE_ACCOUNT_SECRET (the one being validated)
        username: MIXPANEL_SERVICE_ACCOUNT_USERNAME (from env)
        project_id: MIXPANEL_PROJECT_ID (from env)
        region: "us" | "eu" | "in" (default "us")

    Returns:
        (is_valid, message)
    """
    if not secret:
        return False, "Service account secret is empty"

    if not username:
        return False, "Save Mixpanel Service Account Username first, then validate the secret"

    if not project_id:
        return False, "Save Mixpanel Project ID first, then validate the secret"

    host = REGION_HOSTS.get((region or "us").lower(), REGION_HOSTS["us"])
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
        if response.status_code == 401:
            return False, "Invalid service account username or secret"
        if response.status_code == 403:
            return False, "Service account lacks access to this Mixpanel project"
        if response.status_code == 404:
            return False, "Project not found — check MIXPANEL_PROJECT_ID"
        return False, f"Unexpected response: {response.status_code} - {response.text[:120]}"

    except requests.exceptions.Timeout:
        return False, "Connection timed out"
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to Mixpanel API"
    except Exception as e:
        logger.error("Mixpanel validation error: %s: %s", type(e).__name__, e)
        return False, f"Validation failed: {str(e)[:100]}"
