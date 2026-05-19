"""
EnvService — facade for reading/writing the runtime environment variables
that the rest of the app consults via ``os.getenv``.

History note: an earlier implementation wrote runtime updates to
``backend/.env`` on disk. That file is excluded by ``backend/.dockerignore``
and lives on the container's ephemeral filesystem (only ``/app/data`` is
volumed), so every key saved through the Admin Settings UI evaporated on
the next container restart. Runtime writes are now routed through
``ApiKeyStore``, which persists encrypted values into Supabase's
``app_settings.api_keys`` JSONB column. Build-time env vars (set by
docker-compose / Coolify) still take precedence — see
``ApiKeyStore.hydrate_environ``.

This class keeps the same public surface so existing callers don't change:
``get_key`` / ``set_key`` / ``delete_key`` / ``mask_key`` / ``reload_env``
all still work. ``reload_env`` is now a no-op (kept for API compat) because
there's no longer a file to reload.

Rotation note: rotating ``SECRET_KEY`` invalidates ciphertexts in the
store. The admin UI will then show the affected keys as unset and the
operator must re-save them via the UI.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class EnvService:
    """
    Service for managing environment variables.

    Reads remain ``os.getenv``-backed. Writes are dual-path: they update
    the current process's ``os.environ`` immediately (so the same request
    sees the new value) and persist into ``ApiKeyStore`` so the value
    survives container restarts.
    """

    def __init__(self):
        # Path retained only for the one-time migration of legacy
        # backend/.env entries into the store. We no longer write to this
        # file in normal operation.
        self.backend_dir = Path(__file__).parent.parent.parent.parent
        self.env_path = self.backend_dir / ".env"

        # One-shot migration: if backend/.env still has API-key entries from
        # the previous code path, move them into the store and strip them
        # from the file. Idempotent — re-running on an empty file is a no-op.
        # Best-effort: any failure (no Supabase yet, .env unreadable) is
        # logged and skipped; the rest of the app must still come up.
        try:
            from app.services.app_settings.api_key_store import (
                migrate_env_file_into_store,
            )
            # Lazy import to avoid a circular dep with API_KEYS_CONFIG.
            from app.api.settings.api_keys import API_KEYS_CONFIG  # noqa: WPS433

            known = {entry["id"] for entry in API_KEYS_CONFIG}
            migrate_env_file_into_store(self.env_path, known)
        except Exception as exc:  # noqa: BLE001 — migration is best-effort
            logger.warning("Legacy .env migration skipped: %s", exc)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def reload_env(self) -> None:
        """
        No-op kept for backwards compatibility.

        Historical behaviour: re-read ``backend/.env`` into ``os.environ``.
        Runtime writes now go through ``ApiKeyStore`` and ``os.environ`` is
        updated in place inside ``set_key`` / ``delete_key``, so this call
        has nothing to do. Existing call sites that invoke it after a save
        keep working without modification.
        """
        return None

    def get_key(self, key: str) -> Optional[str]:
        """Return the current value of an environment variable, or None."""
        return os.getenv(key)

    # ------------------------------------------------------------------
    # Writes — dual-path: os.environ (immediate) + ApiKeyStore (persistent)
    # ------------------------------------------------------------------

    def set_key(self, key: str, value: str) -> None:
        """
        Persist a key into the store and update the running process env.

        Args:
            key: Environment variable name (e.g. ``"NOTION_API_KEY"``).
            value: The value to store. Pass a non-empty string — callers
                should ``delete_key`` for clearing.
        """
        if not key or not isinstance(key, str):
            raise ValueError("Key must be a non-empty string")
        if value is None:
            raise ValueError("Value cannot be None — use delete_key to clear")

        # Update the running process first so the same request that's
        # making this save can immediately use the new value (e.g. the
        # validate-then-save flow).
        os.environ[key] = value

        # Persist — failures here are logged inside the store and don't
        # raise, but we surface a warning at the call site so the operator
        # sees a hint in the response logs.
        from app.services.app_settings.api_key_store import api_key_store

        ok = api_key_store.set(key, value)
        if not ok:
            logger.warning(
                "EnvService.set_key: persisted to os.environ but ApiKeyStore "
                "write failed for %s — value will be lost on container restart.",
                key,
            )

    def delete_key(self, key: str) -> None:
        """Remove the key from both the running process and the store."""
        if not key or not isinstance(key, str):
            raise ValueError("Key must be a non-empty string")

        os.environ.pop(key, None)

        from app.services.app_settings.api_key_store import api_key_store

        api_key_store.delete(key)

    def save(self) -> None:
        """No-op kept for backwards compatibility (writes are immediate)."""
        return None

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def mask_key(self, value: Optional[str]) -> str:
        """
        Mask an API key for display.

        Returns ``'sk-...xyz'``-style output. Short values (<= 8 chars)
        are fully masked. Empty / None returns ``''``.
        """
        if not value:
            return ""
        if len(value) <= 8:
            return "***"
        return f"{value[:3]}***{value[-3:]}"

    def get_all_keys(self) -> Dict[str, str]:
        """
        Read every persisted API key as ``{key: plaintext}``.

        Reads from the store, not from any file. Used by diagnostic
        surfaces — never echo this directly to the browser.
        """
        from app.services.app_settings.api_key_store import api_key_store

        return api_key_store.load_all()
