-- MCP Connections (Account-level)
-- Stores MCP server connection config for importing external data as sources.

CREATE TABLE IF NOT EXISTS mcp_connections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  server_url TEXT NOT NULL,
  transport TEXT NOT NULL DEFAULT 'sse',
  auth_type TEXT NOT NULL DEFAULT 'none',
  auth_config JSONB DEFAULT '{}'::jsonb,
  is_active BOOLEAN DEFAULT true,
  visible_to_all BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT valid_transport CHECK (transport IN ('sse')),
  CONSTRAINT valid_auth_type CHECK (auth_type IN ('none', 'bearer', 'api_key', 'header')),
  CONSTRAINT mcp_name_not_empty CHECK (length(trim(name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_mcp_connections_owner_user_id ON mcp_connections(owner_user_id);

-- Users allowed to use an MCP connection (for multi-user mode)
CREATE TABLE IF NOT EXISTS mcp_connection_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id UUID NOT NULL REFERENCES mcp_connections(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(connection_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_mcp_connection_users_connection_id ON mcp_connection_users(connection_id);
CREATE INDEX IF NOT EXISTS idx_mcp_connection_users_user_id ON mcp_connection_users(user_id);

-- Auto-update updated_at
DROP TRIGGER IF EXISTS update_mcp_connections_updated_at ON mcp_connections;
CREATE TRIGGER update_mcp_connections_updated_at BEFORE UPDATE ON mcp_connections
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
