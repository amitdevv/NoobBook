"""
ElevenLabs API key validator.

ElevenLabs has two key formats:
- Legacy keys: long hex strings, have broad permissions
- Scoped keys (sk_ prefix): per-permission grants

Validation strategy: try each endpoint the app actually uses.
A `missing_permissions` 401 means the key IS authenticated — it just
lacks that particular scope. Only `invalid_api_key` means a bad key.

Returns a 3-tuple: (is_valid, message, warning)
- warning=True when the key is real but missing required permissions
"""
import logging
from typing import Tuple
import requests

logger = logging.getLogger(__name__)

_VALIDATION_ENDPOINTS = [
    ("GET",  "https://api.elevenlabs.io/v1/user",                             "User info"),
    ("POST", "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe", "Speech-to-text"),
    ("GET",  "https://api.elevenlabs.io/v1/models",                           "TTS models"),
    ("GET",  "https://api.elevenlabs.io/v1/voices",                           "Voices"),
]


def _check_endpoint(method: str, url: str, api_key: str) -> Tuple[str, str]:
    """Return (outcome, detail). outcome: ok | missing_permission | invalid_key | error"""
    try:
        resp = requests.request(method, url, headers={"xi-api-key": api_key}, timeout=10)

        if resp.status_code in (200, 201):
            return "ok", resp.text

        if resp.status_code == 429:
            return "ok", "rate_limited"

        if resp.status_code == 401:
            detail = resp.json().get("detail", {})
            status = detail.get("status") if isinstance(detail, dict) else None
            if status == "missing_permissions":
                return "missing_permission", detail.get("message", "")
            return "invalid_key", detail.get("message", "") if isinstance(detail, dict) else str(detail)

        return "error", f"HTTP {resp.status_code}"

    except requests.exceptions.Timeout:
        return "error", "timeout"
    except requests.exceptions.RequestException as exc:
        return "error", str(exc)


def validate_elevenlabs_key(api_key: str) -> Tuple[bool, str, bool]:
    """
    Validate an ElevenLabs API key.

    Returns:
        (is_valid, message, warning)
        - warning=True means the key is authenticated but lacks required scopes
        - message uses | as delimiter: "short summary|scope1,scope2" when warning=True
    """
    if not api_key:
        return False, "API key is empty", False

    missing_scopes = []

    for method, url, label in _VALIDATION_ENDPOINTS:
        outcome, _ = _check_endpoint(method, url, api_key)

        if outcome == "ok":
            return True, f"Valid ElevenLabs key — {label} confirmed", False

        if outcome == "invalid_key":
            return False, "Invalid API key — authentication failed", False

        if outcome == "missing_permission":
            missing_scopes.append(label)

        # network errors → skip, try next endpoint

    if missing_scopes:
        scopes_str = ",".join(missing_scopes)
        return True, f"Scoped key — grant missing permissions|{scopes_str}", True

    return False, "Could not reach ElevenLabs — check your network and try again", False
