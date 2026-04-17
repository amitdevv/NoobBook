/**
 * PermissionsModal Component
 * Per-user module permissions editor for admin settings.
 * 5 collapsible categories with master + individual toggles.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  CaretDown,
  CaretRight,
  CircleNotch,
  ShieldCheck,
  Files,
  Database,
  Palette,
  Plugs,
  ChatCircle,
  Minus,
} from '@phosphor-icons/react';
import { usersAPI } from '@/lib/api/settings';
import type { UserPermissions } from '@/lib/api/settings';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';
import { cn } from '@/lib/utils';

const log = createLogger('permissions-modal');

// ---------------------------------------------------------------------------
// Category config — icon, label, description, sub-items
// ---------------------------------------------------------------------------

const CATEGORY_CONFIG: Record<
  keyof UserPermissions,
  {
    label: string;
    description: string;
    icon: React.ElementType;
    iconColor: string;
    items: Record<string, string>;
  }
> = {
  document_sources: {
    label: 'Document Sources',
    description: 'Upload and process files',
    icon: Files,
    iconColor: 'text-blue-600 bg-blue-50',
    items: {
      pdf: 'PDF',
      docx: 'DOCX',
      pptx: 'PPTX',
      image: 'Images',
      audio: 'Audio',
      url_youtube: 'URL / YouTube',
      text: 'Text / Paste',
      google_drive: 'Google Drive',
    },
  },
  data_sources: {
    label: 'Data Sources',
    description: 'Live data connections',
    icon: Database,
    iconColor: 'text-emerald-600 bg-emerald-50',
    items: {
      database: 'Database (PostgreSQL / MySQL)',
      csv: 'CSV Files',
      freshdesk: 'Freshdesk Tickets',
      jira: 'Jira Issues',
      mixpanel: 'Mixpanel Analytics',
    },
  },
  studio: {
    label: 'Studio',
    description: 'Content generation',
    icon: Palette,
    iconColor: 'text-violet-600 bg-violet-50',
    items: {
      audio_overview: 'Audio Overview',
      ad_creative: 'Ad Creative',
      flash_cards: 'Flash Cards',
      flow_diagrams: 'Flow Diagrams',
      infographics: 'Infographics',
      mind_maps: 'Mind Maps',
      quizzes: 'Quizzes',
      social_posts: 'Social Posts',
      emails: 'Email Templates',
      websites: 'Websites',
      components: 'UI Components',
      videos: 'Videos',
      wireframes: 'Wireframes',
      presentations: 'Presentations',
      prds: 'PRDs',
      marketing_strategies: 'Marketing Strategies',
      blogs: 'Blogs',
      business_reports: 'Business Reports',
    },
  },
  integrations: {
    label: 'Integrations',
    description: 'Third-party services',
    icon: Plugs,
    iconColor: 'text-amber-600 bg-amber-50',
    items: {
      jira: 'Jira',
      mixpanel: 'Mixpanel',
      notion: 'Notion',
      mcp: 'MCP Connections',
      elevenlabs: 'ElevenLabs (Voice)',
    },
  },
  chat_features: {
    label: 'Chat Features',
    description: 'Advanced capabilities',
    icon: ChatCircle,
    iconColor: 'text-rose-600 bg-rose-50',
    items: {
      memory: 'Memory (Store / Recall)',
      voice_input: 'Voice Input',
      chat_export: 'Chat Export (PDF)',
    },
  },
};

const CATEGORY_ORDER: (keyof UserPermissions)[] = [
  'document_sources',
  'data_sources',
  'studio',
  'integrations',
  'chat_features',
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildDefaultPermissions(): UserPermissions {
  const perms: Record<string, { enabled: boolean; items: Record<string, boolean> }> = {};
  for (const key of CATEGORY_ORDER) {
    const items: Record<string, boolean> = {};
    for (const itemKey of Object.keys(CATEGORY_CONFIG[key].items)) {
      items[itemKey] = true;
    }
    perms[key] = { enabled: true, items };
  }
  return perms as unknown as UserPermissions;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PermissionsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId: string;
  userEmail: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const PermissionsModal: React.FC<PermissionsModalProps> = ({
  open,
  onOpenChange,
  userId,
  userEmail,
}) => {
  const [permissions, setPermissions] = useState<UserPermissions>(buildDefaultPermissions());
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(['document_sources', 'data_sources']),
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Per-connection access state (databases + MCP)
  const [allConnections, setAllConnections] = useState<{
    databases: { id: string; name: string }[];
    mcp: { id: string; name: string }[];
  }>({ databases: [], mcp: [] });
  const [connectionAccess, setConnectionAccess] = useState<{
    database_ids: string[];
    mcp_ids: string[];
  }>({ database_ids: [], mcp_ids: [] });

  const { success, error } = useToast();

  // Fetch on open
  const loadPermissions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await usersAPI.getUserPermissions(userId);
      setPermissions(data.permissions);
      setAllConnections(data.connections);
      setConnectionAccess(data.connection_access);
    } catch (err) {
      log.error({ err }, 'failed to load permissions');
      setPermissions(buildDefaultPermissions());
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (open) loadPermissions();
  }, [open, loadPermissions]);

  // --------------------------------------------------
  // Toggle logic
  // --------------------------------------------------

  const toggleCategory = (catKey: keyof UserPermissions) => {
    setPermissions((prev) => {
      const cat = prev[catKey];
      const next = !cat.enabled;
      const items: Record<string, boolean> = {};
      for (const k of Object.keys(cat.items)) items[k] = next;
      return { ...prev, [catKey]: { enabled: next, items } };
    });
  };

  const toggleItem = (catKey: keyof UserPermissions, itemKey: string) => {
    setPermissions((prev) => {
      const cat = prev[catKey];
      const items = { ...cat.items, [itemKey]: !cat.items[itemKey] };
      const anyOn = Object.values(items).some(Boolean);
      return { ...prev, [catKey]: { enabled: anyOn, items } };
    });
  };

  const toggleExpanded = (key: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  // --------------------------------------------------
  // Save
  // --------------------------------------------------

  const toggleConnection = (type: 'database_ids' | 'mcp_ids', connId: string) => {
    setConnectionAccess((prev) => {
      const ids = prev[type];
      const next = ids.includes(connId) ? ids.filter((id) => id !== connId) : [...ids, connId];
      return { ...prev, [type]: next };
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await usersAPI.updateUserPermissions(userId, permissions, connectionAccess);
      success('Permissions updated');
      onOpenChange(false);
    } catch (err) {
      log.error({ err }, 'failed to save permissions');
      const axErr = err as { response?: { data?: { error?: string } } };
      error(axErr.response?.data?.error || 'Failed to save permissions');
    } finally {
      setSaving(false);
    }
  };

  // Count enabled / total for a category
  const countEnabled = (catKey: keyof UserPermissions) => {
    const items = permissions[catKey].items;
    const total = Object.keys(items).length;
    const on = Object.values(items).filter(Boolean).length;
    return { on, total };
  };

  // --------------------------------------------------
  // Render
  // --------------------------------------------------

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px] max-h-[85vh] flex flex-col gap-0 p-0 overflow-hidden">
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 border-b bg-stone-50/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-100">
              <ShieldCheck size={20} weight="duotone" className="text-amber-700" />
            </div>
            <div>
              <DialogTitle className="text-base">Module Permissions</DialogTitle>
              <p className="text-sm text-muted-foreground mt-0.5">{userEmail}</p>
            </div>
          </div>
        </DialogHeader>

        {/* Body */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <CircleNotch size={24} className="animate-spin text-stone-300" />
          </div>
        ) : (
          <div className="overflow-y-auto flex-1 px-6 py-4 space-y-2">
            {CATEGORY_ORDER.map((catKey) => {
              const config = CATEGORY_CONFIG[catKey];
              const cat = permissions[catKey];
              const isExpanded = expandedCategories.has(catKey);
              const { on, total } = countEnabled(catKey);
              const allOn = on === total;
              const noneOn = on === 0;
              const isIndeterminate = !noneOn && !allOn;
              const Icon = config.icon;

              return (
                <div
                  key={catKey}
                  className={cn(
                    'rounded-lg border transition-colors',
                    isExpanded ? 'border-stone-200 bg-white' : 'border-stone-100 bg-stone-50/50 hover:bg-stone-50',
                  )}
                >
                  {/* Category row */}
                  <div className="flex items-center gap-3 px-4 py-3">
                    <button
                      type="button"
                      onClick={() => toggleExpanded(catKey)}
                      className="text-stone-400 hover:text-stone-600 transition-colors"
                    >
                      {isExpanded ? <CaretDown size={12} weight="bold" /> : <CaretRight size={12} weight="bold" />}
                    </button>

                    <div className={cn('p-1.5 rounded-md', config.iconColor)}>
                      <Icon size={14} weight="duotone" />
                    </div>

                    <Checkbox
                      checked={isIndeterminate ? 'indeterminate' : cat.enabled}
                      onCheckedChange={() => toggleCategory(catKey)}
                    />

                    <button
                      type="button"
                      onClick={() => toggleExpanded(catKey)}
                      className="flex-1 text-left flex items-center justify-between min-w-0"
                    >
                      <div className="min-w-0">
                        <span className="text-sm font-medium text-stone-800">
                          {config.label}
                        </span>
                        <span className="hidden sm:inline ml-2 text-xs text-stone-400">
                          {config.description}
                        </span>
                      </div>

                      {/* Counter pill */}
                      <span
                        className={cn(
                          'text-[11px] font-medium px-2 py-0.5 rounded-full flex-shrink-0 ml-2 tabular-nums',
                          noneOn
                            ? 'bg-red-50 text-red-600'
                            : allOn
                              ? 'bg-emerald-50 text-emerald-600'
                              : 'bg-amber-50 text-amber-700',
                        )}
                      >
                        {on}/{total}
                      </span>
                    </button>
                  </div>

                  {/* Expanded items */}
                  {isExpanded && (
                    <div className="px-4 pb-3 pl-[4.25rem]">
                      <div className="border-t border-dashed border-stone-150 pt-3 flex flex-wrap gap-x-1 gap-y-1">
                        {Object.entries(config.items).map(([itemKey, label]) => {
                          const isOn = cat.items[itemKey] !== false;
                          return (
                            <button
                              key={itemKey}
                              type="button"
                              onClick={() => toggleItem(catKey, itemKey)}
                              className={cn(
                                'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all',
                                'border cursor-pointer select-none',
                                isOn
                                  ? 'bg-stone-800 text-white border-stone-800 hover:bg-stone-700'
                                  : 'bg-white text-stone-400 border-stone-200 hover:border-stone-300 hover:text-stone-500 line-through decoration-stone-300',
                              )}
                            >
                              {isOn ? (
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                              ) : (
                                <Minus size={10} className="flex-shrink-0 opacity-50" />
                              )}
                              {label}
                            </button>
                          );
                        })}
                      </div>

                      {/* Per-connection access: nested under Database */}
                      {catKey === 'data_sources' && cat.items.database && allConnections.databases.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-dotted border-stone-200">
                          <p className="text-[11px] text-stone-400 font-medium mb-1.5 uppercase tracking-wider">Database Connections</p>
                          <div className="flex flex-wrap gap-1">
                            {allConnections.databases.map((conn) => {
                              const hasAccess = connectionAccess.database_ids.includes(conn.id);
                              return (
                                <button
                                  key={conn.id}
                                  type="button"
                                  onClick={() => toggleConnection('database_ids', conn.id)}
                                  className={cn(
                                    'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all',
                                    'border cursor-pointer select-none',
                                    hasAccess
                                      ? 'bg-emerald-700 text-white border-emerald-700 hover:bg-emerald-600'
                                      : 'bg-white text-stone-400 border-stone-200 hover:border-stone-300 line-through decoration-stone-300',
                                  )}
                                >
                                  {hasAccess ? (
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 flex-shrink-0" />
                                  ) : (
                                    <Minus size={10} className="flex-shrink-0 opacity-50" />
                                  )}
                                  {conn.name}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Per-connection access: nested under MCP */}
                      {catKey === 'integrations' && cat.items.mcp && allConnections.mcp.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-dotted border-stone-200">
                          <p className="text-[11px] text-stone-400 font-medium mb-1.5 uppercase tracking-wider">MCP Connections</p>
                          <div className="flex flex-wrap gap-1">
                            {allConnections.mcp.map((conn) => {
                              const hasAccess = connectionAccess.mcp_ids.includes(conn.id);
                              return (
                                <button
                                  key={conn.id}
                                  type="button"
                                  onClick={() => toggleConnection('mcp_ids', conn.id)}
                                  className={cn(
                                    'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all',
                                    'border cursor-pointer select-none',
                                    hasAccess
                                      ? 'bg-emerald-700 text-white border-emerald-700 hover:bg-emerald-600'
                                      : 'bg-white text-stone-400 border-stone-200 hover:border-stone-300 line-through decoration-stone-300',
                                  )}
                                >
                                  {hasAccess ? (
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 flex-shrink-0" />
                                  ) : (
                                    <Minus size={10} className="flex-shrink-0 opacity-50" />
                                  )}
                                  {conn.name}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Footer */}
        <DialogFooter className="px-6 py-4 border-t bg-stone-50/30">
          <Button variant="soft" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || loading}>
            {saving ? (
              <>
                <CircleNotch size={14} className="animate-spin mr-1.5" />
                Saving...
              </>
            ) : (
              'Save Permissions'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
