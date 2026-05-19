"""
Tests for ApiKeyStore — encrypted persistence of API keys.

These tests stub out the Supabase client so the round-trips happen against
a dict the test controls. The Fernet path is exercised end-to-end (real
crypto) when SECRET_KEY is set; the plaintext-fallback path is exercised
when it's not.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest.mock import MagicMock

# Supabase auth_service constructs a dedicated client at import time.
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault(
    "SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoidGVzdCJ9.test",
)


def _import_store_module():
    return importlib.import_module(
        "app.services.app_settings.api_key_store"
    )


class _FakeAppSettingsTable:
    """In-memory stand-in for the Supabase app_settings table singleton row."""

    def __init__(self, initial: dict | None = None) -> None:
        self.row = {"api_keys": dict(initial or {})}

    def select(self, _columns: str):
        return _Query(self, mode="select")

    def update(self, payload: dict):
        return _Query(self, mode="update", payload=payload)


class _Query:
    def __init__(self, table: _FakeAppSettingsTable, mode: str, payload=None):
        self.table = table
        self.mode = mode
        self.payload = payload
        self._where_id = None

    def eq(self, _column: str, value):  # only used for ("id", True)
        self._where_id = value
        return self

    def limit(self, _n: int):
        return self

    def execute(self):
        if self.mode == "select":
            return MagicMock(data=[{"api_keys": dict(self.table.row["api_keys"])}])
        if self.mode == "update" and self.payload is not None:
            self.table.row["api_keys"] = dict(self.payload["api_keys"])
            return MagicMock(data=[{"api_keys": dict(self.table.row["api_keys"])}])
        return MagicMock(data=[])


def _install_fake_supabase(monkeypatch, table: _FakeAppSettingsTable):
    """Wire a fake Supabase client into the store's get_supabase()."""
    store_mod = _import_store_module()
    client = MagicMock()
    client.table.return_value = table
    monkeypatch.setattr(store_mod, "get_supabase", lambda: client)
    monkeypatch.setattr(store_mod, "is_supabase_enabled", lambda: True)
    return store_mod


# ---------------------------------------------------------------------------
# Encryption round-trip
# ---------------------------------------------------------------------------


def test_fernet_round_trip_preserves_value(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-for-fernet-derivation")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    store = store_mod.ApiKeyStore()
    assert store.set("NOTION_API_KEY", "ntn_top_secret_value") is True

    # The raw column must not contain the plaintext.
    stored_ciphertext = table.row["api_keys"]["NOTION_API_KEY"]
    assert "ntn_top_secret_value" not in stored_ciphertext
    assert not stored_ciphertext.startswith("plain:")

    # Round-tripping via a fresh ApiKeyStore instance (same SECRET_KEY)
    # must recover the original.
    fresh = store_mod.ApiKeyStore()
    loaded = fresh.load_all()
    assert loaded["NOTION_API_KEY"] == "ntn_top_secret_value"


def test_plaintext_fallback_when_secret_key_missing(monkeypatch, caplog):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    with caplog.at_level("WARNING"):
        store = store_mod.ApiKeyStore()
    assert any("SECRET_KEY" in r.message for r in caplog.records)

    store.set("FOO", "bar")
    raw = table.row["api_keys"]["FOO"]
    assert raw.startswith("plain:")
    assert store.load_all() == {"FOO": "bar"}


def test_decrypt_fails_gracefully_after_secret_rotation(monkeypatch):
    """If SECRET_KEY rotates, old ciphertexts can't decrypt; load_all skips
    them instead of throwing so the admin UI keeps working."""
    monkeypatch.setenv("SECRET_KEY", "original-secret")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    store_mod.ApiKeyStore().set("FOO", "bar")
    # Rotate the secret — a NEW store instance will use a different Fernet key.
    monkeypatch.setenv("SECRET_KEY", "rotated-secret")
    loaded = store_mod.ApiKeyStore().load_all()
    assert "FOO" not in loaded  # decryption silently skipped


# ---------------------------------------------------------------------------
# hydrate_environ
# ---------------------------------------------------------------------------


def test_source_classification_uses_value_match_not_just_presence(monkeypatch):
    """
    Regression: when an operator pins a key via the host env AND a stale DB
    entry exists for the same name, source must be 'env' (not 'db'). The
    earlier implementation classified by name presence, which silently
    exposed pinned keys as editable in the UI.
    """
    monkeypatch.setenv("SECRET_KEY", "s")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    # Both stores have an entry for the same key, but the values differ.
    store_mod.ApiKeyStore().set("NOTION_API_KEY", "stale-db-value")
    monkeypatch.setenv("NOTION_API_KEY", "host-pinned-value")

    # This is the exact comparison the GET handler performs.
    db_values = store_mod.ApiKeyStore().load_all()
    value = os.environ["NOTION_API_KEY"]
    if not value:
        source = "unset"
    elif db_values.get("NOTION_API_KEY") == value:
        source = "db"
    else:
        source = "env"
    assert source == "env"


def test_hydrate_environ_does_not_overwrite_existing(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    # DB has one value; os.environ has a non-empty competing value.
    store_mod.ApiKeyStore().set("PINNED_BY_HOST", "db-value")
    monkeypatch.setenv("PINNED_BY_HOST", "host-value")

    store_mod.ApiKeyStore().hydrate_environ()
    assert os.environ["PINNED_BY_HOST"] == "host-value"


def test_hydrate_environ_fills_in_empty(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    store_mod.ApiKeyStore().set("UNSET_BY_HOST", "from-db")
    monkeypatch.delenv("UNSET_BY_HOST", raising=False)

    n = store_mod.ApiKeyStore().hydrate_environ()
    assert n >= 1
    assert os.environ["UNSET_BY_HOST"] == "from-db"


# ---------------------------------------------------------------------------
# JSONB merge preserves unrelated keys
# ---------------------------------------------------------------------------


def test_set_preserves_unrelated_keys(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    store = store_mod.ApiKeyStore()
    store.set("A", "alpha")
    store.set("B", "beta")
    store.set("A", "alpha2")  # update, not replace-whole-map

    loaded = store.load_all()
    assert loaded == {"A": "alpha2", "B": "beta"}


def test_delete_is_idempotent(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    store = store_mod.ApiKeyStore()
    store.set("A", "alpha")
    assert store.delete("A") is True
    assert store.delete("A") is True  # no-op the second time
    assert store.load_all() == {}


# ---------------------------------------------------------------------------
# First-boot legacy migration
# ---------------------------------------------------------------------------


def test_migrate_env_file_moves_known_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# header comment\n"
        "NOTION_API_KEY=ntn_legacy_value\n"
        "PORT=5001\n"  # unrelated — must be kept
        "OPENAI_API_KEY=\"sk-quoted\"\n"
        "\n",
        encoding="utf-8",
    )

    migrated = store_mod.migrate_env_file_into_store(
        env_file, known_keys={"NOTION_API_KEY", "OPENAI_API_KEY"}
    )
    assert migrated == 2

    # Store has the keys (decrypted).
    loaded = store_mod.ApiKeyStore().load_all()
    assert loaded["NOTION_API_KEY"] == "ntn_legacy_value"
    assert loaded["OPENAI_API_KEY"] == "sk-quoted"

    # PORT must still be in the file.
    text = env_file.read_text(encoding="utf-8")
    assert "PORT=5001" in text
    assert "NOTION_API_KEY" not in text
    assert "OPENAI_API_KEY" not in text


def test_migrate_env_file_skips_when_no_matching_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    env_file = tmp_path / ".env"
    env_file.write_text("PORT=5001\nFLASK_ENV=production\n", encoding="utf-8")
    before = env_file.read_text(encoding="utf-8")

    n = store_mod.migrate_env_file_into_store(
        env_file, known_keys={"NOTION_API_KEY"}
    )
    assert n == 0
    # File untouched.
    assert env_file.read_text(encoding="utf-8") == before


def test_migrate_env_file_absent_is_zero(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s")
    table = _FakeAppSettingsTable()
    store_mod = _install_fake_supabase(monkeypatch, table)

    missing = tmp_path / "nope.env"
    assert store_mod.migrate_env_file_into_store(missing, {"NOTION_API_KEY"}) == 0
