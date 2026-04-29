/**
 * SourcesList Component
 *
 * Renders the per-project source list with three orthogonal layers:
 *   1. Search-by-name (the existing search input above the panel).
 *   2. Tag-filter (one or more selected chips → AND semantics: a row
 *      must have ALL selected tags to be visible).
 *   3. Bulk-select mode — when toggled, every row gets a checkbox and
 *      a contextual action bar slides in from the bottom of the panel.
 *
 * The list is wrapped in `<div className="relative">` so the
 * BulkActionBar can absolute-position itself within it.
 */

import React, { useMemo } from 'react';
import { ScrollArea } from '../ui/scroll-area';
import { FolderOpen } from '@phosphor-icons/react';
import { Skeleton } from '../ui/skeleton';
import { type Source } from '../../lib/api/sources';
import { SourceItem } from './SourceItem';
import { TagFilterBar } from './SourceTags';
import { BulkActionBar } from './BulkActionBar';

interface SourcesListProps {
  sources: Source[];
  loading: boolean;
  searchQuery: string;
  onDownload: (sourceId: string) => void;
  onDelete: (sourceId: string, sourceName: string) => void;
  onRename: (sourceId: string, currentName: string) => void;
  onToggleActive: (sourceId: string, active: boolean) => void;
  onCancelProcessing: (sourceId: string) => void;
  onRetryProcessing: (sourceId: string) => void;
  onViewProcessed: (sourceId: string) => void;
  onSyncFreshdesk?: (sourceId: string) => void;
  onBackfillFreshdesk?: (sourceId: string) => void;
  // Tags
  tagFilter: string[];
  onTagFilterToggle: (tag: string) => void;
  onTagFilterClear: () => void;
  onTagsChange: (sourceId: string, tags: string[]) => void;
  // Bulk
  bulkMode: boolean;
  selectedIds: Set<string>;
  onToggleSelected: (sourceId: string, next: boolean) => void;
  onBulkActivate: () => void;
  onBulkDeactivate: () => void;
  onBulkDelete: () => void;
  onCancelBulk: () => void;
  bulkBusy?: boolean;
}

export const SourcesList: React.FC<SourcesListProps> = ({
  sources,
  loading,
  searchQuery,
  onDownload,
  onDelete,
  onRename,
  onToggleActive,
  onCancelProcessing,
  onRetryProcessing,
  onViewProcessed,
  onSyncFreshdesk,
  onBackfillFreshdesk,
  tagFilter,
  onTagFilterToggle,
  onTagFilterClear,
  onTagsChange,
  bulkMode,
  selectedIds,
  onToggleSelected,
  onBulkActivate,
  onBulkDeactivate,
  onBulkDelete,
  onCancelBulk,
  bulkBusy,
}) => {
  // Project-wide tag universe — drives both the filter strip and the
  // per-row tag editor's suggestion list.
  const allTags = useMemo(() => {
    const set = new Set<string>();
    sources.forEach((s) => (s.tags || []).forEach((t) => set.add(t)));
    return Array.from(set).sort();
  }, [sources]);

  // Apply search + tag filters in one pass.
  const filteredSources = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return sources.filter((s) => {
      if (q && !s.name.toLowerCase().includes(q)) return false;
      if (tagFilter.length > 0) {
        const tags = new Set(s.tags || []);
        for (const t of tagFilter) {
          if (!tags.has(t)) return false;
        }
      }
      return true;
    });
  }, [sources, searchQuery, tagFilter]);

  return (
    <div className="relative flex-1 flex flex-col min-h-0">
      <TagFilterBar
        allTags={allTags}
        selected={tagFilter}
        onToggle={onTagFilterToggle}
        onClear={onTagFilterClear}
      />
      <ScrollArea className="flex-1">
        <div className={`p-4 ${bulkMode ? 'pb-20' : ''}`}>
          {loading ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="flex items-center gap-2 p-2 rounded-lg">
                  <Skeleton className="h-5 w-5 rounded" />
                  <div className="flex-1 space-y-1">
                    <Skeleton className="h-3.5 w-3/4" />
                    <Skeleton className="h-2.5 w-1/4" />
                  </div>
                  <Skeleton className="h-4 w-4 rounded" />
                </div>
              ))}
            </div>
          ) : filteredSources.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <FolderOpen size={48} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">
                {searchQuery || tagFilter.length > 0
                  ? 'No sources match these filters'
                  : 'No sources yet'}
              </p>
              <p className="text-xs mt-1">
                {searchQuery || tagFilter.length > 0
                  ? 'Try clearing a filter'
                  : 'Add documents, images, or audio to get started'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredSources.map((source) => (
                <SourceItem
                  key={source.id}
                  source={source}
                  onDownload={onDownload}
                  onDelete={onDelete}
                  onRename={onRename}
                  onToggleActive={onToggleActive}
                  onCancelProcessing={onCancelProcessing}
                  onRetryProcessing={onRetryProcessing}
                  onViewProcessed={onViewProcessed}
                  onSyncFreshdesk={onSyncFreshdesk}
                  onBackfillFreshdesk={onBackfillFreshdesk}
                  selected={bulkMode ? selectedIds.has(source.id) : undefined}
                  onToggleSelected={bulkMode ? onToggleSelected : undefined}
                  onTagClick={onTagFilterToggle}
                  knownTags={allTags}
                  onTagsChange={onTagsChange}
                />
              ))}
            </div>
          )}
        </div>
      </ScrollArea>

      <BulkActionBar
        count={selectedIds.size}
        onActivate={onBulkActivate}
        onDeactivate={onBulkDeactivate}
        onDelete={onBulkDelete}
        onCancel={onCancelBulk}
        busy={bulkBusy}
      />
    </div>
  );
};
