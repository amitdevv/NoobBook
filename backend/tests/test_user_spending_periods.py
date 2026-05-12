"""
Tests for lazy user spending-period resets.
"""
from app.services.data_services.user_service import UserService


def _service_with_store(store):
    """Build a UserService instance without opening a real Supabase client."""
    svc = UserService.__new__(UserService)

    def get_user_settings_raw(_user_id):
        return dict(store)

    def save_user_settings(_user_id, settings):
        store.clear()
        store.update(settings)
        return True

    svc.get_user_settings_raw = get_user_settings_raw
    svc.save_user_settings = save_user_settings
    return svc


def test_maybe_reset_expired_spending_period_persists_zeroed_period(monkeypatch):
    store = {
        "cost_limit": 25.0,
        "reset_frequency": "weekly",
        "period_spend": 25.03,
        "period_start": "2026-05-03T03:30:00Z",
    }
    svc = _service_with_store(store)

    monkeypatch.setattr(
        "app.utils.spending_schedule.is_period_expired",
        lambda _period_start, _frequency: True,
    )
    monkeypatch.setattr(
        "app.utils.spending_schedule.aligned_period_start_iso",
        lambda _frequency: "2026-05-10T03:30:00Z",
    )

    settings = svc.maybe_reset_expired_spending_period("user-1")

    assert settings["period_spend"] == 0.0
    assert settings["period_start"] == "2026-05-10T03:30:00Z"
    assert store["period_spend"] == 0.0


def test_increment_period_spend_resets_before_adding_new_cost(monkeypatch):
    store = {
        "cost_limit": 25.0,
        "reset_frequency": "weekly",
        "period_spend": 25.03,
        "period_start": "2026-05-03T03:30:00Z",
    }
    svc = _service_with_store(store)

    monkeypatch.setattr(
        "app.utils.spending_schedule.is_period_expired",
        lambda _period_start, _frequency: True,
    )
    monkeypatch.setattr(
        "app.utils.spending_schedule.aligned_period_start_iso",
        lambda _frequency: "2026-05-10T03:30:00Z",
    )

    svc.increment_period_spend("user-1", 0.5)

    assert store["period_spend"] == 0.5
    assert store["period_start"] == "2026-05-10T03:30:00Z"
