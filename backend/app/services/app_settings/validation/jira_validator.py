"""
Jira API credentials validator.

Educational Note: Validates Jira credentials by calling /rest/api/3/myself
which returns the authenticated user's profile. Uses Basic Auth with
email + API token. Requires JIRA_CLOUD_ID to determine the API base URL.
"""
import logging
from typing import Tuple, Optional
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


def validate_jira_key(
    api_token: str,
    email: Optional[str] = None,
    cloud_id: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Validate Jira credentials by fetching the authenticated user.

    Educational Note: Jira uses Basic Auth (email:api_token) and needs a
    Cloud ID to construct the API URL. All three fields must be provided.
    If email or cloud_id are missing, we return a helpful message telling
    the user to save those fields first.

    Args:
        api_token: Jira API token
        email: Jira account email (required for Basic Auth)
        cloud_id: Atlassian Cloud ID (required for API URL)

    Returns:
        Tuple of (is_valid, message)
    """
    if not api_token or api_token == '':
        return False, "API token is empty"

    if not email:
        return False, "Save Jira Email first, then validate the API token"

    if not cloud_id:
        return False, "Save Jira Cloud ID first, then validate the API token"

    try:
        base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"
        response = requests.get(
            f"{base_url}/myself",
            auth=HTTPBasicAuth(email, api_token),
            headers={'Accept': 'application/json'},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            display_name = data.get('displayName', 'Unknown')
            return True, f"Valid Jira credentials (user: {display_name})"
        elif response.status_code == 401:
            return False, "Invalid email or API token"
        elif response.status_code == 403:
            return False, "API token lacks required permissions"
        elif response.status_code == 404:
            return False, "Invalid Cloud ID — site not found"
        else:
            return False, f"Unexpected response: {response.status_code}"

    except requests.exceptions.Timeout:
        return False, "Connection timed out"
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to Atlassian API"
    except Exception as e:
        logger.error("Jira validation error: %s: %s", type(e).__name__, e)
        return False, f"Validation failed: {str(e)[:100]}"
