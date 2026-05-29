"""
Prompt Config - Manages system prompts for AI interactions.

This module handles loading, storing, and retrieving
prompts used in AI conversations. Projects can have custom prompts or
fall back to the global default.

Prompt Config Structure (consistent across all prompt files):
{
    "version": "2.0",
    "name": "prompt_name",
    "description": "What this prompt is for",
    "model": "claude-sonnet-4-6",
    "max_tokens": 4096,
    "temperature": 0.7,
    "system_prompt": "The actual prompt text...",
    "created_at": "...",
    "updated_at": "..."
}

Prompt Hierarchy:
1. Project custom prompt (if set)
2. Global default prompt (fallback)
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from config import Config

logger = logging.getLogger(__name__)


class PromptConfig(dict):
    """
    Dict subclass whose "model" key is resolved dynamically on every access.

    Services in this codebase often cache the result of
    prompt_loader.get_prompt_config(...) in self._prompt_config and reuse it
    for the lifetime of the process. If we mutated config["model"] once at
    load time, an admin changing the model override later would not take
    effect until restart.

    By overriding __getitem__ and get for the "model" key, every lookup re-reads
    the env-var-backed override. Services can keep caching the PromptConfig
    instance (everything else is static) while still picking up admin changes
    immediately.
    """

    def __init__(self, data: Dict[str, Any], prompt_name: Optional[str] = None):
        super().__init__(data)
        # Use object.__setattr__ to bypass dict semantics
        object.__setattr__(self, "_prompt_name", prompt_name)

    def _resolved_model(self) -> Optional[Any]:
        # Lazy import to avoid circular dependency at module load time
        from app.config.model_loader import get_model_override_for_prompt

        prompt_name = object.__getattribute__(self, "_prompt_name")
        if not prompt_name:
            return None
        return get_model_override_for_prompt(prompt_name)

    def __getitem__(self, key):
        if key == "model":
            override = self._resolved_model()
            if override:
                return override
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == "model":
            override = self._resolved_model()
            if override:
                return override
        return super().get(key, default)

    def raw_model(self) -> Optional[str]:
        """
        Return the JSON-baked model, bypassing any admin override.

        Used by the settings UI to show what "Default" actually resolves to
        for each prompt — so admins can see whether selecting Default keeps
        Sonnet, Opus, Haiku, or a mix.
        """
        return super().get("model")


class PromptLoader:
    """
    Loader class for managing system prompts.

    Prompts define how the AI behaves. Different projects
    might need different prompts based on their use case (research, coding,
    learning, etc.).
    """

    def __init__(self):
        """Initialize the prompt service."""
        self.prompts_dir = Config.DATA_DIR / "prompts"
        self.projects_dir = Config.PROJECTS_DIR
        # Sibling of prompts_dir. Persisted via the same `backend-data`
        # Docker volume but **not** clobbered by entrypoint.sh's
        # `cp /app/_prompts_staging/* data/prompts/`. Admin edits land
        # here so they survive container redeploys.
        self.overrides_dir = Config.DATA_DIR / "prompt_overrides"

        # Ensure both directories exist
        self.prompts_dir.mkdir(exist_ok=True, parents=True)
        self.overrides_dir.mkdir(exist_ok=True, parents=True)

    # ────────────────────────────────────────────────────────────────
    # Override resolution helpers (Roadmap #16 — admin-editable prompts).
    # Overrides live alongside the shipped defaults but in a sibling
    # directory that the container entrypoint doesn't clobber. The
    # resolver merges {**base, **override} so an override file only
    # needs the fields the admin actually changed.
    # ────────────────────────────────────────────────────────────────

    def _override_path(self, prompt_name: str) -> Path:
        return self.overrides_dir / f"{prompt_name}_prompt.json"

    def _load_override(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """Read the override file for ``prompt_name``, or return ``None``."""
        path = self._override_path(prompt_name)
        if not path.exists():
            return None
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("Override %s is not a JSON object — ignoring", path)
                return None
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to read override %s: %s", path, e)
            return None

    def has_override(self, prompt_name: str) -> bool:
        """True iff an admin override file exists for this prompt."""
        return self._override_path(prompt_name).exists()

    def write_override(self, prompt_name: str, override: Dict[str, Any]) -> bool:
        """
        Persist an admin override. Caller is responsible for validation
        (see ``prompt_var_utils.validate_edit``) — this just writes to disk.
        """
        path = self._override_path(prompt_name)
        try:
            with open(path, 'w') as f:
                json.dump(override, f, indent=2)
            return True
        except IOError as e:
            logger.error("Failed to write override %s: %s", path, e)
            return False

    def clear_override(self, prompt_name: str) -> bool:
        """Delete the override file. Returns False only on a real I/O error."""
        path = self._override_path(prompt_name)
        if not path.exists():
            return True
        try:
            path.unlink()
            return True
        except IOError as e:
            logger.error("Failed to delete override %s: %s", path, e)
            return False

    def _load_base(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """Load the shipped default for ``prompt_name``, no merge."""
        prompt_file = self.prompts_dir / f"{prompt_name}_prompt.json"
        try:
            with open(prompt_file, 'r') as f:
                data = json.load(f)
            # Legacy format compat
            if "prompt" in data and "system_prompt" not in data:
                data["system_prompt"] = data.pop("prompt")
            return data
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def get_prompt_default_config(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """
        Return the shipped default for a prompt, ignoring any admin override.

        Used by the Admin Settings → Prompts editor to show a "compare to
        default" diff and to compute the canonical required-variable list.
        """
        base = self._load_base(prompt_name)
        if base is None:
            return None
        return PromptConfig(base, prompt_name=prompt_name)

    def get_default_prompt_config(self) -> Dict[str, Any]:
        """
        Load the full default prompt configuration.

        Returns the complete prompt config including
        model, max_tokens, temperature, and system_prompt. Resolves
        admin overrides — same path ``get_prompt_config`` uses.

        Returns:
            Dict with all prompt config fields
        """
        config = self.get_prompt_config("default")
        if config is None:
            # Should never happen — default_prompt.json ships with the repo
            # — but if it ever does, fail loudly rather than returning None
            # silently and breaking every chat downstream.
            raise FileNotFoundError(
                "default_prompt.json missing from prompts directory"
            )
        return config

    def get_default_prompt(self) -> str:
        """
        Load the global default system prompt text.

        This is used when projects don't have custom prompts.
        It provides a baseline behavior for the AI assistant.

        Returns:
            The default system prompt text
        """
        config = self.get_default_prompt_config()
        return config.get("system_prompt", "")

    def get_project_prompt(self, project_id: str) -> str:
        """
        Get the prompt for a specific project.

        First checks for a custom prompt in project settings,
        then falls back to the global default.

        Args:
            project_id: The project UUID

        Returns:
            The project's system prompt (custom or default)
        """
        project_file = self.projects_dir / f"{project_id}.json"

        try:
            with open(project_file, 'r') as f:
                project_data = json.load(f)
                custom_prompt = project_data.get("settings", {}).get("custom_prompt")

                if custom_prompt:
                    return custom_prompt
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # Return default if no custom prompt
        return self.get_default_prompt()

    def get_project_prompt_config(self, project_id: str) -> Dict[str, Any]:
        """
        Get the full prompt config for a specific project.

        Returns the default config but with custom prompt
        if the project has one. This ensures model/max_tokens/temperature
        come from the default config even when using custom prompts.

        Args:
            project_id: The project UUID

        Returns:
            Dict with all prompt config fields
        """
        config = self.get_default_prompt_config()

        # Check for custom prompt override
        project_file = self.projects_dir / f"{project_id}.json"

        try:
            with open(project_file, 'r') as f:
                project_data = json.load(f)
                custom_prompt = project_data.get("settings", {}).get("custom_prompt")

                if custom_prompt:
                    config["system_prompt"] = custom_prompt
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # get_default_prompt_config already returns a PromptConfig tagged with
        # prompt_name="default" so the admin "chat" category override applies.
        return config

    def update_project_prompt(self, project_id: str, prompt: Optional[str]) -> bool:
        """
        Update a project's custom prompt.

        Setting prompt to None removes the custom prompt
        and reverts to the default.

        Args:
            project_id: The project UUID
            prompt: New custom prompt, or None to reset to default

        Returns:
            True if successful, False if project not found
        """
        project_file = self.projects_dir / f"{project_id}.json"

        if not project_file.exists():
            return False

        try:
            with open(project_file, 'r') as f:
                project_data = json.load(f)

            # Ensure settings dict exists
            if "settings" not in project_data:
                project_data["settings"] = {}

            # Update or remove custom prompt
            if prompt:
                project_data["settings"]["custom_prompt"] = prompt
            else:
                # Remove custom prompt to use default
                project_data["settings"].pop("custom_prompt", None)

            # Save updated project
            with open(project_file, 'w') as f:
                json.dump(project_data, f, indent=2)

            return True

        except (json.JSONDecodeError, IOError):
            return False

    def save_default_prompt(self, prompt: str) -> bool:
        """
        Update the global default prompt.

        This affects all projects that don't have
        custom prompts. Use with caution.

        Args:
            prompt: New default prompt text

        Returns:
            True if successful
        """
        default_prompt_file = self.prompts_dir / "default_prompt.json"

        try:
            prompt_data = {"prompt": prompt}
            with open(default_prompt_file, 'w') as f:
                json.dump(prompt_data, f, indent=2)
            return True
        except IOError:
            return False

    def get_agent_prompt(self, agent_name: str) -> Optional[str]:
        """
        Load a prompt for a specific agent.

        Agents (like web_agent, pdf_agent, etc.) have
        their own specialized prompts stored in data/prompts/{agent_name}_prompt.json

        Args:
            agent_name: Name of the agent (e.g., "web_agent")

        Returns:
            The agent's system prompt, or None if not found
        """
        prompt_file = self.prompts_dir / f"{agent_name}_prompt.json"

        try:
            with open(prompt_file, 'r') as f:
                prompt_data = json.load(f)
                # Look for system_prompt first (new format), then prompt (legacy)
                return prompt_data.get("system_prompt") or prompt_data.get("prompt")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def get_prompt_config(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """
        Load full prompt configuration by name, with admin override merged.

        Resolution order:
          1. ``data/prompts/<name>_prompt.json``  (shipped default)
          2. ``data/prompt_overrides/<name>_prompt.json`` (admin override,
             merged on top — only fields the admin edited need to be
             present in the override file)

        Returns:
            Full prompt config dict, or None if neither file exists.
        """
        base = self._load_base(prompt_name)
        if base is None:
            return None
        override = self._load_override(prompt_name) or {}
        merged = {**base, **override}
        return PromptConfig(merged, prompt_name=prompt_name)

    def list_all_prompts(self) -> list[Dict[str, Any]]:
        """
        List all prompt configurations from the prompts directory.

        Each entry is the *effective* config (base merged with any admin
        override) plus a ``has_override`` boolean and a ``prompt_name``
        suitable for the admin editor URL.

        Returns:
            List of prompt config dicts with all fields
        """
        prompts = []

        # Get all prompt JSON files
        prompt_files = sorted(self.prompts_dir.glob("*_prompt.json"))

        for prompt_file in prompt_files:
            try:
                with open(prompt_file, 'r') as f:
                    base_data = json.load(f)

                    # Handle legacy format where "prompt" was used instead of "system_prompt"
                    if "prompt" in base_data and "system_prompt" not in base_data:
                        base_data["system_prompt"] = base_data.pop("prompt")

                    # `prompt_name` is the filename stripped of "_prompt.json"
                    # — this is what every other API in this module uses
                    # as the lookup key.
                    prompt_name = prompt_file.stem
                    if prompt_name.endswith("_prompt"):
                        prompt_name = prompt_name[: -len("_prompt")]

                    override = self._load_override(prompt_name) or {}
                    effective = {**base_data, **override}

                    effective["filename"] = prompt_file.name
                    effective["prompt_name"] = prompt_name
                    effective["has_override"] = bool(override)

                    prompts.append(effective)
            except (json.JSONDecodeError, IOError) as e:
                logger.error("Failed to load prompt %s: %s", prompt_file, e)
                continue

        return prompts


# Singleton instance for easy import
prompt_loader = PromptLoader()
