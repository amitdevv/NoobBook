/**
 * Orchestrates project source management: owns source state and API calls,
 * delegates rendering to SourcesList / SourcesFooter / AddSourcesSheet.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  sourcesAPI,
  MAX_SOURCES,
  isSourceViewable,
  type Source,
} from '../../lib/api/sources';
import { chatsAPI } from '../../lib/api/chats';
import { ToastContainer } from '../ui/toast';
import { useToast } from '../ui/use-toast';
import { SourcesHeader } from './SourcesHeader';
import { SourcesList } from './SourcesList';
import { SourcesFooter } from './SourcesFooter';
import { AddSourcesSheet } from './AddSourcesSheet';
import { SourcePreviewSheet } from './preview/SourcePreviewSheet';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { ScrollArea } from '../ui/scroll-area';
import { getAuthUrl } from '../../lib/api/client';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';
import {
  Books,
  CaretRight,
  Plus,
} from '@phosphor-icons/react';
import { getSourceIcon } from './sourceIcon';
import { createLogger } from '@/lib/logger';
import { patchOne, removeOne, upsertOne } from '@/lib/resourceState';

const log = createLogger('sources-panel');

interface SourcesPanelProps {
  projectId: string;
  isCollapsed?: boolean;
  onExpand?: () => void;
  onSourcesChange?: () => void;
  activeChatId?: string | null;
  selectedSourceIds?: string[];
  onSelectedSourcesChange?: (ids: string[]) => void;
}


export const SourcesPanel: React.FC<SourcesPanelProps> = ({
  projectId,
  isCollapsed,
  onExpand,
  onSourcesChange,
  activeChatId,
  selectedSourceIds = [],
  onSelectedSourcesChange,
}) => {
  const { toasts, dismissToast, success, error, info, showToast } = useToast();

  // State
  const [sources, setSources] = useState<Source[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number; pct: number; fileName: string } | null>(null);

  // Rename dialog state
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renameSourceId, setRenameSourceId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  // Source preview state. The new SourcePreviewSheet does its own
  // fetching from the source object, so we only need to track which
  // source is open + visibility.
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerSource, setViewerSource] = useState<Source | null>(null);

  /**
   * Ref for error function to avoid infinite loop in useCallback
   * Toast functions are recreated each render, causing
   * useCallback to recreate loadSources, triggering useEffect infinitely.
   * Using a ref ensures we always have the latest function without re-renders.
   */
  const errorRef = useRef(error);
  errorRef.current = error;

  // Ref for onSourcesChange to use in effects without triggering re-renders
  const onSourcesChangeRef = useRef(onSourcesChange);
  onSourcesChangeRef.current = onSourcesChange;

  // Ref to track previous sources for detecting status changes
  const prevSourcesRef = useRef<Source[]>([]);

  // Ref to track recently toggled source IDs (prevents stale polls from reverting)
  const recentTogglesRef = useRef<Set<string>>(new Set());

  // Ref for selectedSourceIds to use in callbacks without re-creating them
  const selectedSourceIdsRef = useRef(selectedSourceIds);
  selectedSourceIdsRef.current = selectedSourceIds;

  // Ref to the latest sources so the fixed-cadence Freshdesk interval can read
  // them without depending on `sources` (which would tear down/recreate the
  // 15-min timer on every 3s status poll).
  const sourcesRef = useRef(sources);
  sourcesRef.current = sources;

  /**
   * Load sources from API (with loading state for initial load)
   */
  const loadSources = useCallback(async () => {
    try {
      const data = await sourcesAPI.listSources(projectId);
      // Override active flag with per-chat selection
      const ids = selectedSourceIdsRef.current;
      setSources(data.map(s => ({ ...s, active: ids.includes(s.id) })));
    } catch (err) {
      log.error({ err }, 'failed to load sources');
      errorRef.current('Failed to load sources');
    } finally {
      setInitialLoading(false);
    }
  }, [projectId]);

  /**
   * Silent refresh for polling (no loading state to avoid flicker)
   * This is used for background polling so the UI
   * doesn't flicker on each refresh.
   */
  const refreshSources = useCallback(async () => {
    try {
      const data = await sourcesAPI.listSources(projectId);
      const ids = selectedSourceIdsRef.current;
      setSources(prev => {
        if (prev.length === 0) return data.map(s => ({ ...s, active: ids.includes(s.id) }));
        // Preserve active state for recently toggled sources (prevents stale polls from reverting)
        return data.map(source => {
          if (recentTogglesRef.current.has(source.id)) {
            const local = prev.find(s => s.id === source.id);
            if (local) return { ...source, active: local.active };
          }
          // Override active from per-chat selection
          return { ...source, active: ids.includes(source.id) };
        });
      });
    } catch (err) {
      log.error({ err }, 'failed to refresh sources');
      // Don't show toast on polling errors to avoid spam
    }
  }, [projectId]);

  // Load sources on mount and when projectId changes
  useEffect(() => {
    loadSources();
  }, [loadSources]);

  // Auto-sync Freshdesk sources every 15 minutes
  useEffect(() => {
    const FRESHDESK_SYNC_INTERVAL = 15 * 60 * 1000; // 15 minutes

    const interval = setInterval(async () => {
      const freshdeskSources = sourcesRef.current.filter(
        (s) => s.status === 'ready' &&
          ((s.embedding_info as Record<string, string>)?.file_extension || '') === '.freshdesk'
      );
      for (const src of freshdeskSources) {
        try {
          await sourcesAPI.syncFreshdesk(projectId, src.id);
          await refreshSources();
        } catch {
          // Silent — don't spam errors for background sync
        }
      }
    }, FRESHDESK_SYNC_INTERVAL);

    return () => clearInterval(interval);
  // Fixed 15-min cadence keyed only on project; reads latest sources via ref.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  /**
   * Detect when sources transition to "ready" status
   * When a source finishes processing, ChatPanel needs to know
   * so it can update the active sources count in the header. We compare previous
   * and current sources to detect this transition.
   */
  useEffect(() => {
    const prevSources = prevSourcesRef.current;

    // Check if any source transitioned to "ready"
    const hasNewReadySource = sources.some(source => {
      const prevSource = prevSources.find(s => s.id === source.id);
      // Source is now ready and wasn't ready before (or didn't exist)
      return source.status === 'ready' && (!prevSource || prevSource.status !== 'ready');
    });

    // Update ref for next comparison
    prevSourcesRef.current = sources;

    // Notify parent if a source became ready
    if (hasNewReadySource && prevSources.length > 0) {
      onSourcesChangeRef.current?.();
    }
  }, [sources]);

  /**
   * Derive source.active from per-chat selectedSourceIds.
   * Source checkboxes now reflect the active chat's selection,
   * not the global is_active flag from the backend.
   */
  useEffect(() => {
    setSources(prev =>
      prev.map(s => ({ ...s, active: selectedSourceIds.includes(s.id) }))
    );
  }, [selectedSourceIds]);

  /**
   * Polling for source status updates
   * When sources are actively processing or embedding, we poll
   * every 3 seconds to update the UI. Polling stops when no sources are working.
   * Note: We check for "processing" and "embedding", not "uploaded" because
   * "uploaded" is also the state after cancellation (waiting for user to retry).
   */
  useEffect(() => {
    // Only poll when sources are actively being processed or embedded
    const hasActiveSources = sources.some(
      s => s.status === 'processing' || s.status === 'embedding'
    );

    if (!hasActiveSources) {
      return; // No polling needed
    }

    // Set up polling interval with silent refresh (no flicker)
    const pollInterval = setInterval(() => {
      refreshSources();
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(pollInterval);
  }, [sources, refreshSources]);

  // Pull the user-facing error out of an axios envelope when present,
  // otherwise fall back to the Error message or a supplied default.
  const resolveErrorMessage = (err: unknown, fallback: string): string => {
    const base = err instanceof Error ? err.message : fallback;
    if (typeof err === 'object' && err !== null && 'response' in err) {
      return (err as { response?: { data?: { error?: string } } }).response?.data?.error || base;
    }
    return base;
  };

  // Shared path for every "add a single source" flow: enforce the source cap,
  // optimistically insert the created source (honoring the current selection),
  // toast, and surface a clean error. File upload stays separate — it has its
  // own batch/progress/retry control flow.
  const addSource = async (
    apiCall: () => Promise<Source>,
    { successMsg, fallbackErr, logMsg }: { successMsg: string; fallbackErr: string; logMsg: string },
  ): Promise<void> => {
    if (sources.length >= MAX_SOURCES) {
      error(`Cannot add. Maximum ${MAX_SOURCES} sources allowed.`);
      return;
    }
    try {
      const created = await apiCall();
      setSources((prev) => upsertOne(prev, { ...created, active: selectedSourceIdsRef.current.includes(created.id) }, { prepend: true }));
      success(successMsg);
      setSheetOpen(false);
    } catch (err: unknown) {
      log.error({ err }, logMsg);
      error(resolveErrorMessage(err, fallbackErr));
    }
  };

  const handleFileUpload = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);

    // Check source limit
    if (sources.length + fileArray.length > MAX_SOURCES) {
      error(`Cannot upload. Maximum ${MAX_SOURCES} sources allowed.`);
      return;
    }

    setUploading(true);

    try {
      for (let i = 0; i < fileArray.length; i++) {
        const file = fileArray[i];
        setUploadProgress({ current: i + 1, total: fileArray.length, pct: 0, fileName: file.name });
        const created = await sourcesAPI.uploadSource(projectId, file, undefined, undefined, (pct) => {
          setUploadProgress((prev) => prev ? { ...prev, pct } : prev);
        });
        setSources((prev) => upsertOne(prev, { ...created, active: selectedSourceIdsRef.current.includes(created.id) }, { prepend: true }));
      }
      success(`Uploaded ${fileArray.length} file(s) successfully`);
      setSheetOpen(false);
    } catch (err: unknown) {
      log.error({ err }, 'failed to upload files');
      // Inline Retry on the toast: one click re-runs the same upload batch
      // without making the user re-pick files. Snapshot the original list
      // so the closure stays stable even after `setUploading(false)`.
      const retryFiles = fileArray;
      showToast('error', resolveErrorMessage(err, 'Upload failed'), {
        label: 'Retry',
        onClick: () => handleFileUpload(retryFiles),
      });
    } finally {
      setUploading(false);
      setUploadProgress(null);
    }
  };

  const handleAddUrl = (url: string) =>
    addSource(() => sourcesAPI.addUrlSource(projectId, url),
      { successMsg: 'URL source added successfully', fallbackErr: 'Failed to add URL', logMsg: 'failed to add URL source' });

  const handleAddText = (content: string, name: string) =>
    addSource(() => sourcesAPI.addTextSource(projectId, content, name),
      { successMsg: 'Text source added successfully', fallbackErr: 'Failed to add text', logMsg: 'failed to add text source' });

  const handleAddResearch = (topic: string, description: string, links: string[]) =>
    addSource(() => sourcesAPI.addResearchSource(projectId, topic, description, links),
      { successMsg: 'Deep research started - this may take a few minutes', fallbackErr: 'Failed to start research', logMsg: 'failed to start research' });

  const handleAddDatabase = (connectionId: string, name?: string, description?: string) =>
    addSource(() => sourcesAPI.addDatabaseSource(projectId, connectionId, name, description),
      { successMsg: 'Database source added successfully', fallbackErr: 'Failed to add database', logMsg: 'failed to add database source' });

  const handleAddMcp = (connectionId: string, resourceUris: string[], name?: string, description?: string) =>
    addSource(() => sourcesAPI.addMcpSource(projectId, connectionId, resourceUris, name, description),
      { successMsg: 'MCP source added successfully', fallbackErr: 'Failed to add MCP source', logMsg: 'failed to add MCP source' });

  const handleAddFreshdesk = (name?: string, description?: string) =>
    addSource(() => sourcesAPI.addFreshdeskSource(projectId, name, description),
      { successMsg: 'Freshdesk sync started — fetching last 90 days of tickets. Check the status bar for progress.', fallbackErr: 'Failed to add Freshdesk source', logMsg: 'failed to add Freshdesk source' });

  const handleAddJira = (name?: string, description?: string) =>
    addSource(() => sourcesAPI.addJiraSource(projectId, name, description),
      { successMsg: 'Jira source added — processing issues. Check the status bar for progress.', fallbackErr: 'Failed to add Jira source', logMsg: 'failed to add Jira source' });

  const handleAddMixpanel = (name?: string, description?: string) =>
    addSource(() => sourcesAPI.addMixpanelSource(projectId, name, description),
      { successMsg: 'Mixpanel source added — verifying connection. Check the status bar for progress.', fallbackErr: 'Failed to add Mixpanel source', logMsg: 'failed to add Mixpanel source' });

  /**
   * Handle Freshdesk sync
   */
  const handleSyncFreshdesk = async (sourceId: string) => {
    try {
      await sourcesAPI.syncFreshdesk(projectId, sourceId);
      setSources((prev) => patchOne(prev, sourceId, { status: 'processing' }));
      success('Freshdesk sync started — check status bar for progress');
    } catch (err: unknown) {
      log.error({ err }, 'failed to sync Freshdesk');
      error('Failed to sync Freshdesk tickets');
    }
  };

  const handleBackfillFreshdesk = async (sourceId: string) => {
    try {
      await sourcesAPI.backfillFreshdesk(projectId, sourceId);
      setSources((prev) => patchOne(prev, sourceId, { status: 'processing' }));
      success('Freshdesk backfill started — check status bar for progress');
    } catch (err: unknown) {
      log.error({ err }, 'failed to backfill Freshdesk');
      error('Failed to backfill Freshdesk tickets');
    }
  };

  /**
   * Handle source deletion
   */
  const handleDeleteSource = async (sourceId: string, sourceName: string) => {
    try {
      await sourcesAPI.deleteSource(projectId, sourceId);
      setSources((prev) => removeOne(prev, sourceId));
      success(`Deleted "${sourceName}"`);
      // Notify parent that sources changed (triggers ChatPanel refresh)
      onSourcesChange?.();
    } catch (err) {
      log.error({ err }, 'failed to delete source');
      error('Failed to delete source');
    }
  };

  /**
   * Handle source download
   */
  const handleDownloadSource = (sourceId: string) => {
    const url = sourcesAPI.getDownloadUrl(projectId, sourceId);
    window.open(getAuthUrl(url), '_blank');
  };

  /**
   * Open rename dialog for a source
   */
  const handleRenameSource = (sourceId: string, currentName: string) => {
    setRenameSourceId(sourceId);
    setRenameValue(currentName);
    setRenameDialogOpen(true);
  };

  /**
   * Submit rename
   */
  const handleRenameSubmit = async () => {
    if (!renameSourceId || !renameValue.trim()) return;

    try {
      const updated = await sourcesAPI.updateSource(projectId, renameSourceId, {
        name: renameValue.trim(),
      });
      setSources((prev) => upsertOne(prev, { ...updated, active: selectedSourceIdsRef.current.includes(updated.id) }));
      success('Source renamed successfully');
      setRenameDialogOpen(false);
    } catch (err) {
      log.error({ err }, 'failed to rename source');
      error('Failed to rename source');
    }
  };

  /**
   * Toggle source active state (per-chat selection).
   * Instead of updating the source's global is_active flag,
   * we now update the chat's selected_source_ids array. Each chat maintains
   * its own set of selected sources independently.
   */
  const handleToggleActive = async (sourceId: string, active: boolean) => {
    if (!activeChatId) {
      info('Open a chat first — sources are selected per chat');
      return;
    }

    // Compute new selection
    const newIds = active
      ? [...selectedSourceIds, sourceId]
      : selectedSourceIds.filter(id => id !== sourceId);

    // Optimistic update: change checkbox immediately
    setSources(prev =>
      prev.map(s => s.id === sourceId ? { ...s, active } : s)
    );
    onSelectedSourcesChange?.(newIds);

    // Guard against stale poll responses overwriting this toggle
    recentTogglesRef.current.add(sourceId);

    try {
      await chatsAPI.updateChatSources(projectId, activeChatId, newIds);
    } catch (err) {
      log.error({ err }, 'failed to update chat source selection');
      error('Failed to update source selection');
      // Revert optimistic update on error
      const revertedIds = active
        ? selectedSourceIds.filter(id => id !== sourceId)
        : [...selectedSourceIds, sourceId];
      onSelectedSourcesChange?.(revertedIds);
      setSources(prev =>
        prev.map(s => s.id === sourceId ? { ...s, active: !active } : s)
      );
    } finally {
      // Clear the guard after a delay (allow DB to catch up)
      setTimeout(() => recentTogglesRef.current.delete(sourceId), 5000);
    }
  };

  /**
   * Cancel processing for a source
   * Stops any running tasks, cleans up processed data,
   * but keeps raw file so user can retry later.
   */
  const handleCancelProcessing = async (sourceId: string) => {
    try {
      await sourcesAPI.cancelProcessing(projectId, sourceId);
      setSources((prev) => patchOne(prev, sourceId, { status: 'uploaded' }));
      success('Processing cancelled');
    } catch (err) {
      log.error({ err }, 'failed to cancel processing');
      error('Failed to cancel processing');
    }
  };

  /**
   * Retry processing for a failed or uploaded source
   */
  const handleRetryProcessing = async (sourceId: string) => {
    try {
      await sourcesAPI.retryProcessing(projectId, sourceId);
      setSources((prev) => patchOne(prev, sourceId, { status: 'processing', error_message: null }));
      success('Processing restarted');
    } catch (err) {
      log.error({ err }, 'failed to retry processing');
      error('Failed to retry processing');
    }
  };

  /**
   * View processed content for a source
   * Fetches the extracted text from the backend and displays
   * it in a side sheet. Only available for text-based sources that are ready.
   */
  const handleViewProcessed = (sourceId: string) => {
    const target = sources.find((s) => s.id === sourceId);
    if (!target) {
      log.warn({ sourceId }, 'cannot preview: source not in current list');
      return;
    }
    setViewerSource(target);
    setViewerOpen(true);
  };

  // Calculate totals
  const totalSize = sources.reduce((sum, s) => sum + s.file_size, 0);
  const sourcesCount = sources.length;
  const isAtLimit = sourcesCount >= MAX_SOURCES;

  return (
    <>
      {/* Collapsed view - show icon bar with source icons */}
      {isCollapsed ? (
        <TooltipProvider delayDuration={100}>
          <div className="h-full flex flex-col items-center py-3 bg-card">
            {/* Sources header icon */}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={onExpand}
                  className="p-2.5 rounded-lg hover:bg-muted transition-colors mb-2"
                >
                  <Books size={24} className="text-primary" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <p>Sources</p>
              </TooltipContent>
            </Tooltip>

            {/* Expand button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={onExpand}
                  className="p-2 rounded-lg hover:bg-muted transition-colors mb-3"
                >
                  <CaretRight size={16} className="text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <p>Expand panel</p>
              </TooltipContent>
            </Tooltip>

            {/* Add source button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setSheetOpen(true)}
                  disabled={isAtLimit}
                  className={`p-2.5 rounded-lg hover:bg-muted transition-colors mb-1 ${isAtLimit ? 'opacity-30 cursor-default' : ''}`}
                >
                  <Plus size={20} className="text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <p>Add sources</p>
              </TooltipContent>
            </Tooltip>

            {/* Source icons */}
            <ScrollArea className="flex-1 w-full">
              <div className="flex flex-col items-center gap-1.5 px-1">
                {sources.map((source) => {
                  const IconComponent = getSourceIcon(source);
                  return (
                    <Tooltip key={source.id}>
                      <TooltipTrigger asChild>
                        <button
                          onClick={() => {
                            if (isSourceViewable(source)) {
                              handleViewProcessed(source.id);
                            } else {
                              onExpand?.();
                            }
                          }}
                          className="p-2.5 rounded-lg hover:bg-muted transition-colors w-full flex justify-center"
                        >
                          <IconComponent size={22} weight="bold" className="text-muted-foreground" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="right">
                        <p className="max-w-[200px] truncate">{source.name}</p>
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </div>
            </ScrollArea>
          </div>
        </TooltipProvider>
      ) : (
        <div className="flex flex-col h-full" data-tour="sources-panel">
          <SourcesHeader
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onAddClick={() => setSheetOpen(true)}
            isAtLimit={isAtLimit}
          />

          <SourcesList
            sources={sources}
            loading={initialLoading}
            searchQuery={searchQuery}
            onDownload={handleDownloadSource}
            onDelete={handleDeleteSource}
            onRename={handleRenameSource}
            onToggleActive={handleToggleActive}
            onCancelProcessing={handleCancelProcessing}
            onRetryProcessing={handleRetryProcessing}
            onViewProcessed={handleViewProcessed}
            onSyncFreshdesk={handleSyncFreshdesk}
            onBackfillFreshdesk={handleBackfillFreshdesk}
          />

          <SourcesFooter sourcesCount={sourcesCount} totalSize={totalSize} />
        </div>
      )}

      <AddSourcesSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        projectId={projectId}
        sourcesCount={sourcesCount}
        onUpload={handleFileUpload}
        onAddUrl={handleAddUrl}
        onAddText={handleAddText}
        onAddResearch={handleAddResearch}
        onAddDatabase={handleAddDatabase}
        onAddMcp={handleAddMcp}
        onAddFreshdesk={handleAddFreshdesk}
        onAddJira={handleAddJira}
        onAddMixpanel={handleAddMixpanel}
        uploadProgress={uploadProgress}
        onImportComplete={refreshSources}
        uploading={uploading}
      />

      {/* Rename Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Rename Source</DialogTitle>
            <DialogDescription>
              Enter a new name for this source.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                placeholder="Source name"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleRenameSubmit();
                  }
                }}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="soft" onClick={() => setRenameDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleRenameSubmit} disabled={!renameValue.trim()}>
              Rename
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Source preview — type-aware (PDF, image, audio, csv,
          markdown for everything text-based). */}
      <SourcePreviewSheet
        open={viewerOpen}
        onOpenChange={setViewerOpen}
        projectId={projectId}
        source={viewerSource}
      />

      {/* Toast notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  );
};
