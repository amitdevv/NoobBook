-- Per-chat source selection
-- Stores which sources are selected for each chat (NULL = new chat, no sources selected)
ALTER TABLE chats ADD COLUMN selected_source_ids UUID[] DEFAULT NULL;
