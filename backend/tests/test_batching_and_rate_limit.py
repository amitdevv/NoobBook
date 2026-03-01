"""
Tests for batching_utils and rate_limit_utils.

Covers:
- create_batches: empty, exact division, remainder, single item, invalid size
- get_batch_info: even division edge case, empty input
- RateLimiter: counter increment, window reset, remaining_requests, reset()
"""
import pytest
import time
from unittest.mock import patch

from app.utils.batching_utils import create_batches, get_batch_info, DEFAULT_BATCH_SIZE
from app.utils.rate_limit_utils import RateLimiter


# ===========================================================================
# create_batches
# ===========================================================================

class TestCreateBatches:

    def test_empty_list(self):
        assert create_batches([], 5) == []

    def test_exact_division(self):
        result = create_batches([1, 2, 3, 4, 5, 6], 3)
        assert result == [[1, 2, 3], [4, 5, 6]]

    def test_remainder(self):
        result = create_batches([1, 2, 3, 4, 5, 6, 7], 3)
        assert result == [[1, 2, 3], [4, 5, 6], [7]]

    def test_single_batch_when_items_less_than_size(self):
        result = create_batches([1, 2, 3], 5)
        assert result == [[1, 2, 3]]

    def test_single_item(self):
        result = create_batches([1], 1)
        assert result == [[1]]

    def test_batch_size_one(self):
        result = create_batches([1, 2, 3], 1)
        assert result == [[1], [2], [3]]

    def test_invalid_batch_size_zero(self):
        with pytest.raises(ValueError):
            create_batches([1, 2], 0)

    def test_invalid_batch_size_negative(self):
        with pytest.raises(ValueError):
            create_batches([1, 2], -1)

    def test_default_batch_size_is_five(self):
        assert DEFAULT_BATCH_SIZE == 5

    def test_preserves_types(self):
        """Works with any type, not just integers."""
        result = create_batches(["a", "b", "c"], 2)
        assert result == [["a", "b"], ["c"]]


# ===========================================================================
# get_batch_info
# ===========================================================================

class TestGetBatchInfo:

    def test_basic_info(self):
        info = get_batch_info([1, 2, 3, 4, 5, 6, 7], 3)
        assert info["total_items"] == 7
        assert info["batch_size"] == 3
        assert info["total_batches"] == 3
        assert info["last_batch_size"] == 1

    def test_even_division(self):
        """When items divide evenly, last_batch_size == batch_size (not 0)."""
        info = get_batch_info([1, 2, 3, 4, 5, 6], 3)
        assert info["total_batches"] == 2
        assert info["last_batch_size"] == 3

    def test_single_item(self):
        info = get_batch_info([1], 5)
        assert info["total_batches"] == 1
        assert info["last_batch_size"] == 1

    def test_empty_list(self):
        info = get_batch_info([], 5)
        assert info["total_items"] == 0
        assert info["total_batches"] == 0
        assert info["last_batch_size"] == 0

    def test_invalid_batch_size(self):
        info = get_batch_info([1, 2], 0)
        assert info["total_items"] == 0


# ===========================================================================
# RateLimiter
# ===========================================================================

class TestRateLimiter:

    def test_initial_remaining(self):
        limiter = RateLimiter(10)
        assert limiter.remaining_requests == 10

    def test_counter_increments(self):
        limiter = RateLimiter(10)
        limiter.wait_if_needed()
        assert limiter.remaining_requests == 9

    def test_multiple_calls(self):
        limiter = RateLimiter(5)
        for _ in range(3):
            limiter.wait_if_needed()
        assert limiter.remaining_requests == 2

    def test_reset(self):
        limiter = RateLimiter(10)
        for _ in range(5):
            limiter.wait_if_needed()
        limiter.reset()
        assert limiter.remaining_requests == 10

    def test_window_expired_resets_remaining(self):
        """After 60s, remaining_requests returns full limit."""
        limiter = RateLimiter(10)
        limiter.wait_if_needed()  # Use 1 request
        assert limiter.remaining_requests == 9

        # Simulate window expiry
        limiter._minute_start_time = time.time() - 61
        assert limiter.remaining_requests == 10

    def test_seconds_until_reset_expired(self):
        limiter = RateLimiter(10)
        # Set start time to 61 seconds ago
        limiter._minute_start_time = time.time() - 61
        assert limiter.seconds_until_reset == 0.0

    def test_seconds_until_reset_active(self):
        limiter = RateLimiter(10)
        limiter.wait_if_needed()  # Starts the window
        remaining = limiter.seconds_until_reset
        assert 0 < remaining <= 60

    def test_wait_if_needed_returns_zero_when_not_limited(self):
        limiter = RateLimiter(100)
        waited = limiter.wait_if_needed()
        assert waited == 0.0

    def test_window_reset_on_new_call(self):
        """Calling wait_if_needed after window expiry resets counter."""
        limiter = RateLimiter(10)
        for _ in range(5):
            limiter.wait_if_needed()

        # Simulate window expiry
        limiter._minute_start_time = time.time() - 61
        limiter.wait_if_needed()

        # Counter should have been reset to 0, then incremented to 1
        assert limiter.remaining_requests == 9
