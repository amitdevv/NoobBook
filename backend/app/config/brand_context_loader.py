"""
Brand Context Loader - Builds brand context for studio agent prompts.

Educational Note: This module creates formatted brand guidelines context
that can be injected into studio agent system prompts. The context includes:

1. Color Palette - Primary, secondary, accent, and custom colors
2. Typography - Font families and sizing information
3. Brand Guidelines - Written guidelines and best practices
4. Brand Voice - Tone, personality, and keywords

The context is only loaded when the feature has brand enabled.
"""
from typing import Dict, Any, Optional

from app.services.data_services.brand_config_service import brand_config_service
from app.services.data_services.brand_asset_service import brand_asset_service


class BrandContextLoader:
    """
    Loader for building brand context for studio agent prompts.

    Educational Note: This loader is called by studio services before
    content generation. It checks if brand is enabled for the feature
    and builds formatted context for the AI to follow.
    """

    def load_brand_context(
        self,
        project_id: str,
        feature_name: str
    ) -> str:
        """
        Load brand context for injection into a studio agent prompt.

        Educational Note: This method first checks if the feature has
        brand enabled. If not, it returns an empty string. This allows
        features like mind maps to skip brand application while
        presentations and blogs follow brand guidelines.

        Args:
            project_id: The project UUID
            feature_name: The studio feature name (e.g., 'blog', 'presentation')

        Returns:
            Formatted brand context string, or empty string if brand disabled
        """
        # Check if brand is enabled for this feature
        if not brand_config_service.is_feature_enabled(project_id, feature_name):
            return ""

        # Get brand config
        config = brand_config_service.get_config(project_id)

        # Build context sections
        sections = []

        sections.append("## Brand Guidelines")
        sections.append("")

        # Add color palette
        color_context = self._build_color_context(config)
        if color_context:
            sections.append(color_context)

        # Add typography
        typography_context = self._build_typography_context(config)
        if typography_context:
            sections.append(typography_context)

        # Add brand assets info
        assets_context = self._build_assets_context(project_id)
        if assets_context:
            sections.append(assets_context)

        # Add brand voice
        voice_context = self._build_voice_context(config)
        if voice_context:
            sections.append(voice_context)

        # Add guidelines text
        guidelines_context = self._build_guidelines_context(config)
        if guidelines_context:
            sections.append(guidelines_context)

        # Add best practices
        practices_context = self._build_practices_context(config)
        if practices_context:
            sections.append(practices_context)

        if len(sections) <= 2:  # Only header and empty line
            return ""

        sections.append("Please ensure all generated content follows these brand guidelines.")
        sections.append("")

        return "\n".join(sections)

    def _build_color_context(self, config: Dict[str, Any]) -> str:
        """Build color palette context section."""
        colors = config.get("colors", {})

        if not colors:
            return ""

        lines = [
            "### Color Palette",
            "",
        ]

        # Standard colors
        if colors.get("primary"):
            lines.append(f"- **Primary Color**: {colors['primary']}")
        if colors.get("secondary"):
            lines.append(f"- **Secondary Color**: {colors['secondary']}")
        if colors.get("accent"):
            lines.append(f"- **Accent Color**: {colors['accent']}")
        if colors.get("background"):
            lines.append(f"- **Background Color**: {colors['background']}")
        if colors.get("text"):
            lines.append(f"- **Text Color**: {colors['text']}")

        # Custom colors
        custom_colors = colors.get("custom", [])
        if custom_colors:
            lines.append("")
            lines.append("**Custom Colors**:")
            for custom in custom_colors:
                name = custom.get("name", "Unnamed")
                value = custom.get("value", "#000000")
                lines.append(f"- {name}: {value}")

        lines.append("")
        return "\n".join(lines)

    def _build_typography_context(self, config: Dict[str, Any]) -> str:
        """Build typography context section."""
        typography = config.get("typography", {})

        if not typography:
            return ""

        lines = [
            "### Typography",
            "",
        ]

        if typography.get("heading_font"):
            lines.append(f"- **Heading Font**: {typography['heading_font']}")
        if typography.get("body_font"):
            lines.append(f"- **Body Font**: {typography['body_font']}")

        if typography.get("heading_weight"):
            lines.append(f"- **Heading Weight**: {typography['heading_weight']}")
        if typography.get("body_weight"):
            lines.append(f"- **Body Weight**: {typography['body_weight']}")

        heading_sizes = typography.get("heading_sizes", {})
        if heading_sizes:
            sizes = [f"H{i}={heading_sizes.get(f'h{i}', 'auto')}" for i in range(1, 7) if heading_sizes.get(f'h{i}')]
            lines.append(f"- **Heading Sizes**: {', '.join(sizes)}")

        if typography.get("body_size"):
            lines.append(f"- **Body Size**: {typography['body_size']}")
        if typography.get("line_height"):
            lines.append(f"- **Line Height**: {typography['line_height']}")

        lines.append("")
        return "\n".join(lines)

    def _build_assets_context(self, project_id: str) -> str:
        """Build brand assets context section."""
        assets = brand_asset_service.list_assets(project_id)

        if not assets:
            return ""

        # Group by type
        logos = [a for a in assets if a.get("asset_type") == "logo"]
        icons = [a for a in assets if a.get("asset_type") == "icon"]

        lines = [
            "### Brand Assets",
            "",
        ]

        # Primary logo
        primary_logo = next((a for a in logos if a.get("is_primary")), None)
        if primary_logo:
            lines.append(f"- **Primary Logo**: {primary_logo.get('name', 'Logo')}")
            if primary_logo.get("description"):
                lines.append(f"  - Description: {primary_logo['description']}")

        # Logo count
        if len(logos) > 1:
            lines.append(f"- **Additional Logos Available**: {len(logos) - 1}")

        # Icons
        if icons:
            lines.append(f"- **Icons Available**: {len(icons)}")

        lines.append("")
        return "\n".join(lines)

    def _build_voice_context(self, config: Dict[str, Any]) -> str:
        """Build brand voice context section."""
        voice = config.get("voice", {})

        if not voice:
            return ""

        lines = [
            "### Brand Voice",
            "",
        ]

        if voice.get("tone"):
            lines.append(f"- **Tone**: {voice['tone']}")

        personality = voice.get("personality", [])
        if personality:
            lines.append(f"- **Personality Traits**: {', '.join(personality)}")

        keywords = voice.get("keywords", [])
        if keywords:
            lines.append(f"- **Key Terms to Use**: {', '.join(keywords)}")

        lines.append("")
        return "\n".join(lines)

    def _build_guidelines_context(self, config: Dict[str, Any]) -> str:
        """Build written guidelines context section."""
        guidelines = config.get("guidelines")

        if not guidelines:
            return ""

        lines = [
            "### Written Guidelines",
            "",
            guidelines,
            "",
        ]

        return "\n".join(lines)

    def _build_practices_context(self, config: Dict[str, Any]) -> str:
        """Build best practices (dos/donts) context section."""
        practices = config.get("best_practices", {})

        dos = practices.get("dos", [])
        donts = practices.get("donts", [])

        if not dos and not donts:
            return ""

        lines = [
            "### Best Practices",
            "",
        ]

        if dos:
            lines.append("**Do**:")
            for item in dos:
                lines.append(f"- {item}")
            lines.append("")

        if donts:
            lines.append("**Don't**:")
            for item in donts:
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines)

    def get_brand_summary(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of brand configuration for display purposes.

        Educational Note: This is useful for showing a brand preview in the UI
        without loading the full context.

        Args:
            project_id: The project UUID

        Returns:
            Summary dict with key brand elements, or None if no config
        """
        config = brand_config_service.get_config(project_id)
        assets = brand_asset_service.list_assets(project_id)

        # Get primary logo
        primary_logo = next(
            (a for a in assets if a.get("asset_type") == "logo" and a.get("is_primary")),
            None
        )

        colors = config.get("colors", {})
        typography = config.get("typography", {})
        voice = config.get("voice", {})

        return {
            "primary_color": colors.get("primary"),
            "secondary_color": colors.get("secondary"),
            "accent_color": colors.get("accent"),
            "heading_font": typography.get("heading_font"),
            "body_font": typography.get("body_font"),
            "tone": voice.get("tone"),
            "primary_logo_name": primary_logo.get("name") if primary_logo else None,
            "has_guidelines": bool(config.get("guidelines")),
            "asset_count": len(assets),
            "feature_settings": config.get("feature_settings", {})
        }


# Singleton instance
brand_context_loader = BrandContextLoader()


def load_brand_context(project_id: str, feature_name: str) -> str:
    """
    Convenience function for loading brand context.

    Args:
        project_id: The project UUID
        feature_name: The studio feature name

    Returns:
        Formatted brand context string
    """
    return brand_context_loader.load_brand_context(project_id, feature_name)
