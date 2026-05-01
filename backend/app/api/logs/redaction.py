"""
Redaction for log lines before they leave the server.

Conservative regex-based scrubbing — false positives (over-redacting) are
safe; false negatives (leaking a credential) are not. Tuned for the
secrets that actually appear in our logs:
  - Postgres connection strings (password segment)
  - Bearer tokens
  - JWT-shaped tokens (eyJ...)
  - Anthropic / OpenAI API key shapes
"""
from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # postgresql://user:pw@host -> postgresql://[REDACTED]@host
    (re.compile(r"(postgres(?:ql)?://)[^\s@]+@", re.IGNORECASE), r"\1[REDACTED]@"),
    # Bearer <token>
    (re.compile(r"(Bearer\s+)[\w.\-]{20,}", re.IGNORECASE), r"\1[REDACTED]"),
    # JWT-shaped (eyJ...)
    (re.compile(r"eyJ[\w\-]+\.[\w\-]+\.[\w\-]+"), "[REDACTED_JWT]"),
    # Anthropic / OpenAI keys
    (re.compile(r"sk-ant-[\w\-]+"), "[REDACTED_KEY]"),
    (re.compile(r"sk-[\w\-]{30,}"), "[REDACTED_KEY]"),
    # Supabase service / anon keys are JWTs (caught above), but the bare
    # "service_role" / "anon" tokens sometimes appear quoted as 'sbp_...'.
    (re.compile(r"sbp_[\w]{20,}"), "[REDACTED_KEY]"),
]


def redact_line(line: str) -> str:
    """Apply all redaction patterns to a single log line."""
    for pattern, replacement in _PATTERNS:
        line = pattern.sub(replacement, line)
    return line
