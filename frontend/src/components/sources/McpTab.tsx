/**
 * McpTab Component
 * Educational Note: Attaches an account-level MCP connection to a project as an MCP source.
 * Users select a connection, browse available resources, pick which ones to snapshot,
 * and NoobBook will embed them for RAG search in chat.
 */

import React, { useEffect, useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Checkbox } from '../ui/checkbox';
import { CircleNotch, Plus, ArrowsClockwise, Plug } from '@phosphor-icons/react';
import { mcpAPI, type McpResource } from '@/lib/api/settings';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { ScrollArea } from '../ui/scroll-area';
import { useIntegrations } from '@/contexts/IntegrationsContext';

interface McpTabProps {
  isAtLimit: boolean;
  onAddMcp: (connectionId: string, resourceUris: string[], name?: string, description?: string) => Promise<void>;
}

export const McpTab: React.FC<McpTabProps> = ({ isAtLimit, onAddMcp }) => {
  const [adding, setAdding] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  // Resource browsing state
  const [resources, setResources] = useState<McpResource[]>([]);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [resourcesError, setResourcesError] = useState('');
  const [selectedUris, setSelectedUris] = useState<Set<string>>(new Set());

  const [loadError, setLoadError] = useState('');
  const {
    mcpConnections: connections,
    mcpLoading: loading,
    ensureMcpConnections,
  } = useIntegrations();

  const loadConnections = async () => {
    setLoadError('');
    try {
      const conns = await ensureMcpConnections({ force: true });
      if (!selectedConnectionId && conns.length > 0) {
        setSelectedConnectionId(conns[0].id);
      }
    } catch {
      setLoadError('Failed to load MCP connections. Check your network.');
    }
  };

  useEffect(() => {
    ensureMcpConnections().then((conns) => {
      if (!selectedConnectionId && conns.length > 0) {
        setSelectedConnectionId(conns[0].id);
      }
    }).catch(() => {
      setLoadError('Failed to load MCP connections. Check your network.');
    });
  }, [ensureMcpConnections, selectedConnectionId]);

  useEffect(() => {
    if (!selectedConnectionId && connections.length > 0) {
      setSelectedConnectionId(connections[0].id);
    }
  }, [connections, selectedConnectionId]);

  // Reset resources when connection changes
  useEffect(() => {
    setResources([]);
    setSelectedUris(new Set());
    setResourcesError('');
  }, [selectedConnectionId]);

  const handleBrowseResources = async () => {
    if (!selectedConnectionId) return;
    setResourcesLoading(true);
    setResourcesError('');
    try {
      const res = await mcpAPI.listResources(selectedConnectionId);
      setResources(res);
      // Select all by default
      setSelectedUris(new Set(res.map((r) => r.uri)));
    } catch {
      setResourcesError('Failed to load resources. Check the connection in Settings.');
      setResources([]);
    } finally {
      setResourcesLoading(false);
    }
  };

  const toggleResource = (uri: string) => {
    setSelectedUris((prev) => {
      const next = new Set(prev);
      if (next.has(uri)) {
        next.delete(uri);
      } else {
        next.add(uri);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedUris.size === resources.length) {
      setSelectedUris(new Set());
    } else {
      setSelectedUris(new Set(resources.map((r) => r.uri)));
    }
  };

  const handleAdd = async () => {
    if (!selectedConnectionId || selectedUris.size === 0) return;
    setAdding(true);
    try {
      await onAddMcp(
        selectedConnectionId,
        Array.from(selectedUris),
        name.trim() || undefined,
        description.trim() || undefined
      );
      // Only clear form on success — preserve selections on failure
      setName('');
      setDescription('');
      setResources([]);
      setSelectedUris(new Set());
    } catch {
      // Error toast is handled by the parent onAddMcp; keep form state intact
    } finally {
      setAdding(false);
    }
  };

  const selected = connections.find((c) => c.id === selectedConnectionId);

  return (
    <div className="space-y-4">
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <CircleNotch size={28} className="animate-spin" />
        </div>
      ) : loadError ? (
        <div className="space-y-2">
          <p className="text-sm text-red-600">{loadError}</p>
          <Button variant="soft" onClick={loadConnections} disabled={loading}>
            Retry
          </Button>
        </div>
      ) : connections.length === 0 ? (
        <div className="space-y-2">
          <p className="text-sm">
            No MCP connections found.
          </p>
          <p className="text-xs text-muted-foreground">
            Add a connection in Admin Settings → MCP Connections, then come back here to attach resources to this project.
          </p>
          <Button variant="soft" onClick={loadConnections} disabled={loading}>
            Refresh
          </Button>
        </div>
      ) : (
        <>
          <div className="space-y-2">
            <label className="text-sm font-medium block">Select MCP connection</label>
            <Select
              value={selectedConnectionId}
              onValueChange={(v) => setSelectedConnectionId(v)}
              disabled={isAtLimit}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose an MCP server" />
              </SelectTrigger>
              <SelectContent>
                {connections.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    <div className="flex items-center gap-2">
                      <Plug size={14} />
                      {c.name}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {selected ? (
              <p className="text-xs text-muted-foreground font-mono break-all">
                {selected.transport === 'stdio'
                  ? `${selected.stdio_config?.command || ''} ${(selected.stdio_config?.args || []).join(' ')}`.trim()
                  : selected.server_url}
              </p>
            ) : null}
          </div>

          {/* Browse Resources */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Button
                variant="soft"
                size="sm"
                onClick={handleBrowseResources}
                disabled={!selectedConnectionId || resourcesLoading || isAtLimit}
              >
                {resourcesLoading ? (
                  <>
                    <CircleNotch size={14} className="mr-1 animate-spin" />
                    Loading...
                  </>
                ) : (
                  <>
                    <ArrowsClockwise size={14} className="mr-1" />
                    Browse Resources
                  </>
                )}
              </Button>
              {resources.length > 0 && (
                <span className="text-xs text-muted-foreground">
                  {selectedUris.size}/{resources.length} selected
                </span>
              )}
            </div>

            {resourcesError && (
              <p className="text-xs text-red-600">{resourcesError}</p>
            )}

            {resources.length > 0 && (
              <div className="rounded-lg border">
                <div className="flex items-center gap-2 px-3 py-2 border-b bg-muted/30">
                  <Checkbox
                    checked={selectedUris.size === resources.length}
                    onCheckedChange={toggleAll}
                  />
                  <span className="text-xs font-medium">Select all</span>
                </div>
                <ScrollArea className="max-h-[200px]">
                  <div className="divide-y">
                    {resources.map((r) => (
                      <label
                        key={r.uri}
                        className="flex items-start gap-2 px-3 py-2 hover:bg-accent cursor-pointer"
                      >
                        <Checkbox
                          checked={selectedUris.has(r.uri)}
                          onCheckedChange={() => toggleResource(r.uri)}
                          className="mt-0.5"
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm truncate">{r.name}</p>
                          {r.description && (
                            <p className="text-xs text-muted-foreground truncate">{r.description}</p>
                          )}
                          <p className="text-[11px] text-muted-foreground font-mono truncate">{r.uri}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium block">Display name (optional)</label>
            <Input
              placeholder="GitHub Docs"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isAtLimit || adding}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium block">Description (optional)</label>
            <Input
              placeholder="Documentation from MCP server"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isAtLimit || adding}
            />
          </div>

          <div className="flex gap-2">
            <Button variant="soft" onClick={loadConnections} disabled={loading}>
              Refresh
            </Button>
            <Button
              onClick={handleAdd}
              disabled={isAtLimit || adding || !selectedConnectionId || selectedUris.size === 0}
            >
              {adding ? (
                <>
                  <CircleNotch size={16} className="mr-2 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus size={16} className="mr-2" />
                  Add MCP source ({selectedUris.size} resource{selectedUris.size !== 1 ? 's' : ''})
                </>
              )}
            </Button>
          </div>

          <p className="text-xs text-muted-foreground">
            NoobBook will snapshot the selected resources, embed them, and make them searchable in chat.
          </p>
        </>
      )}
    </div>
  );
};
