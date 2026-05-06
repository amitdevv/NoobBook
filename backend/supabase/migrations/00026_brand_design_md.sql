-- Migration: Add design.md spec field to brand_config
-- Description: Long-form markdown design specification (google-labs-code/design.md
-- format) injected into studio agent system prompts alongside the existing
-- structured brand-kit. NULL means "use the bundled sample" — empty string means
-- "admin explicitly cleared it, send nothing".
-- Created: 2026-05-06

ALTER TABLE brand_config ADD COLUMN IF NOT EXISTS design_md TEXT;

COMMENT ON COLUMN brand_config.design_md IS 'Long-form design.md spec (markdown). Injected into 7 brand-aware studio agents via brand_context_loader. NULL = use bundled sample.';
