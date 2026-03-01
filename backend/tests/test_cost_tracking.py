"""
Tests for cost_tracking.py.

Covers:
- _get_model_key: model string detection, case insensitivity, unknown defaults
- _calculate_cost: exact pricing math for sonnet/haiku
- _ensure_cost_structure: None, empty, partial dicts, preserves existing
- _get_default_costs: structure validation
"""
import pytest

from app.utils.cost_tracking import (
    _get_model_key,
    _calculate_cost,
    _get_default_costs,
    _ensure_cost_structure,
)


# ===========================================================================
# _get_model_key
# ===========================================================================

class TestGetModelKey:

    def test_sonnet_full_id(self):
        assert _get_model_key("claude-sonnet-4-5-20250929") == "sonnet"

    def test_haiku_full_id(self):
        assert _get_model_key("claude-haiku-3-20240307") == "haiku"

    def test_sonnet_short(self):
        assert _get_model_key("claude-sonnet-4-6") == "sonnet"

    def test_haiku_short(self):
        assert _get_model_key("claude-haiku-4-5") == "haiku"

    def test_case_insensitive(self):
        assert _get_model_key("claude-SONNET-4-6") == "sonnet"
        assert _get_model_key("CLAUDE-HAIKU-3") == "haiku"

    def test_unknown_defaults_to_sonnet(self):
        """Unknown model strings default to sonnet pricing."""
        assert _get_model_key("gpt-4o") == "sonnet"
        assert _get_model_key("unknown-model") == "sonnet"

    def test_empty_string(self):
        assert _get_model_key("") == "sonnet"


# ===========================================================================
# _calculate_cost
# ===========================================================================

class TestCalculateCost:

    def test_sonnet_input_only(self):
        """Sonnet: $3/1M input tokens → 1M tokens = $3.00"""
        assert _calculate_cost("sonnet", 1_000_000, 0) == pytest.approx(3.0)

    def test_sonnet_output_only(self):
        """Sonnet: $15/1M output tokens → 1M tokens = $15.00"""
        assert _calculate_cost("sonnet", 0, 1_000_000) == pytest.approx(15.0)

    def test_sonnet_combined(self):
        """Sonnet: 1M in + 1M out = $3 + $15 = $18"""
        assert _calculate_cost("sonnet", 1_000_000, 1_000_000) == pytest.approx(18.0)

    def test_haiku_input_only(self):
        """Haiku: $1/1M input tokens"""
        assert _calculate_cost("haiku", 1_000_000, 0) == pytest.approx(1.0)

    def test_haiku_output_only(self):
        """Haiku: $5/1M output tokens"""
        assert _calculate_cost("haiku", 0, 1_000_000) == pytest.approx(5.0)

    def test_haiku_combined(self):
        """Haiku: 1M in + 1M out = $1 + $5 = $6"""
        assert _calculate_cost("haiku", 1_000_000, 1_000_000) == pytest.approx(6.0)

    def test_zero_tokens(self):
        assert _calculate_cost("sonnet", 0, 0) == 0.0

    def test_small_usage(self):
        """1000 tokens should cost fractions of a cent."""
        cost = _calculate_cost("sonnet", 1000, 1000)
        assert cost == pytest.approx(0.018, abs=0.001)

    def test_unknown_model_uses_sonnet_pricing(self):
        """Unknown model key falls back to sonnet pricing."""
        assert _calculate_cost("opus", 1_000_000, 0) == pytest.approx(3.0)


# ===========================================================================
# _get_default_costs
# ===========================================================================

class TestGetDefaultCosts:

    def test_structure(self):
        costs = _get_default_costs()
        assert costs["total_cost"] == 0.0
        assert "sonnet" in costs["by_model"]
        assert "haiku" in costs["by_model"]

    def test_model_structure(self):
        costs = _get_default_costs()
        for model in ["sonnet", "haiku"]:
            assert costs["by_model"][model]["input_tokens"] == 0
            assert costs["by_model"][model]["output_tokens"] == 0
            assert costs["by_model"][model]["cost"] == 0.0


# ===========================================================================
# _ensure_cost_structure
# ===========================================================================

class TestEnsureCostStructure:

    def test_none_returns_defaults(self):
        result = _ensure_cost_structure(None)
        assert result["total_cost"] == 0.0
        assert "sonnet" in result["by_model"]
        assert "haiku" in result["by_model"]

    def test_empty_dict_fills_all(self):
        result = _ensure_cost_structure({})
        assert result["total_cost"] == 0.0
        assert "sonnet" in result["by_model"]

    def test_partial_dict_missing_model(self):
        """Dict with sonnet but missing haiku gets haiku added."""
        costs = {
            "total_cost": 5.0,
            "by_model": {
                "sonnet": {"input_tokens": 100, "output_tokens": 50, "cost": 5.0}
            }
        }
        result = _ensure_cost_structure(costs)
        assert result["total_cost"] == 5.0
        assert result["by_model"]["sonnet"]["cost"] == 5.0
        assert result["by_model"]["haiku"]["cost"] == 0.0

    def test_preserves_existing_values(self):
        """Existing non-zero values are not overwritten."""
        costs = {
            "total_cost": 10.5,
            "by_model": {
                "sonnet": {"input_tokens": 500, "output_tokens": 200, "cost": 10.5},
                "haiku": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
            }
        }
        result = _ensure_cost_structure(costs)
        assert result["total_cost"] == 10.5
        assert result["by_model"]["sonnet"]["input_tokens"] == 500

    def test_missing_total_cost(self):
        costs = {"by_model": {"sonnet": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}}}
        result = _ensure_cost_structure(costs)
        assert result["total_cost"] == 0.0

    def test_missing_by_model(self):
        costs = {"total_cost": 0.0}
        result = _ensure_cost_structure(costs)
        assert "sonnet" in result["by_model"]
        assert "haiku" in result["by_model"]
