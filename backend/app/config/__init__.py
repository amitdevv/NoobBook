"""
Config - Configuration loaders and providers.

Educational Note: This folder contains services that load and provide
configuration data for other services. They handle:
- Tool definitions (JSON schemas for Claude tools)
- Prompt configurations (system prompts, model settings)
- API tier settings (rate limits, worker counts)
- Context building (sources, memory for chat prompts)
- Brand context building (colors, typography, guidelines for studio prompts)

These are NOT AI-powered services - they load configuration from files
and environment variables.

Loaders:
- tool_loader: Load tool definitions from JSON files
- prompt_loader: Load/save prompt configurations
- tier_loader: API tier rate limit settings
- context_loader: Build source and memory context for chat prompts
- brand_context_loader: Build brand context for studio prompts
"""
from app.config.tool_loader import tool_loader
from app.config.prompt_loader import prompt_loader
from app.config.context_loader import context_loader
from app.config.brand_context_loader import brand_context_loader, load_brand_context
from app.config.tier_loader import (
    get_tier,
    get_tier_config,
    get_all_tiers,
    get_max_workers,
    get_anthropic_config,
    get_openai_config,
    get_pinecone_config,
    APIProvider,
    ANTHROPIC_TIERS,
    OPENAI_TIERS,
    PINECONE_TIERS,
)

__all__ = [
    "tool_loader",
    "prompt_loader",
    "context_loader",
    "brand_context_loader",
    "load_brand_context",
    "get_tier",
    "get_tier_config",
    "get_all_tiers",
    "get_max_workers",
    "get_anthropic_config",
    "get_openai_config",
    "get_pinecone_config",
    "APIProvider",
    "ANTHROPIC_TIERS",
    "OPENAI_TIERS",
    "PINECONE_TIERS",
]
