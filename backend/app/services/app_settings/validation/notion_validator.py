"""
Notion API key validator.

Educational Note: Validates Notion integration tokens by calling the
/v1/users/me endpoint, which returns the bot user associated with the token.
This is a free, read-only API call — no data is created or modified.
"""
import logging
from typing import Tuple
import requests

logger = logging.getLogger(__name__)


def validate_notion_key(api_key: str) -> Tuple[bool, str]:
    """
    Validate a Notion API key by fetching the bot user info.

    Uses GET /v1/users/me — returns bot identity if token is valid.

    Args:
        api_key: The Notion integration token to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not api_key or api_key == '':
        return False, "API key is empty"

    try:
        response = requests.get(
            'https://api.notion.com/v1/users/me',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Notion-Version': '2022-06-28'
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            bot_name = data.get('name', 'Unknown')
            return True, f"Valid Notion key (bot: {bot_name})"
        elif response.status_code == 401:
            return False, "Invalid API key"
        elif response.status_code == 403:
            return False, "API key lacks required permissions"
        else:
            return False, f"Unexpected response: {response.status_code}"

    except requests.exceptions.Timeout:
        return False, "Connection timed out"
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to Notion API"
    except Exception as e:
        logger.error("Notion validation error: %s: %s", type(e).__name__, e)
        return False, f"Validation failed: {str(e)[:100]}"
