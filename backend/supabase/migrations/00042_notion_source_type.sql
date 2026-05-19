-- Notion source type
--
-- The original initial_schema constraint only listed the file-based source
-- types (PDF/DOCX/.../RESEARCH). Subsequent integration sources (DATABASE,
-- FRESHDESK, JIRA, MIXPANEL, MCP, DATA/CSV) have been added in code without
-- a constraint update — at this point the constraint is either out-of-sync
-- or already dropped on production. Drop and re-create with the full set so
-- the schema actually matches the application contract going forward.
--
-- NOTE: file uploads (`file_upload.py`) write `type = category.upper()`
-- where category comes from ALLOWED_EXTENSIONS in file_utils.py. The
-- categories are 'document', 'audio', 'image', 'data', 'link' — so PDF /
-- DOCX / PPTX / TXT / MD / JSON / HTML / XML all hit production with
-- `type = 'DOCUMENT'`. AI-extraction labels like 'PDF' / 'DOCX' / 'PPTX'
-- only appear in processed-file headers, not in sources.type. The
-- constraint MUST include 'DOCUMENT' or it will reject every PDF upload
-- ever made. Keeping the AI labels in the list too is harmless and means
-- future code paths can use either convention without breakage.

ALTER TABLE sources DROP CONSTRAINT IF EXISTS valid_type;

ALTER TABLE sources ADD CONSTRAINT valid_type CHECK (
  type IN (
    -- File uploads write category.upper() — this is what most prod rows are
    'DOCUMENT', 'IMAGE', 'AUDIO', 'DATA', 'LINK',
    -- AI-extraction labels (used by processed-file headers; tolerated in the
    -- sources.type column as well so the two never have to be reconciled)
    'PDF', 'DOCX', 'PPTX', 'TEXT', 'CSV',
    -- Web sources
    'YOUTUBE',
    -- AI-generated sources
    'RESEARCH',
    -- Integration / live-API sources
    'DATABASE', 'FRESHDESK', 'JIRA', 'MIXPANEL', 'MCP',
    -- Notion (this migration)
    'NOTION'
  )
);

COMMENT ON COLUMN sources.type IS
  'Source type. File uploads: DOCUMENT, IMAGE, AUDIO, DATA, LINK '
  '(category.upper() from file_utils.ALLOWED_EXTENSIONS). '
  'AI-extraction labels: PDF, DOCX, PPTX, TEXT, CSV. Web: YOUTUBE. '
  'AI-generated: RESEARCH. Integrations: DATABASE, FRESHDESK, JIRA, '
  'MIXPANEL, MCP, NOTION.';
