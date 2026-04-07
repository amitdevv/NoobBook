"""
Cost Tracking Utility - Track and calculate API costs per project.

Educational Note: This utility tracks Claude API usage costs by model.
Costs are stored in Supabase projects table and updated after each API call.

Pricing (per 1M tokens):
- Opus:   $5 input, $25 output
- Sonnet: $3 input, $15 output
- Haiku:  $1 input, $5 output
"""
import logging
from typing import Dict, Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)


# Pricing per 1M tokens
PRICING = {
    "opus": {"input": 5.0, "output": 25.0},
    "sonnet": {"input": 3.0, "output": 15.0},
    "haiku": {"input": 1.0, "output": 5.0},
}

# Tracked model buckets, in stable order. Used by _get_default_costs and
# _ensure_cost_structure so the breakdown always shows every model bucket
# even if a project has only used some of them.
_MODEL_KEYS = ("opus", "sonnet", "haiku")

# Lock for thread-safe operations
_lock = Lock()


def _get_model_key(model_string: str) -> str:
    """
    Extract model key (opus/sonnet/haiku) from full model string.

    Args:
        model_string: Full model ID like "claude-sonnet-4-6"

    Returns:
        "opus", "sonnet", or "haiku"
    """
    model_lower = model_string.lower()
    if "opus" in model_lower:
        return "opus"
    if "sonnet" in model_lower:
        return "sonnet"
    if "haiku" in model_lower:
        return "haiku"
    # Default to sonnet pricing for unknown models
    return "sonnet"


def _calculate_cost(model_key: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for a single API call.

    Args:
        model_key: "sonnet" or "haiku"
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    pricing = PRICING.get(model_key, PRICING["sonnet"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def _get_project_service():
    """Get project service (lazy import to avoid circular imports)."""
    from app.services.data_services import project_service
    return project_service


def _load_costs(project_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load cost tracking data from Supabase."""
    try:
        project_service = _get_project_service()
        owner_id = user_id or project_service.get_project_owner_id(project_id)
        if not owner_id:
            return None
        return project_service.get_project_costs(project_id, user_id=owner_id)
    except Exception as e:
        logger.error("Error loading costs for %s: %s", project_id, e)
        return None


def _save_costs(project_id: str, costs: Dict[str, Any], user_id: Optional[str] = None) -> bool:
    """Save cost tracking data to Supabase."""
    try:
        project_service = _get_project_service()
        owner_id = user_id or project_service.get_project_owner_id(project_id)
        if not owner_id:
            return False
        return project_service.update_project_costs(project_id, costs, user_id=owner_id)
    except Exception as e:
        logger.error("Error saving costs for %s: %s", project_id, e)
        return False


def _empty_bucket() -> Dict[str, Any]:
    return {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}


def _get_default_costs() -> Dict[str, Any]:
    """
    Get default cost tracking structure.

    Educational Note: Returns the initial cost tracking structure
    for projects that don't have costs yet.
    """
    return {
        "total_cost": 0.0,
        "by_model": {key: _empty_bucket() for key in _MODEL_KEYS},
    }


def _ensure_cost_structure(costs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ensure costs dict has proper structure.

    Educational Note: Initializes the cost tracking structure if it
    doesn't exist, preserving any existing data.
    """
    if costs is None:
        return _get_default_costs()

    # Ensure all required fields exist
    if "total_cost" not in costs:
        costs["total_cost"] = 0.0
    if "by_model" not in costs:
        costs["by_model"] = {}

    for model in _MODEL_KEYS:
        if model not in costs["by_model"]:
            costs["by_model"][model] = _empty_bucket()

    return costs


def add_usage(
    project_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Add API usage to project cost tracking.

    Educational Note: This function is called after each Claude API call
    to update the cumulative cost tracking in Supabase.

    Args:
        project_id: The project UUID
        model: Full model string (e.g., "claude-sonnet-4-6")
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used

    Returns:
        Updated cost tracking data or None if failed
    """
    with _lock:
        # Load current costs from Supabase
        costs = _load_costs(project_id, user_id=user_id)
        if costs is None:
            # Project might not exist or no costs yet - use defaults
            costs = _get_default_costs()

        # Ensure structure exists
        costs = _ensure_cost_structure(costs)

        # Get model key and calculate cost
        model_key = _get_model_key(model)
        call_cost = _calculate_cost(model_key, input_tokens, output_tokens)

        # Update model-specific tracking
        model_tracking = costs["by_model"][model_key]
        model_tracking["input_tokens"] += input_tokens
        model_tracking["output_tokens"] += output_tokens
        model_tracking["cost"] += call_cost

        # Update total cost
        costs["total_cost"] += call_cost

        # Save updated costs to Supabase
        if _save_costs(project_id, costs, user_id=user_id):
            return costs
        else:
            logger.warning("Failed to save costs for project %s", project_id)
            return None


def get_project_costs(project_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get cost tracking data for a project.

    Args:
        project_id: The project UUID

    Returns:
        Cost tracking data or default structure if not found
    """
    costs = _load_costs(project_id, user_id=user_id)

    # Ensure structure exists (for projects created before cost tracking)
    costs = _ensure_cost_structure(costs)

    return costs
