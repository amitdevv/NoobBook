"""
Brand Config Service - Business logic for brand configuration management.

Educational Note: Brand configuration stores colors, typography, guidelines,
and voice settings for a project. This is used by studio agents to maintain
consistent branding across generated content.

The config is created on first access with sensible defaults and can be
updated incrementally (e.g., update just colors without touching typography).
"""
from typing import Optional, Dict, Any

from app.services.integrations.supabase import get_supabase, is_supabase_enabled


# Default brand configuration values
DEFAULT_COLORS = {
    "primary": "#000000",
    "secondary": "#666666",
    "accent": "#0066CC",
    "background": "#FFFFFF",
    "text": "#1A1A1A",
    "custom": []
}

DEFAULT_TYPOGRAPHY = {
    "heading_font": "Inter",
    "body_font": "Inter",
    "heading_sizes": {"h1": "2.5rem", "h2": "2rem", "h3": "1.5rem"},
    "body_size": "1rem",
    "line_height": "1.6"
}

DEFAULT_SPACING = {
    "base": "1rem",
    "small": "0.5rem",
    "large": "2rem",
    "section": "4rem"
}

DEFAULT_BEST_PRACTICES = {
    "dos": [],
    "donts": []
}

DEFAULT_VOICE = {
    "tone": "professional",
    "personality": [],
    "keywords": []
}

DEFAULT_FEATURE_SETTINGS = {
    "infographic": True,
    "presentation": True,
    "mind_map": False,
    "blog": True,
    "email": True,
    "ads_creative": True,
    "social_post": True,
    "prd": False,
    "business_report": True
}


class BrandConfigService:
    """
    Service class for managing brand configuration using Supabase.

    Educational Note: Unlike brand assets which can have multiple per project,
    each project has exactly one brand config. The config is created automatically
    on first access with defaults.
    """

    def __init__(self):
        """Initialize the brand config service."""
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_ANON_KEY to your .env file."
            )
        self.supabase = get_supabase()
        self.table = "brand_config"

    def get_config(self, project_id: str) -> Dict[str, Any]:
        """
        Get the brand configuration for a project.

        Educational Note: Creates default config if none exists. This ensures
        there's always a valid config to work with.

        Args:
            project_id: The project UUID

        Returns:
            Brand configuration object
        """
        response = (
            self.supabase.table(self.table)
            .select("*")
            .eq("project_id", project_id)
            .execute()
        )

        if response.data:
            return response.data[0]

        # Create default config if none exists
        return self._create_default_config(project_id)

    def update_config(
        self,
        project_id: str,
        colors: Optional[Dict[str, Any]] = None,
        typography: Optional[Dict[str, Any]] = None,
        spacing: Optional[Dict[str, Any]] = None,
        guidelines: Optional[str] = None,
        best_practices: Optional[Dict[str, Any]] = None,
        voice: Optional[Dict[str, Any]] = None,
        feature_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update the brand configuration for a project.

        Educational Note: Only updates the fields that are provided.
        This allows partial updates (e.g., just update colors).

        Args:
            project_id: The project UUID
            colors: Color palette settings
            typography: Typography settings
            spacing: Spacing configuration
            guidelines: Brand guidelines text
            best_practices: Dos and don'ts
            voice: Brand voice settings
            feature_settings: Per-feature brand toggles

        Returns:
            Updated brand configuration
        """
        # Ensure config exists
        self.get_config(project_id)

        # Build update data (only include non-None values)
        update_data = {}
        if colors is not None:
            update_data["colors"] = colors
        if typography is not None:
            update_data["typography"] = typography
        if spacing is not None:
            update_data["spacing"] = spacing
        if guidelines is not None:
            update_data["guidelines"] = guidelines
        if best_practices is not None:
            update_data["best_practices"] = best_practices
        if voice is not None:
            update_data["voice"] = voice
        if feature_settings is not None:
            update_data["feature_settings"] = feature_settings

        if not update_data:
            # No updates, return existing config
            return self.get_config(project_id)

        # Update the config
        response = (
            self.supabase.table(self.table)
            .update(update_data)
            .eq("project_id", project_id)
            .execute()
        )

        if response.data:
            print(f"Updated brand config for project: {project_id}")
            return response.data[0]

        return self.get_config(project_id)

    def update_colors(
        self,
        project_id: str,
        colors: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update just the color palette.

        Args:
            project_id: The project UUID
            colors: New color palette

        Returns:
            Updated brand configuration
        """
        return self.update_config(project_id, colors=colors)

    def update_typography(
        self,
        project_id: str,
        typography: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update just the typography settings.

        Args:
            project_id: The project UUID
            typography: New typography settings

        Returns:
            Updated brand configuration
        """
        return self.update_config(project_id, typography=typography)

    def update_guidelines(
        self,
        project_id: str,
        guidelines: str
    ) -> Dict[str, Any]:
        """
        Update just the brand guidelines text.

        Args:
            project_id: The project UUID
            guidelines: New guidelines text (markdown supported)

        Returns:
            Updated brand configuration
        """
        return self.update_config(project_id, guidelines=guidelines)

    def update_best_practices(
        self,
        project_id: str,
        best_practices: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update just the best practices (dos/donts).

        Args:
            project_id: The project UUID
            best_practices: Object with 'dos' and 'donts' arrays

        Returns:
            Updated brand configuration
        """
        return self.update_config(project_id, best_practices=best_practices)

    def update_voice(
        self,
        project_id: str,
        voice: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update just the brand voice settings.

        Args:
            project_id: The project UUID
            voice: Object with tone, personality, keywords

        Returns:
            Updated brand configuration
        """
        return self.update_config(project_id, voice=voice)

    def update_feature_settings(
        self,
        project_id: str,
        feature_settings: Dict[str, bool]
    ) -> Dict[str, Any]:
        """
        Update per-feature brand application settings.

        Educational Note: This controls which studio features should apply
        the brand configuration. For example, mind maps might not need
        brand colors but presentations do.

        Args:
            project_id: The project UUID
            feature_settings: Dict mapping feature names to booleans

        Returns:
            Updated brand configuration
        """
        return self.update_config(project_id, feature_settings=feature_settings)

    def is_feature_enabled(
        self,
        project_id: str,
        feature_name: str
    ) -> bool:
        """
        Check if brand should be applied for a specific feature.

        Args:
            project_id: The project UUID
            feature_name: The studio feature name (e.g., 'blog', 'presentation')

        Returns:
            True if brand should be applied for this feature
        """
        config = self.get_config(project_id)
        feature_settings = config.get("feature_settings", DEFAULT_FEATURE_SETTINGS)
        return feature_settings.get(feature_name, False)

    def delete_config(self, project_id: str) -> bool:
        """
        Delete the brand configuration for a project.

        Educational Note: This is typically called when a project is deleted
        (via cascade) but can also be used to reset to defaults by deleting
        and then getting the config again.

        Args:
            project_id: The project UUID

        Returns:
            True if deleted, False if not found
        """
        response = (
            self.supabase.table(self.table)
            .delete()
            .eq("project_id", project_id)
            .execute()
        )

        # Check if any rows were deleted
        return bool(response.data)

    def _create_default_config(self, project_id: str) -> Dict[str, Any]:
        """
        Create a default brand configuration for a project.

        Args:
            project_id: The project UUID

        Returns:
            Newly created brand configuration
        """
        config_data = {
            "project_id": project_id,
            "colors": DEFAULT_COLORS,
            "typography": DEFAULT_TYPOGRAPHY,
            "spacing": DEFAULT_SPACING,
            "guidelines": None,
            "best_practices": DEFAULT_BEST_PRACTICES,
            "voice": DEFAULT_VOICE,
            "feature_settings": DEFAULT_FEATURE_SETTINGS
        }

        response = (
            self.supabase.table(self.table)
            .insert(config_data)
            .execute()
        )

        if response.data:
            print(f"Created default brand config for project: {project_id}")
            return response.data[0]

        raise RuntimeError("Failed to create default brand config")


# Singleton instance
brand_config_service = BrandConfigService()
