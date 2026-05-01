"""
Support-bundle assembler.

Builds an in-memory ZIP containing the rotated backend log files plus a
small bundle of deployment metadata. Total size is bounded by the log
rotation cap (5MB × 6 files = ~30MB) so building in-memory is fine.
"""
from __future__ import annotations

import io
import json
import os
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from app.api.logs.redaction import redact_line
from app.utils import logger as logger_module


def _iter_log_files() -> Iterable[Path]:
    """Yield existing log files in oldest-first order so the bundle reads
    chronologically when concatenated."""
    base = logger_module.LOG_FILE
    if base is None:
        return
    if not base.parent.exists():
        return
    archives = sorted(
        (p for p in base.parent.glob(f"{base.name}.*") if p.is_file()),
        key=lambda p: p.name,
        reverse=True,  # backend.log.5 (oldest) first → backend.log.1 (newest archive)
    )
    for p in archives:
        yield p
    if base.exists():
        yield base


def _redact_file_bytes(path: Path) -> bytes:
    """Read a log file line-by-line, apply redaction, return bytes for the ZIP entry."""
    out = io.StringIO()
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            out.write(redact_line(line))
    return out.getvalue().encode("utf-8")


def _build_info_json() -> dict:
    supabase_host = ""
    raw_url = os.getenv("SUPABASE_URL", "")
    if raw_url:
        try:
            supabase_host = urlparse(raw_url).hostname or ""
        except Exception:
            supabase_host = ""

    log_size = 0
    archive_count = 0
    if logger_module.LOG_FILE and logger_module.LOG_FILE.exists():
        log_size = logger_module.LOG_FILE.stat().st_size
    if logger_module.LOG_DIR and logger_module.LOG_DIR.exists():
        archive_count = sum(
            1 for p in logger_module.LOG_DIR.glob(f"{logger_module.LOG_FILE.name}.*")
            if p.is_file()
        )

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deployment_mode": os.getenv("FLASK_ENV", "development"),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "app_version": os.getenv("APP_VERSION", "unknown"),
        "supabase_url_host": supabase_host,
        "anthropic_tier": os.getenv("ANTHROPIC_TIER", "1"),
        "log_file_size_bytes": log_size,
        "log_archive_count": archive_count,
    }


def _build_env_keys() -> str:
    """List of env var NAMES present in the backend's environment. Names
    only — values are intentionally never included since some env vars
    legitimately hold secrets that aren't covered by the regex redactor."""
    names = sorted(os.environ.keys())
    return "\n".join(names) + "\n"


def _build_migrations_listing() -> str:
    """Either query schema_migrations from Supabase, or fall back to listing
    the on-disk migration files. Both are useful: the DB tells us what's
    actually applied, the on-disk list tells us what shipped with this build."""
    lines: list[str] = []
    try:
        from app.services.integrations.supabase import get_supabase

        supabase = get_supabase()
        resp = (
            supabase.table("schema_migrations")
            .select("filename, applied_at")
            .order("filename")
            .execute()
        )
        rows = resp.data or []
        lines.append("# Applied migrations (from schema_migrations table)")
        for r in rows:
            lines.append(f"{r.get('filename', '?')}  {r.get('applied_at', '?')}")
    except Exception as exc:
        lines.append(f"# Could not query schema_migrations: {exc}")

    lines.append("")
    lines.append("# Migration files shipped in this build")
    migrations_dir = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
    if migrations_dir.is_dir():
        for f in sorted(migrations_dir.glob("*.sql")):
            lines.append(f.name)
    else:
        lines.append(f"(directory not found: {migrations_dir})")

    return "\n".join(lines) + "\n"


def build_bundle() -> tuple[bytes, str]:
    """Assemble the bundle ZIP. Returns (bytes, suggested_filename)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    filename = f"noobbook-bundle-{timestamp}.zip"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Log files (redacted)
        any_log_written = False
        for path in _iter_log_files():
            try:
                content = _redact_file_bytes(path)
            except Exception as exc:
                content = f"# Failed to read {path.name}: {exc}\n".encode("utf-8")
            zf.writestr(path.name, content)
            any_log_written = True
        if not any_log_written:
            zf.writestr(
                "backend.log",
                b"# No log file on disk yet. The RotatingFileHandler creates it on first log line.\n",
            )

        zf.writestr("info.json", json.dumps(_build_info_json(), indent=2) + "\n")
        zf.writestr("env-keys.txt", _build_env_keys())
        zf.writestr("migrations.txt", _build_migrations_listing())

    return buf.getvalue(), filename
