"""
ApiKeyStore — persistent, encrypted storage for API keys configured via the
Admin Settings → API Keys UI.

Why this exists:
    `env_service.set_key()` used to write to /app/.env, which is excluded by
    backend/.dockerignore and lives on the container's ephemeral filesystem.
    Every key saved through the UI vanished on the next container restart.
    This module stores those keys in the Supabase `app_settings.api_keys`
    JSONB column so they survive restarts, redeploys, OOM kills, etc.

Encryption:
    Values are Fernet-encrypted before insert. The encryption key is derived
    from the SECRET_KEY env var (SHA-256 → urlsafe-base64). If SECRET_KEY is
    missing — e.g. a dev workstation that hasn't bootstrapped one — values
    are stored with a `plain:` prefix so the store keeps working without
    crashing the admin UI; a warning is logged so the operator notices.

Source resolution at runtime:
    Build-time env vars (set by docker-compose `environment:` / Coolify
    secrets) take precedence over DB values. `hydrate_environ()` only sets
    os.environ keys that are currently unset or empty — letting an operator
    "pin" a key via host env if they want to, while the UI is otherwise
    authoritative.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)


_PLAINTEXT_PREFIX = "plain:"


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a Fernet-compatible 32-byte key from SECRET_KEY via SHA-256."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class ApiKeyStore:
    """
    Singleton-style accessor for the encrypted app_settings.api_keys JSONB.

    Methods are deliberately small and synchronous: this gets called on
    every Admin Settings save and at app startup, and the data set is tiny
    (≤ 30 keys per deploy), so a JSONB read-modify-write per call is fine.
    """

    def __init__(self) -> None:
        secret = os.getenv("SECRET_KEY", "").strip()
        if secret:
            self._fernet: Optional[Fernet] = Fernet(_derive_fernet_key(secret))
            self._encryption_disabled = False
        else:
            self._fernet = None
            self._encryption_disabled = True
            logger.warning(
                "SECRET_KEY is not set — ApiKeyStore will store values without "
                "encryption (prefixed with 'plain:'). Set SECRET_KEY in your "
                "environment to enable Fernet encryption-at-rest."
            )

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------

    def _encrypt(self, value: str) -> str:
        if self._encryption_disabled or self._fernet is None:
            return f"{_PLAINTEXT_PREFIX}{value}"
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def _decrypt(self, ciphertext: str) -> Optional[str]:
        if ciphertext.startswith(_PLAINTEXT_PREFIX):
            return ciphertext[len(_PLAINTEXT_PREFIX):]
        if self._fernet is None:
            # Ciphertext exists but we can't decrypt it because SECRET_KEY is
            # missing now. Log and skip — the admin UI will show the key as
            # unset and the operator can re-enter it.
            logger.warning(
                "Cannot decrypt stored API key — SECRET_KEY missing or rotated. "
                "Operator must re-save the key via the UI."
            )
            return None
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken:
            logger.warning(
                "Stored API key ciphertext failed decryption (likely rotated "
                "SECRET_KEY). Operator must re-save the affected key."
            )
            return None

    # ------------------------------------------------------------------
    # Supabase access
    # ------------------------------------------------------------------

    def _read_raw(self) -> Dict[str, str]:
        """Return the raw {key: ciphertext} map from Supabase, or {} on miss."""
        if not is_supabase_enabled():
            return {}
        try:
            client = get_supabase()
            resp = (
                client.table("app_settings")
                .select("api_keys")
                .eq("id", True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.warning("ApiKeyStore: could not read app_settings: %s", exc)
            return {}
        rows = resp.data or []
        if not rows:
            return {}
        return rows[0].get("api_keys") or {}

    def _write_raw(self, raw: Dict[str, str]) -> bool:
        """Persist the full raw map. Caller is responsible for read-modify-write."""
        if not is_supabase_enabled():
            return False
        try:
            client = get_supabase()
            resp = (
                client.table("app_settings")
                .update({"api_keys": raw})
                .eq("id", True)
                .execute()
            )
            return bool(resp.data)
        except Exception as exc:
            logger.exception("ApiKeyStore: failed to write api_keys: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_all(self) -> Dict[str, str]:
        """Return {key_id: plaintext} for every successfully-decrypted entry."""
        raw = self._read_raw()
        out: Dict[str, str] = {}
        for k, ciphertext in raw.items():
            if not isinstance(ciphertext, str):
                continue
            plaintext = self._decrypt(ciphertext)
            if plaintext is not None:
                out[k] = plaintext
        return out

    def has(self, key_id: str) -> bool:
        return key_id in self._read_raw()

    def set(self, key_id: str, value: str) -> bool:
        if not key_id:
            return False
        raw = self._read_raw()
        raw[key_id] = self._encrypt(value)
        return self._write_raw(raw)

    def delete(self, key_id: str) -> bool:
        if not key_id:
            return False
        raw = self._read_raw()
        if key_id not in raw:
            return True  # nothing to do — idempotent
        del raw[key_id]
        return self._write_raw(raw)

    def hydrate_environ(self) -> int:
        """
        Populate os.environ with stored keys for any that are currently unset
        or empty. Build-time env vars win when both are present — that lets
        an operator pin a key via host env if they want, while the UI remains
        authoritative for everything else. Returns the count of vars hydrated.
        """
        applied = 0
        for k, v in self.load_all().items():
            existing = os.environ.get(k)
            if existing is None or existing == "":
                os.environ[k] = v
                applied += 1
        if applied:
            logger.info("ApiKeyStore: hydrated %d API key(s) from Supabase", applied)
        return applied


# Module-level helper for the one-time migration of any legacy
# `backend/.env` API-key entries into the store. Called from EnvService
# during first __init__ so existing self-hosted deployments don't lose
# their previously-saved keys.
def migrate_env_file_into_store(env_file: Path, known_keys: set[str]) -> int:
    """
    If `env_file` exists and contains any KEY=VALUE lines whose key is in
    `known_keys` (i.e. recognized by API_KEYS_CONFIG), copy each into the
    store and strip those lines from the file. Returns the count migrated.
    Non-API keys (PORT, FLASK_ENV, etc.) are left untouched.
    """
    if not env_file.exists():
        return 0
    try:
        text = env_file.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not read %s for API-key migration: %s", env_file, exc)
        return 0

    keep_lines: list[str] = []
    migrated: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            keep_lines.append(line)
            continue
        k, v = stripped.split("=", 1)
        k = k.strip()
        # Trim matching surrounding quotes only
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        if k in known_keys and v:
            migrated.append((k, v))
            continue
        keep_lines.append(line)

    if not migrated:
        return 0

    store = ApiKeyStore()
    written = 0
    for k, v in migrated:
        if store.set(k, v):
            written += 1
        else:
            # If the write failed (e.g. Supabase unreachable), bail without
            # touching the file so we don't lose the operator's keys.
            logger.warning(
                "ApiKeyStore migration could not persist %s — leaving %s "
                "untouched and skipping cleanup.",
                k,
                env_file,
            )
            return written

    try:
        env_file.write_text("\n".join(keep_lines) + ("\n" if keep_lines else ""), encoding="utf-8")
        logger.info(
            "ApiKeyStore migration: moved %d API key(s) from %s into Supabase.",
            written,
            env_file,
        )
    except Exception as exc:
        logger.warning("Could not rewrite %s after migration: %s", env_file, exc)
    return written


# Singleton-ish instance for callers that just need the store.
api_key_store = ApiKeyStore()
