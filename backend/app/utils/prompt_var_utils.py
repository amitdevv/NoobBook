"""
Prompt variable utilities (Roadmap #16).

The admin-editable prompts feature lets operators rewrite the body of any
shipped prompt. A handful of those prompts are templates consumed by
``str.format(...)`` calls inside services — e.g. ``memory_service`` does
``user_message.format(memory_type=..., current_memory=..., new_memory=...,
reason=...)``. If an admin removes one of those tokens during an edit, the
``.format`` call raises ``KeyError`` at runtime and the feature breaks
silently for end users.

This module provides:

* ``extract_vars(text)``   — pull single-token ``{var_name}`` placeholders
                             out of a prompt body, ignoring multi-token /
                             JSON-shaped curly braces.
* ``required_vars(base)``  — compute the set of vars that *must* remain in
                             a given prompt config (system_prompt +
                             user_message + user_message_template).
* ``validate_edit(...)``   — used by the PUT handler to reject saves that
                             would drop required tokens.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Single-token placeholder. Lowercase + underscore + digits, must start
# with a letter or underscore — matches Python identifier conventions, so
# JSON shapes like ``{"key": "value"}`` (which contain colons and quotes)
# don't accidentally match.
_VAR_PATTERN = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


# Fields we look at when computing required vars / validating edits. Some
# prompts use ``user_message``, others ``user_message_template`` — accept
# both.
_TEMPLATED_FIELDS = ("system_prompt", "user_message", "user_message_template")


def extract_vars(text: str) -> List[str]:
    """
    Return the deduped list of placeholder names in document order.

    Empty input or a non-string returns an empty list. Duplicates are
    collapsed but order of first occurrence is preserved so messages
    like "Missing: {a}, {b}" are stable across runs.
    """
    if not isinstance(text, str) or not text:
        return []
    seen: List[str] = []
    in_set: set[str] = set()
    for match in _VAR_PATTERN.finditer(text):
        name = match.group(1)
        if name not in in_set:
            in_set.add(name)
            seen.append(name)
    return seen


def _combined_template_text(config: Dict[str, object]) -> str:
    """Concatenate the templated fields of a prompt config for var scanning."""
    parts: List[str] = []
    for field in _TEMPLATED_FIELDS:
        value = config.get(field)
        if isinstance(value, str) and value:
            parts.append(value)
    return "\n".join(parts)


def required_vars(base_config: Dict[str, object]) -> List[str]:
    """
    Return the variables that must remain in any edited version of this prompt.

    "Required" = present in the *base* config (i.e., the shipped default).
    Adding new variables in an override is fine — only removing existing
    ones is a problem because some service in the codebase already calls
    ``.format(**that_var=...)`` and would crash on KeyError.
    """
    return extract_vars(_combined_template_text(base_config))


def validate_edit(
    base_config: Dict[str, object],
    edited_config: Dict[str, object],
) -> Tuple[bool, List[str], List[str]]:
    """
    Compare the edited prompt against the base and report differences.

    Returns ``(ok, missing, extra)``:
      * ``missing`` — required vars that have disappeared from the edit.
        Non-empty ⇒ ``ok`` is False; the save must be rejected.
      * ``extra``   — new vars the admin introduced that the base didn't
                      have. Informational only — admins are free to add
                      placeholders, with the caveat that the consuming
                      service has to supply them. Surfaced in the UI as a
                      yellow warning.
    """
    required = set(required_vars(base_config))

    # For "present" we look at the merged effective config (base ∪ override
    # for the templated fields the admin touched). The caller passes
    # ``edited_config`` which is the merged result — already contains the
    # fields the admin updated, falling through to base for the rest.
    present = set(extract_vars(_combined_template_text(edited_config)))

    missing = sorted(required - present)
    extra = sorted(present - required)
    ok = not missing
    return ok, missing, extra
