"""
Freshdesk API key validator.

Educational Note: Validates Freshdesk credentials by fetching a single ticket.
Uses Basic Auth with api_key as username and 'X' as password (Freshdesk convention).
Requires FRESHDESK_DOMAIN to construct the API base URL.
"""
import logging
from typing import Tuple, Optional
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


def validate_freshdesk_key(
    api_key: str,
    domain: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validate Freshdesk credentials by fetching tickets endpoint.

    Args:
        api_key: Freshdesk API key
        domain: Freshdesk domain (e.g. 'company.freshdesk.com' or 'company')

    Returns:
        Tuple of (is_valid, message)
    """
    if not api_key:
        return False, "API key is empty"

    if not domain:
        return False, "Save Freshdesk Domain first, then validate the API key"

    # Normalize domain
    if ".freshdesk.com" not in domain:
        domain = f"{domain}.freshdesk.com"

    try:
        response = requests.get(
            f"https://{domain}/api/v2/tickets?per_page=1",
            auth=HTTPBasicAuth(api_key, "X"),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code == 200:
            tickets = response.json()
            count = len(tickets) if isinstance(tickets, list) else 0
            return True, f"Valid Freshdesk credentials ({domain}, {count} ticket(s) accessible)"
        elif response.status_code == 401:
            return False, "Invalid API key"
        elif response.status_code == 403:
            return False, "API key lacks required permissions"
        elif response.status_code == 404:
            return False, f"Domain not found: {domain}"
        else:
            return False, f"Unexpected response: {response.status_code}"

    except requests.exceptions.Timeout:
        return False, "Connection timed out"
    except requests.exceptions.ConnectionError:
        return False, f"Could not connect to {domain}"
    except Exception as e:
        logger.error("Freshdesk validation error: %s: %s", type(e).__name__, e)
        return False, f"Validation failed: {str(e)[:100]}"
