-- MCP: Add stdio transport support and tools caching
-- Enables MCP servers that run as subprocesses (e.g., uvx freshdesk-mcp)
-- and caches discovered tool definitions for chat integration.

-- Allow stdio transport in addition to sse
ALTER TABLE mcp_connections DROP CONSTRAINT IF EXISTS valid_transport;
ALTER TABLE mcp_connections ADD CONSTRAINT valid_transport CHECK (transport IN ('sse', 'stdio'));

-- Make server_url nullable (stdio connections don't have a URL)
ALTER TABLE mcp_connections ALTER COLUMN server_url DROP NOT NULL;

-- Stdio config: command, args, env vars for subprocess-based MCP servers
ALTER TABLE mcp_connections ADD COLUMN IF NOT EXISTS stdio_config JSONB DEFAULT '{}'::jsonb;

-- Whether this connection's tools should be injected into chat
ALTER TABLE mcp_connections ADD COLUMN IF NOT EXISTS tools_enabled BOOLEAN DEFAULT false;

-- Cache of discovered tool definitions (refreshed on demand)
ALTER TABLE mcp_connections ADD COLUMN IF NOT EXISTS cached_tools JSONB DEFAULT NULL;

-- When tools were last cached
ALTER TABLE mcp_connections ADD COLUMN IF NOT EXISTS tools_cached_at TIMESTAMPTZ DEFAULT NULL;
