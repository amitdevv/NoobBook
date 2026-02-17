-- Per-chat source selection
-- NULL = legacy chat (backwards-compat: falls back to all ready+active sources)
-- Empty array = explicitly no sources selected (new chat default)
-- Non-empty array = specific sources selected for this chat
ALTER TABLE chats ADD COLUMN selected_source_ids UUID[] DEFAULT NULL;
