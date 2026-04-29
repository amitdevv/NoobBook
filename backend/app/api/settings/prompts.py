"""
Admin Prompts settings endpoints (Roadmap #16).

Surface every shipped prompt config under ``backend/data/prompts/`` to
admins through Settings → Prompts. Admins can rewrite the body, change
``max_tokens`` / ``temperature``, and reset back to the shipped default.
Critical ``.format()`` placeholders (e.g. ``{current_memory}`` in
``memory_prompt``) are auto-detected from the shipped default and the
PUT validator rejects any save that drops one — preventing a stale
admin edit from blowing up a downstream service with KeyError at
runtime.

Persistence: edits land in ``data/prompt_overrides/<name>_prompt.json``,
sibling of the shipped defaults. The container entrypoint's
``cp /app/_prompts_staging/* data/prompts/`` doesn't touch this
sibling directory, so admin edits survive redeploys.

Routes:
  GET    /settings/prompts                      — list summaries
  GET    /settings/prompts/<name>               — full config + required vars
  PUT    /settings/prompts/<name>               — update; validate; write override
  DELETE /settings/prompts/<name>/override      — reset to shipped default

``model`` is intentionally NOT writable here — the existing
``/settings/models`` endpoint owns per-category model overrides via env
vars, and dual-writing the model would create two competing sources of
truth. The editor surfaces ``model`` read-only with a "Edit in Models →"
link.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import current_app, jsonify, request

from app.api.settings import settings_bp
from app.config import prompt_loader
from app.config.prompt_referenced_by import referenced_by
from app.services.auth.rbac import require_admin
from app.utils.prompt_var_utils import extract_vars, required_vars, validate_edit


# Only these fields are writable through this endpoint. The admin can
# leave any subset out of the PUT body — only the keys present are
# overridden, the rest fall back to the shipped default.
_EDITABLE_FIELDS = ("system_prompt", "user_message", "user_message_template", "max_tokens", "temperature")


def _summarize(prompt_name: str, base: Dict[str, Any], effective: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a list-row payload — what the left-rail in the UI shows."""
    return {
        "prompt_name": prompt_name,
        "name": effective.get("name") or prompt_name,
        "description": effective.get("description") or "",
        "model": effective.get("model"),
        "default_model": base.get("model"),
        "max_tokens": effective.get("max_tokens"),
        "temperature": effective.get("temperature"),
        "has_override": bool(prompt_loader.has_override(prompt_name)),
        "required_vars": required_vars(base),
    }


def _detail(prompt_name: str) -> Optional[Dict[str, Any]]:
    """Shape a full editor-detail payload — what the right pane shows."""
    base = prompt_loader.get_prompt_default_config(prompt_name)
    if base is None:
        return None
    override = prompt_loader._load_override(prompt_name)  # noqa: SLF001 — same module family
    effective = prompt_loader.get_prompt_config(prompt_name) or base

    base_dict = dict(base)
    effective_dict = dict(effective)

    return {
        "prompt_name": prompt_name,
        "base": base_dict,
        "override": override,
        "effective": effective_dict,
        "required_vars": required_vars(base_dict),
        "current_vars": extract_vars(
            "\n".join(
                str(effective_dict.get(f) or "")
                for f in ("system_prompt", "user_message", "user_message_template")
            )
        ),
        "referenced_by": referenced_by(prompt_name),
        "editable_fields": list(_EDITABLE_FIELDS),
    }


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────

@settings_bp.route('/settings/prompts', methods=['GET'])
@require_admin
def list_prompts():
    """Return one row per shipped prompt — for the left rail."""
    try:
        rows: List[Dict[str, Any]] = []
        for effective in prompt_loader.list_all_prompts():
            prompt_name = effective.get("prompt_name")
            if not prompt_name:
                continue
            base = prompt_loader.get_prompt_default_config(prompt_name)
            if base is None:
                continue
            rows.append(_summarize(prompt_name, dict(base), effective))
        # Stable ordering — alphabetical on prompt_name. The list_all_prompts
        # call above already sorts by filename, but be explicit.
        rows.sort(key=lambda r: r["prompt_name"])
        return jsonify({"success": True, "prompts": rows, "count": len(rows)}), 200
    except Exception as e:
        current_app.logger.error("Error listing prompts: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route('/settings/prompts/<prompt_name>', methods=['GET'])
@require_admin
def get_prompt(prompt_name: str):
    """Return the full editor payload for one prompt."""
    try:
        detail = _detail(prompt_name)
        if detail is None:
            return jsonify({
                "success": False,
                "error": f"Unknown prompt: {prompt_name}",
            }), 404
        return jsonify({"success": True, "prompt": detail}), 200
    except Exception as e:
        current_app.logger.error("Error fetching prompt %s: %s", prompt_name, e)
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route('/settings/prompts/<prompt_name>', methods=['PUT'])
@require_admin
def update_prompt(prompt_name: str):
    """
    Apply an admin edit. Body keys that aren't in ``_EDITABLE_FIELDS`` are
    silently ignored (conservative — easier than a 400 for a benign client
    that bundles read-only fields it just received from GET).

    Validation:
      * ``max_tokens`` must be a positive int (cap at 64k just to be safe).
      * ``temperature`` must be a number in [0, 2].
      * Any required ``.format()`` token in the shipped default must
        still be present in the merged effective body.
    """
    try:
        base = prompt_loader.get_prompt_default_config(prompt_name)
        if base is None:
            return jsonify({
                "success": False,
                "error": f"Unknown prompt: {prompt_name}",
            }), 404
        base_dict = dict(base)

        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({
                "success": False,
                "error": "Request body must be a JSON object",
            }), 400

        # Build the override from the editable subset of the body.
        override: Dict[str, Any] = {}
        for field in _EDITABLE_FIELDS:
            if field in body:
                override[field] = body[field]

        # Per-field type checks — one pass before persisting so a single
        # bad field doesn't leave a half-written override on disk.
        if "max_tokens" in override:
            v = override["max_tokens"]
            if not isinstance(v, int) or isinstance(v, bool) or v <= 0 or v > 65536:
                return jsonify({
                    "success": False,
                    "error": "max_tokens must be a positive integer ≤ 65536",
                }), 400
        if "temperature" in override:
            v = override["temperature"]
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 or v > 2:
                return jsonify({
                    "success": False,
                    "error": "temperature must be a number between 0 and 2",
                }), 400
        for field in ("system_prompt", "user_message", "user_message_template"):
            if field in override and not isinstance(override[field], str):
                return jsonify({
                    "success": False,
                    "error": f"{field} must be a string",
                }), 400

        # Compute the effective config as it would be after this save,
        # then check that no required var has gone missing.
        merged = {**base_dict, **override}
        ok, missing, extra = validate_edit(base_dict, merged)
        if not ok:
            return jsonify({
                "success": False,
                "error": (
                    "Edit removes required template variables. "
                    "Re-insert them from the chip strip and try again."
                ),
                "missing_vars": missing,
                "extra_vars": extra,
            }), 400

        # If the override is empty (admin sent no fields, or sent a body
        # identical to base) it's effectively a reset — clear instead of
        # writing an empty file.
        if not override:
            prompt_loader.clear_override(prompt_name)
        else:
            ok = prompt_loader.write_override(prompt_name, override)
            if not ok:
                return jsonify({
                    "success": False,
                    "error": "Failed to write override file (check disk perms / logs)",
                }), 500

        return jsonify({
            "success": True,
            "prompt": _detail(prompt_name),
            "extra_vars": extra,  # surfaced as a yellow-warning toast in the UI
        }), 200
    except Exception as e:
        current_app.logger.error("Error updating prompt %s: %s", prompt_name, e)
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route('/settings/prompts/<prompt_name>/override', methods=['DELETE'])
@require_admin
def reset_prompt(prompt_name: str):
    """Drop the override file. Returns the now-effective (shipped) config."""
    try:
        if prompt_loader.get_prompt_default_config(prompt_name) is None:
            return jsonify({
                "success": False,
                "error": f"Unknown prompt: {prompt_name}",
            }), 404
        ok = prompt_loader.clear_override(prompt_name)
        if not ok:
            return jsonify({
                "success": False,
                "error": "Failed to delete override file",
            }), 500
        return jsonify({"success": True, "prompt": _detail(prompt_name)}), 200
    except Exception as e:
        current_app.logger.error("Error resetting prompt %s: %s", prompt_name, e)
        return jsonify({"success": False, "error": str(e)}), 500
