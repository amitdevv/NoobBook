-- Notion source type
--
-- The original initial_schema constraint only listed the file-based source
-- types (PDF/DOCX/.../RESEARCH). Subsequent integration sources (DATABASE,
-- FRESHDESK, JIRA, MIXPANEL, MCP, DATA/CSV) have been added in code without
-- a constraint update — at this point the constraint is either out-of-sync
-- or already dropped on production. Drop and re-create with the full set so
-- the schema actually matches the application contract going forward.

ALTER TABLE sources DROP CONSTRAINT IF EXISTS valid_type;

ALTER TABLE sources ADD CONSTRAINT valid_type CHECK (
  type IN (
    -- File-based document sources
    'PDF', 'DOCX', 'PPTX', 'IMAGE', 'AUDIO', 'TEXT',
    -- Tabular data sources
    'CSV', 'DATA',
    -- Web sources
    'LINK', 'YOUTUBE',
    -- AI-generated sources
    'RESEARCH',
    -- Integration / live-API sources
    'DATABASE', 'FRESHDESK', 'JIRA', 'MIXPANEL', 'MCP',
    -- Notion (this migration)
    'NOTION'
  )
);

COMMENT ON COLUMN sources.type IS
  'Source type. File: PDF, DOCX, PPTX, IMAGE, AUDIO, TEXT, CSV, DATA. '
  'Web: LINK, YOUTUBE. AI: RESEARCH. Integrations: DATABASE, FRESHDESK, '
  'JIRA, MIXPANEL, MCP, NOTION.';
