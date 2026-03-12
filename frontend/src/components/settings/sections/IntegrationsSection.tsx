/**
 * IntegrationsSection Component
 * Manages Google Drive and Database connections.
 */

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Eye,
  EyeSlash,
  Trash,
  CircleNotch,
  GoogleDriveLogo,
  SignOut,
  ArrowSquareOut,
  Warning,
} from '@phosphor-icons/react';
import { googleDriveAPI, databasesAPI, mcpAPI } from '@/lib/api/settings';
import type { GoogleStatus, DatabaseConnection, DatabaseType, McpConnection, McpAuthType, McpTransport } from '@/lib/api/settings';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('integrations-section');

interface IntegrationsSectionProps {
  isAdmin?: boolean;
}

export const IntegrationsSection: React.FC<IntegrationsSectionProps> = ({ isAdmin = false }) => {
  // Google Drive State
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus>({
    configured: false,
    connected: false,
    email: null,
  });
  const [googleLoading, setGoogleLoading] = useState(false);

  // Database State
  const [dbConnections, setDbConnections] = useState<DatabaseConnection[]>([]);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbCreating, setDbCreating] = useState(false);
  const [dbValidating, setDbValidating] = useState(false);
  const [showDbUri, setShowDbUri] = useState(false);
  const [dbValidation, setDbValidation] = useState<{ valid?: boolean; message?: string }>({});
  const [dbForm, setDbForm] = useState<{
    name: string;
    db_type: DatabaseType;
    connection_uri: string;
    description: string;
  }>({
    name: '',
    db_type: 'postgresql',
    connection_uri: '',
    description: '',
  });

  // MCP State
  const [mcpConnections, setMcpConnections] = useState<McpConnection[]>([]);
  const [mcpLoading, setMcpLoading] = useState(false);
  const [mcpCreating, setMcpCreating] = useState(false);
  const [mcpValidating, setMcpValidating] = useState(false);
  const [showMcpToken, setShowMcpToken] = useState(false);
  const [mcpValidation, setMcpValidation] = useState<{ valid?: boolean; message?: string }>({});
  const [mcpForm, setMcpForm] = useState<{
    name: string;
    transport: McpTransport;
    server_url: string;
    auth_type: McpAuthType;
    auth_token: string;
    stdio_command: string;
    stdio_args: string;
    stdio_env: string;
    description: string;
    tools_enabled: boolean;
  }>({
    name: '',
    transport: 'stdio',
    server_url: '',
    auth_type: 'none',
    auth_token: '',
    stdio_command: '',
    stdio_args: '',
    stdio_env: '',
    description: '',
    tools_enabled: true,
  });

  // Confirmation dialog state
  const [deleteDbId, setDeleteDbId] = useState<string | null>(null);
  const [deleteMcpId, setDeleteMcpId] = useState<string | null>(null);
  const [disconnectGoogleOpen, setDisconnectGoogleOpen] = useState(false);

  const { success, error, info } = useToast();

  useEffect(() => {
    loadGoogleStatus();
    loadDatabases();
    loadMcpConnections();
  }, []);

  const loadGoogleStatus = async () => {
    try {
      const status = await googleDriveAPI.getStatus();
      setGoogleStatus(status);
    } catch (err) {
      log.error({ err }, 'failed to load Google status');
    }
  };

  const handleGoogleConnect = async () => {
    setGoogleLoading(true);
    try {
      const authUrl = await googleDriveAPI.getAuthUrl();
      if (authUrl) {
        window.open(authUrl, '_blank', 'width=500,height=600');
        info('Complete authentication in the new window');
        const pollInterval = setInterval(async () => {
          const status = await googleDriveAPI.getStatus();
          if (status.connected) {
            clearInterval(pollInterval);
            setGoogleStatus(status);
            setGoogleLoading(false);
            success(`Connected as ${status.email}`);
          }
        }, 2000);
        setTimeout(() => {
          clearInterval(pollInterval);
          setGoogleLoading(false);
        }, 120000);
      } else {
        error('Failed to get Google auth URL. Check your credentials.');
        setGoogleLoading(false);
      }
    } catch (err) {
      log.error({ err }, 'failed to Lconnecting GoogleE');
      error('Failed to connect Google Drive');
      setGoogleLoading(false);
    }
  };

  const handleGoogleDisconnect = async () => {
    setGoogleLoading(true);
    try {
      const disconnected = await googleDriveAPI.disconnect();
      if (disconnected) {
        setGoogleStatus({ configured: googleStatus.configured, connected: false, email: null });
        success('Google Drive disconnected');
      } else {
        error('Failed to disconnect Google Drive');
      }
    } catch (err) {
      log.error({ err }, 'failed to Ldisconnecting GoogleE');
      error('Failed to disconnect Google Drive');
    } finally {
      setGoogleLoading(false);
    }
  };

  const loadDatabases = async () => {
    setDbLoading(true);
    try {
      const dbs = await databasesAPI.listDatabases();
      setDbConnections(dbs);
    } catch (err) {
      log.error({ err }, 'failed to load databases');
    } finally {
      setDbLoading(false);
    }
  };

  const handleValidateDatabase = async () => {
    setDbValidating(true);
    try {
      const result = await databasesAPI.validateDatabase(dbForm.db_type, dbForm.connection_uri);
      setDbValidation(result);
      if (result.valid) {
        success(result.message || 'Connection successful');
      } else {
        error(result.message || 'Validation failed');
      }
    } finally {
      setDbValidating(false);
    }
  };

  const handleCreateDatabase = async () => {
    setDbCreating(true);
    try {
      await databasesAPI.createDatabase({
        name: dbForm.name.trim(),
        db_type: dbForm.db_type,
        connection_uri: dbForm.connection_uri.trim(),
        description: dbForm.description.trim() || undefined,
      });
      success('Database connection saved');
      setDbForm({ name: '', db_type: 'postgresql', connection_uri: '', description: '' });
      setDbValidation({});
      await loadDatabases();
    } catch (err) {
      log.error({ err }, 'failed to create database');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to save database connection');
    } finally {
      setDbCreating(false);
    }
  };

  const handleDeleteDatabase = async (connectionId: string) => {
    try {
      await databasesAPI.deleteDatabase(connectionId);
      success('Database connection deleted');
      await loadDatabases();
    } catch (err) {
      log.error({ err }, 'failed to delete database');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to delete database connection');
    }
  };

  // MCP Handlers
  const loadMcpConnections = async () => {
    setMcpLoading(true);
    try {
      const conns = await mcpAPI.listConnections();
      setMcpConnections(conns);
    } catch (err) {
      log.error({ err }, 'failed to load MCP connections');
      error('Failed to load MCP connections');
    } finally {
      setMcpLoading(false);
    }
  };

  const buildMcpAuthConfig = (): Record<string, string> => {
    const token = mcpForm.auth_token.trim();
    if (!token) return {};
    switch (mcpForm.auth_type) {
      case 'bearer': return { token };
      case 'api_key': return { key: token };
      case 'header': return { header_name: 'Authorization', header_value: token };
      default: return {};
    }
  };

  /**
   * Parse stdio env vars from a multiline string (KEY=VALUE format).
   * Educational Note: Users enter env vars like FRESHDESK_API_KEY=abc123,
   * one per line. We parse them into a key-value object for the API.
   */
  const parseStdioEnv = (): Record<string, string> => {
    const env: Record<string, string> = {};
    for (const line of mcpForm.stdio_env.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.includes('=')) continue;
      const eqIdx = trimmed.indexOf('=');
      const key = trimmed.substring(0, eqIdx).trim();
      const value = trimmed.substring(eqIdx + 1).trim();
      if (key) env[key] = value;
    }
    return env;
  };

  const buildStdioConfig = () => ({
    command: mcpForm.stdio_command.trim(),
    args: mcpForm.stdio_args.trim() ? mcpForm.stdio_args.trim().split(/\s+/) : [],
    env: parseStdioEnv(),
  });

  const handleValidateMcp = async () => {
    setMcpValidating(true);
    try {
      const result = await mcpAPI.validateConnection({
        transport: mcpForm.transport,
        server_url: mcpForm.transport === 'sse' ? mcpForm.server_url.trim() : undefined,
        auth_type: mcpForm.transport === 'sse' ? mcpForm.auth_type : 'none',
        auth_config: mcpForm.transport === 'sse' ? buildMcpAuthConfig() : undefined,
        stdio_config: mcpForm.transport === 'stdio' ? buildStdioConfig() : undefined,
      });
      setMcpValidation(result);
      if (result.valid) {
        success(result.message || 'Connection successful');
      } else {
        error(result.message || 'Validation failed');
      }
    } catch (err) {
      log.error({ err }, 'MCP validation request failed');
      error('Failed to reach backend for validation');
    } finally {
      setMcpValidating(false);
    }
  };

  const handleCreateMcp = async () => {
    setMcpCreating(true);
    try {
      await mcpAPI.createConnection({
        name: mcpForm.name.trim(),
        transport: mcpForm.transport,
        server_url: mcpForm.transport === 'sse' ? mcpForm.server_url.trim() : undefined,
        auth_type: mcpForm.transport === 'sse' ? mcpForm.auth_type : 'none',
        auth_config: mcpForm.transport === 'sse' ? buildMcpAuthConfig() : undefined,
        stdio_config: mcpForm.transport === 'stdio' ? buildStdioConfig() : undefined,
        description: mcpForm.description.trim() || undefined,
        tools_enabled: mcpForm.tools_enabled,
      });
      success('MCP connection saved');
      setMcpForm({
        name: '', transport: 'stdio', server_url: '', auth_type: 'none',
        auth_token: '', stdio_command: '', stdio_args: '', stdio_env: '',
        description: '', tools_enabled: true,
      });
      setMcpValidation({});
      await loadMcpConnections();
    } catch (err) {
      log.error({ err }, 'failed to create MCP connection');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to save MCP connection');
    } finally {
      setMcpCreating(false);
    }
  };

  const handleToggleMcpToolsEnabled = async (connectionId: string, enabled: boolean) => {
    setMcpConnections((prev) =>
      prev.map((c) => (c.id === connectionId ? { ...c, tools_enabled: enabled } : c))
    );
    try {
      await mcpAPI.updateToolsEnabled(connectionId, enabled);
      success(enabled ? 'Tools enabled in chat' : 'Tools disabled');
    } catch (err) {
      setMcpConnections((prev) =>
        prev.map((c) => (c.id === connectionId ? { ...c, tools_enabled: !enabled } : c))
      );
      log.error({ err }, 'failed to toggle MCP tools');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to update tools setting');
    }
  };

  const handleDeleteMcp = async (connectionId: string) => {
    try {
      await mcpAPI.deleteConnection(connectionId);
      success('MCP connection deleted');
      await loadMcpConnections();
    } catch (err) {
      log.error({ err }, 'failed to delete MCP connection');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to delete MCP connection');
    }
  };

  const handleToggleMcpVisibility = async (connectionId: string, visibleToAll: boolean) => {
    setMcpConnections((prev) =>
      prev.map((c) => (c.id === connectionId ? { ...c, visible_to_all: visibleToAll } : c))
    );
    try {
      await mcpAPI.updateVisibility(connectionId, visibleToAll);
      success(visibleToAll ? 'Visible to all users' : 'Admin only');
    } catch (err) {
      setMcpConnections((prev) =>
        prev.map((c) => (c.id === connectionId ? { ...c, visible_to_all: !visibleToAll } : c))
      );
      log.error({ err }, 'failed to update MCP visibility');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to update visibility');
    }
  };

  const handleToggleVisibility = async (connectionId: string, visibleToAll: boolean) => {
    // Optimistic update
    setDbConnections((prev) =>
      prev.map((db) => (db.id === connectionId ? { ...db, visible_to_all: visibleToAll } : db))
    );
    try {
      await databasesAPI.updateVisibility(connectionId, visibleToAll);
      success(visibleToAll ? 'Visible to all users' : 'Admin only');
    } catch (err) {
      // Revert on failure
      setDbConnections((prev) =>
        prev.map((db) => (db.id === connectionId ? { ...db, visible_to_all: !visibleToAll } : db))
      );
      log.error({ err }, 'failed to update visibility');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to update visibility');
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-medium text-stone-900 mb-1">Integrations</h2>
        <p className="text-sm text-muted-foreground">
          Connect external services and databases
        </p>
      </div>

      {/* Google Drive Section */}
      <div>
        <h3 className="text-sm font-semibold mb-3">Google Drive</h3>
        <div className="space-y-4">
          <div className="flex items-center gap-3 p-4 rounded-lg border bg-muted/30">
            <GoogleDriveLogo size={32} weight="duotone" className="text-primary" />
            <div className="flex-1">
              {googleStatus.connected ? (
                <>
                  <p className="text-sm font-medium">Connected</p>
                  <p className="text-xs text-muted-foreground">{googleStatus.email}</p>
                </>
              ) : googleStatus.configured ? (
                <>
                  <p className="text-sm font-medium">Not Connected</p>
                  <p className="text-xs text-muted-foreground">Click connect to authorize Google Drive access</p>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium">Not Configured</p>
                  <p className="text-xs text-muted-foreground">Add Google Client ID and Secret in API Keys first</p>
                </>
              )}
            </div>
            {googleStatus.connected ? (
              <Button
                variant="soft"
                size="sm"
                onClick={() => setDisconnectGoogleOpen(true)}
                disabled={googleLoading}
              >
                {googleLoading ? (
                  <CircleNotch size={16} className="animate-spin" />
                ) : (
                  <>
                    <SignOut size={16} className="mr-1" />
                    Disconnect
                  </>
                )}
              </Button>
            ) : (
              <Button
                variant="default"
                size="sm"
                onClick={handleGoogleConnect}
                disabled={googleLoading || !googleStatus.configured}
              >
                {googleLoading ? (
                  <CircleNotch size={16} className="animate-spin" />
                ) : (
                  <>
                    <ArrowSquareOut size={16} className="mr-1" />
                    Connect
                  </>
                )}
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Import files directly from Google Drive. Setup: Create OAuth 2.0 credentials at{' '}
            <a
              href="https://console.cloud.google.com/apis/credentials"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Google Cloud Console
            </a>
          </p>
        </div>
      </div>

      {/* Database Connections Section — admin only */}
      {isAdmin && <>
      <Separator />

      <div>
        <h3 className="text-sm font-semibold mb-3">Database Connections</h3>
        <div className="space-y-4">
          {dbLoading ? (
            <div className="flex items-center justify-center py-6">
              <CircleNotch size={20} className="animate-spin" />
            </div>
          ) : (
            <>
              {dbConnections.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No database connections yet. Add one below to attach it as a DATABASE source in a project.
                </p>
              ) : (
                <div className="space-y-2">
                  {dbConnections.map((db) => (
                    <div
                      key={db.id}
                      className="flex items-start justify-between gap-4 rounded-lg border p-3 bg-muted/20"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium truncate">{db.name}</p>
                          <span className="text-[11px] text-muted-foreground">
                            {db.db_type}
                          </span>
                        </div>
                        {db.description && (
                          <p className="text-xs text-muted-foreground">{db.description}</p>
                        )}
                        <p className="text-xs text-muted-foreground font-mono break-all">
                          {db.connection_uri_masked}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <Switch
                            checked={db.visible_to_all}
                            onCheckedChange={(checked) => handleToggleVisibility(db.id, checked)}
                          />
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {db.visible_to_all ? 'All users' : 'Admin only'}
                          </span>
                        </label>
                        <Button
                          variant="soft"
                          size="sm"
                          onClick={() => setDeleteDbId(db.id)}
                        >
                          <Trash size={16} className="mr-1" />
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="rounded-lg border p-4 space-y-3">
                <p className="text-sm font-medium">Add connection</p>

                <div className="grid gap-2">
                  <Label>Name</Label>
                  <Input
                    value={dbForm.name}
                    onChange={(e) => setDbForm((s) => ({ ...s, name: e.target.value }))}
                    placeholder="Analytics DB"
                  />
                </div>

                <div className="grid gap-2">
                  <Label>Type</Label>
                  <Select
                    value={dbForm.db_type}
                    onValueChange={(v) => {
                      setDbForm((s) => ({ ...s, db_type: v as DatabaseType }));
                      setDbValidation({});
                    }}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select database type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="postgresql">PostgreSQL</SelectItem>
                      <SelectItem value="mysql">MySQL</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <div className="flex items-center justify-between">
                    <Label>Connection URI</Label>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowDbUri((s) => !s)}
                      type="button"
                    >
                      {showDbUri ? <EyeSlash size={16} /> : <Eye size={16} />}
                    </Button>
                  </div>
                  <Input
                    type={showDbUri ? 'text' : 'password'}
                    value={dbForm.connection_uri}
                    onChange={(e) => {
                      setDbForm((s) => ({ ...s, connection_uri: e.target.value }));
                      setDbValidation({});
                    }}
                    placeholder="postgresql://user:pass@host:5432/db"
                  />
                  {dbValidation.message && (
                    <p className={`text-xs ${dbValidation.valid ? 'text-green-600' : 'text-red-600'}`}>
                      {dbValidation.message}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Credentials are stored server-side. The UI will only display a masked URI after saving.
                  </p>
                </div>

                <div className="grid gap-2">
                  <Label>Description (optional)</Label>
                  <Input
                    value={dbForm.description}
                    onChange={(e) => setDbForm((s) => ({ ...s, description: e.target.value }))}
                    placeholder="Read-only reporting database"
                  />
                </div>

                <div className="flex gap-2">
                  <Button
                    variant="soft"
                    onClick={handleValidateDatabase}
                    disabled={dbValidating || !dbForm.connection_uri.trim()}
                  >
                    {dbValidating ? (
                      <>
                        <CircleNotch size={16} className="mr-2 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      'Test connection'
                    )}
                  </Button>
                  <Button
                    onClick={handleCreateDatabase}
                    disabled={
                      dbCreating ||
                      !dbForm.name.trim() ||
                      !dbForm.connection_uri.trim()
                    }
                  >
                    {dbCreating ? (
                      <>
                        <CircleNotch size={16} className="mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      'Save'
                    )}
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <Separator />

      {/* MCP Connections Section */}
      <div>
        <h3 className="text-sm font-semibold mb-3">MCP Connections</h3>
        <div className="space-y-4">
          {mcpLoading ? (
            <div className="flex items-center justify-center py-6">
              <CircleNotch size={20} className="animate-spin" />
            </div>
          ) : (
            <>
              {mcpConnections.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No MCP connections yet. Add one below to connect external tools and data.
                </p>
              ) : (
                <div className="space-y-2">
                  {mcpConnections.map((conn) => (
                    <div
                      key={conn.id}
                      className="flex items-start justify-between gap-4 rounded-lg border p-3 bg-muted/20"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium truncate">{conn.name}</p>
                          <span className="text-[11px] px-1.5 py-0.5 rounded bg-stone-200 text-stone-600">
                            {conn.transport}
                          </span>
                          {conn.cached_tools && conn.cached_tools.length > 0 && (
                            <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                              {conn.cached_tools.length} tools
                            </span>
                          )}
                        </div>
                        {conn.description && (
                          <p className="text-xs text-muted-foreground">{conn.description}</p>
                        )}
                        <p className="text-xs text-muted-foreground font-mono break-all">
                          {conn.transport === 'stdio'
                            ? `${conn.stdio_config?.command || ''} ${(conn.stdio_config?.args || []).join(' ')}`.trim()
                            : conn.server_url}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <label className="flex items-center gap-2 cursor-pointer" title="Enable tools in chat">
                          <Switch
                            checked={conn.tools_enabled}
                            onCheckedChange={(checked) => handleToggleMcpToolsEnabled(conn.id, checked)}
                          />
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {conn.tools_enabled ? 'Chat tools' : 'Tools off'}
                          </span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <Switch
                            checked={conn.visible_to_all}
                            onCheckedChange={(checked) => handleToggleMcpVisibility(conn.id, checked)}
                          />
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {conn.visible_to_all ? 'All users' : 'Admin only'}
                          </span>
                        </label>
                        <Button
                          variant="soft"
                          size="sm"
                          onClick={() => setDeleteMcpId(conn.id)}
                        >
                          <Trash size={16} className="mr-1" />
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="rounded-lg border p-4 space-y-3">
                <p className="text-sm font-medium">Add MCP connection</p>

                <div className="grid gap-2">
                  <Label>Name</Label>
                  <Input
                    value={mcpForm.name}
                    onChange={(e) => setMcpForm((s) => ({ ...s, name: e.target.value }))}
                    placeholder="Freshdesk"
                  />
                </div>

                <div className="grid gap-2">
                  <Label>Transport</Label>
                  <Select
                    value={mcpForm.transport}
                    onValueChange={(v) => {
                      setMcpForm((s) => ({ ...s, transport: v as McpTransport }));
                      setMcpValidation({});
                    }}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="stdio">Stdio (subprocess)</SelectItem>
                      <SelectItem value="sse">SSE (HTTP)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* SSE-specific fields */}
                {mcpForm.transport === 'sse' && (
                  <>
                    <div className="grid gap-2">
                      <Label>Server URL</Label>
                      <Input
                        value={mcpForm.server_url}
                        onChange={(e) => {
                          setMcpForm((s) => ({ ...s, server_url: e.target.value }));
                          setMcpValidation({});
                        }}
                        placeholder="https://mcp-server.example.com/sse"
                      />
                    </div>

                    <div className="grid gap-2">
                      <Label>Auth Type</Label>
                      <Select
                        value={mcpForm.auth_type}
                        onValueChange={(v) => {
                          setMcpForm((s) => ({ ...s, auth_type: v as McpAuthType, auth_token: '' }));
                          setMcpValidation({});
                        }}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">None</SelectItem>
                          <SelectItem value="bearer">Bearer Token</SelectItem>
                          <SelectItem value="api_key">API Key</SelectItem>
                          <SelectItem value="header">Custom Header</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {mcpForm.auth_type !== 'none' && (
                      <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                          <Label>
                            {mcpForm.auth_type === 'bearer' ? 'Token' : mcpForm.auth_type === 'api_key' ? 'API Key' : 'Header Value'}
                          </Label>
                          <Button variant="ghost" size="sm" onClick={() => setShowMcpToken((s) => !s)} type="button">
                            {showMcpToken ? <EyeSlash size={16} /> : <Eye size={16} />}
                          </Button>
                        </div>
                        <Input
                          type={showMcpToken ? 'text' : 'password'}
                          value={mcpForm.auth_token}
                          onChange={(e) => {
                            setMcpForm((s) => ({ ...s, auth_token: e.target.value }));
                            setMcpValidation({});
                          }}
                          placeholder={mcpForm.auth_type === 'bearer' ? 'Bearer token' : mcpForm.auth_type === 'api_key' ? 'API key' : 'Header value'}
                        />
                      </div>
                    )}
                  </>
                )}

                {/* Stdio-specific fields */}
                {mcpForm.transport === 'stdio' && (
                  <>
                    <div className="grid gap-2">
                      <Label>Command</Label>
                      <Input
                        value={mcpForm.stdio_command}
                        onChange={(e) => {
                          setMcpForm((s) => ({ ...s, stdio_command: e.target.value }));
                          setMcpValidation({});
                        }}
                        placeholder="uvx"
                      />
                      <p className="text-xs text-muted-foreground">
                        Allowed: uvx, npx, node, python3, python, docker
                      </p>
                    </div>

                    <div className="grid gap-2">
                      <Label>Arguments</Label>
                      <Input
                        value={mcpForm.stdio_args}
                        onChange={(e) => setMcpForm((s) => ({ ...s, stdio_args: e.target.value }))}
                        placeholder="freshdesk-mcp"
                      />
                      <p className="text-xs text-muted-foreground">
                        Space-separated arguments passed to the command
                      </p>
                    </div>

                    <div className="grid gap-2">
                      <div className="flex items-center justify-between">
                        <Label>Environment Variables</Label>
                        <Button variant="ghost" size="sm" onClick={() => setShowMcpToken((s) => !s)} type="button">
                          {showMcpToken ? <EyeSlash size={16} /> : <Eye size={16} />}
                        </Button>
                      </div>
                      <textarea
                        className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        rows={3}
                        value={showMcpToken ? mcpForm.stdio_env : mcpForm.stdio_env.split('\n').map(l => {
                          const eq = l.indexOf('=');
                          return eq > 0 ? l.substring(0, eq + 1) + '***' : l;
                        }).join('\n')}
                        readOnly={!showMcpToken}
                        onChange={(e) => {
                          if (!showMcpToken) return;
                          setMcpForm((s) => ({ ...s, stdio_env: e.target.value }));
                          setMcpValidation({});
                        }}
                        placeholder={'FRESHDESK_API_KEY=your-key\nFRESHDESK_DOMAIN=company.freshdesk.com'}
                      />
                      <p className="text-xs text-muted-foreground">
                        One per line, KEY=VALUE format. Secrets are stored server-side.
                      </p>
                    </div>
                  </>
                )}

                {mcpValidation.message && (
                  <p className={`text-xs ${mcpValidation.valid ? 'text-green-600' : 'text-red-600'}`}>
                    {mcpValidation.message}
                  </p>
                )}

                <div className="grid gap-2">
                  <Label>Description (optional)</Label>
                  <Input
                    value={mcpForm.description}
                    onChange={(e) => setMcpForm((s) => ({ ...s, description: e.target.value }))}
                    placeholder="Freshdesk support ticket management"
                  />
                </div>

                <label className="flex items-center gap-2 cursor-pointer">
                  <Switch
                    checked={mcpForm.tools_enabled}
                    onCheckedChange={(checked) => setMcpForm((s) => ({ ...s, tools_enabled: checked }))}
                  />
                  <span className="text-sm">Enable tools in chat</span>
                  <span className="text-xs text-muted-foreground">(Claude can call this server's tools during conversations)</span>
                </label>

                <div className="flex gap-2">
                  <Button
                    variant="soft"
                    onClick={handleValidateMcp}
                    disabled={mcpValidating || (mcpForm.transport === 'sse' ? !mcpForm.server_url.trim() : !mcpForm.stdio_command.trim())}
                  >
                    {mcpValidating ? (
                      <>
                        <CircleNotch size={16} className="mr-2 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      'Test connection'
                    )}
                  </Button>
                  <Button
                    onClick={handleCreateMcp}
                    disabled={
                      mcpCreating ||
                      !mcpForm.name.trim() ||
                      (mcpForm.transport === 'sse' ? !mcpForm.server_url.trim() : !mcpForm.stdio_command.trim())
                    }
                  >
                    {mcpCreating ? (
                      <>
                        <CircleNotch size={16} className="mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      'Save'
                    )}
                  </Button>
                </div>
              </div>

              <p className="text-xs text-muted-foreground">
                Connect to MCP servers to use their tools in chat and import resources as sources.
                Stdio transport runs the server as a subprocess (e.g., uvx freshdesk-mcp).
                SSE transport connects via HTTP.
              </p>
            </>
          )}
        </div>
      </div>

      {/* Delete MCP Confirmation */}
      <AlertDialog open={!!deleteMcpId} onOpenChange={(open) => !open && setDeleteMcpId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Warning size={20} className="text-destructive" />
              Delete MCP Connection
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{mcpConnections.find(c => c.id === deleteMcpId)?.name}</strong>? Projects using this connection will lose access.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="soft" onClick={() => setDeleteMcpId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteMcpId) {
                  handleDeleteMcp(deleteMcpId);
                  setDeleteMcpId(null);
                }
              }}
            >
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Database Confirmation */}
      <AlertDialog open={!!deleteDbId} onOpenChange={(open) => !open && setDeleteDbId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Warning size={20} className="text-destructive" />
              Delete Database Connection
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{dbConnections.find(db => db.id === deleteDbId)?.name}</strong>? Projects using this connection will lose access.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="soft" onClick={() => setDeleteDbId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteDbId) {
                  handleDeleteDatabase(deleteDbId);
                  setDeleteDbId(null);
                }
              }}
            >
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      </>}

      {/* Disconnect Google Drive Confirmation */}
      <AlertDialog open={disconnectGoogleOpen} onOpenChange={setDisconnectGoogleOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Warning size={20} className="text-destructive" />
              Disconnect Google Drive
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to disconnect <strong>{googleStatus.email}</strong>? You'll need to re-authenticate to import files again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="soft" onClick={() => setDisconnectGoogleOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                handleGoogleDisconnect();
                setDisconnectGoogleOpen(false);
              }}
            >
              Disconnect
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
