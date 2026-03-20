"""
Opik API key validator.

Educational Note: Validates Opik credentials by attempting to configure
the client. Gracefully handles missing opik package.
"""
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def validate_opik_key(api_key: str) -> Tuple[bool, str]:
    """Validate an Opik API key by attempting configuration."""
    if not api_key:
        return False, "API key is empty"

    try:
        import opik
        opik.configure(api_key=api_key)
        return True, "Valid Opik API key"
    except ImportError:
        return False, "opik package not installed (run: pip install opik)"
    except Exception as e:
        logger.error("Opik validation error: %s: %s", type(e).__name__, e)
        return False, f"Validation failed: {str(e)[:100]}"
