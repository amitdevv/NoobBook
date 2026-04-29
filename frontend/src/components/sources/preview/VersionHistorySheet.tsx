/**
 * VersionHistorySheet — "carbon copies" version history for TEXT
 * sources, opened from the preview toolbar's History button.
 *
 * Each version renders as a paper-card row with a serial number, a
 * relative timestamp, the saved name, and a content preview. Click a
 * card to expand the preview inline; Restore replaces the current
 * source body with that version's content (the backend snapshots the
 * now-current body first, so restore is itself a versioned operation).
 *
 * Visual continuity: serif italic header, monospace tracking labels,
 * amber spine on the current version, single-tap-to-confirm Restore.
 */
import React, { useEffect, useState } from 'react';
import { Sheet, SheetContent, SheetTitle } from '../../ui/sheet';
import { ArrowUUpLeft, CircleNotch, Eye, ClockCounterClockwise } from '@phosphor-icons/react';
import { sourcesAPI } from '../../../lib/api/sources';
import { createLogger } from '@/lib/logger';

const log = createLogger('version-history');

interface VersionMeta {
  id: string;
  source_id: string;
  name: string;
  created_at: string;
}

interface VersionHistorySheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  sourceId: string;
  /** Called after a successful restore so the parent can refetch. */
  onRestored?: () => void;
}

function relativeTimestamp(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return 'just now';
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)} min ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)} h ago`;
  if (ms < 7 * 86_400_000) return `${Math.floor(ms / 86_400_000)} d ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

function exactTimestamp(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export const VersionHistorySheet: React.FC<VersionHistorySheetProps> = ({
  open,
  onOpenChange,
  projectId,
  sourceId,
  onRestored,
}) => {
  const [versions, setVersions] = useState<VersionMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedContent, setExpandedContent] = useState<Record<string, string>>({});
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setVersions(null);
    setError(null);
    setExpandedId(null);
    setExpandedContent({});
    setConfirmId(null);

    sourcesAPI
      .listVersions(projectId, sourceId)
      .then((rows) => {
        if (cancelled) return;
        setVersions(rows);
      })
      .catch((e) => {
        if (cancelled) return;
        log.error({ err: e }, 'failed to list versions');
        setError('Could not load version history.');
      });
    return () => {
      cancelled = true;
    };
  }, [open, projectId, sourceId]);

  const handleExpand = async (versionId: string) => {
    if (expandedId === versionId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(versionId);
    if (!expandedContent[versionId]) {
      try {
        const v = await sourcesAPI.getVersion(projectId, sourceId, versionId);
        setExpandedContent((prev) => ({ ...prev, [versionId]: v.content }));
      } catch (e) {
        log.error({ err: e }, 'failed to fetch version content');
      }
    }
  };

  const handleRestore = async (versionId: string) => {
    if (confirmId !== versionId) {
      // First click arms confirmation; second click executes.
      setConfirmId(versionId);
      window.setTimeout(() => {
        setConfirmId((cur) => (cur === versionId ? null : cur));
      }, 4000);
      return;
    }
    setRestoringId(versionId);
    setRestoreError(null);
    try {
      await sourcesAPI.restoreVersion(projectId, sourceId, versionId);
      onRestored?.();
      onOpenChange(false);
    } catch (e) {
      log.error({ err: e }, 'restore failed');
      // Surface the failure to the user — previously it was
      // swallowed silently and the sheet just sat there.
      setRestoreError(
        e instanceof Error
          ? e.message
          : 'Could not restore that version. Try again or refresh.',
      );
    } finally {
      setRestoringId(null);
      setConfirmId(null);
    }
  };

  const totalCount = versions?.length ?? 0;
  // Newest version becomes "current" — the spine accent.
  const newestId = versions?.[0]?.id;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-[95vw] sm:w-[420px] flex flex-col p-0 bg-stone-50"
      >
        <SheetTitle className="sr-only">Version history</SheetTitle>

        {/* Header — serif italic, with a dot-dash divider beneath. */}
        <div className="flex-shrink-0 px-6 pt-6 pb-3">
          <div className="flex items-center gap-2 text-stone-400">
            <ClockCounterClockwise size={14} />
            <span className="text-[10px] uppercase tracking-[0.2em] font-mono">
              History
            </span>
          </div>
          <h2 className="mt-1 font-serif italic text-[22px] text-stone-900 leading-tight">
            Carbon copies
          </h2>
          <p className="mt-1 text-[12px] text-stone-500">
            {totalCount === 0
              ? 'No prior versions yet.'
              : `${totalCount} prior version${totalCount === 1 ? '' : 's'}.`}
          </p>
        </div>
        <div className="px-6">
          <div className="border-t border-dashed border-stone-300" />
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2">
          {error && (
            <p className="text-sm text-rose-600">{error}</p>
          )}
          {restoreError && (
            <div className="rounded-md border border-rose-200 bg-rose-50/80 px-3 py-2 text-[12px] text-rose-700">
              {restoreError}
            </div>
          )}
          {!versions && !error && (
            <div className="h-32 flex items-center justify-center text-sm text-stone-500">
              <CircleNotch size={16} className="mr-2 animate-spin" />
              Loading versions…
            </div>
          )}
          {versions && versions.length === 0 && !error && (
            <div className="h-32 flex flex-col items-center justify-center text-stone-400 gap-2">
              <ClockCounterClockwise size={22} />
              <p className="text-sm">No prior versions yet.</p>
              <p className="text-[11px] max-w-[260px] text-center">
                Each time you save edits to this source, the previous body
                is filed here.
              </p>
            </div>
          )}
          {versions?.map((v, idx) => {
            const isCurrent = v.id === newestId;
            const isExpanded = expandedId === v.id;
            const serial = totalCount - idx; // newest = highest #
            return (
              <article
                key={v.id}
                className={`relative rounded-lg border bg-white px-3.5 py-2.5 transition-colors ${
                  isCurrent
                    ? 'border-stone-200/70 border-l-2 border-l-amber-500'
                    : 'border-stone-200/70 hover:border-stone-300'
                }`}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-mono text-[11px] text-stone-400 tracking-wide">
                    v#{String(serial).padStart(2, '0')} · {relativeTimestamp(v.created_at)}
                  </span>
                  {isCurrent && (
                    <span className="text-[9px] uppercase tracking-[0.18em] font-mono text-amber-700">
                      most recent
                    </span>
                  )}
                </div>
                <p
                  className="mt-0.5 font-serif italic text-[14px] text-stone-700 truncate"
                  title={v.name}
                >
                  {v.name}
                </p>

                {isExpanded && (
                  <div className="mt-2.5 rounded-md bg-stone-50 border border-stone-200/80 px-3 py-2 max-h-48 overflow-y-auto">
                    {expandedContent[v.id] ? (
                      <pre className="whitespace-pre-wrap text-[12px] leading-relaxed text-stone-700 font-serif italic">
                        {expandedContent[v.id].slice(0, 1200)}
                        {expandedContent[v.id].length > 1200 ? '…' : ''}
                      </pre>
                    ) : (
                      <span className="inline-flex items-center text-[11px] text-stone-500">
                        <CircleNotch size={11} className="mr-2 animate-spin" />
                        Loading…
                      </span>
                    )}
                  </div>
                )}

                <div className="mt-2 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => handleExpand(v.id)}
                    className="inline-flex items-center gap-1 text-[11px] text-stone-500 hover:text-amber-700 transition-colors"
                  >
                    <Eye size={11} />
                    {isExpanded ? 'Collapse' : 'View'}
                  </button>
                  <span className="text-[10px] text-stone-300 font-mono" title={exactTimestamp(v.created_at)}>
                    {exactTimestamp(v.created_at)}
                  </span>
                  {/* Restore is available on every snapshot —
                      including the most-recent one. The "current"
                      label is for the most-recent SNAPSHOT, not the
                      live document; the user has typically edited
                      past it, so rolling back to the most-recent
                      snapshot is the primary undo-the-last-save
                      use case. */}
                  <button
                    type="button"
                    onClick={() => handleRestore(v.id)}
                    disabled={restoringId === v.id}
                    className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                      confirmId === v.id
                        ? 'bg-amber-600 text-white hover:bg-amber-700'
                        : 'bg-stone-100 text-stone-700 hover:bg-amber-50 hover:text-amber-800'
                    }`}
                  >
                    {restoringId === v.id ? (
                      <>
                        <CircleNotch size={11} className="animate-spin" />
                        Restoring
                      </>
                    ) : confirmId === v.id ? (
                      <>
                        <ArrowUUpLeft size={11} weight="bold" />
                        Confirm restore
                      </>
                    ) : (
                      <>
                        <ArrowUUpLeft size={11} />
                        Restore
                      </>
                    )}
                  </button>
                </div>
              </article>
            );
          })}
        </div>

        <div className="flex-shrink-0 px-6 py-3 border-t border-stone-200/80 bg-white text-[10px] uppercase tracking-[0.18em] font-mono text-stone-400 text-center">
          Restoring snapshots the current version first
        </div>
      </SheetContent>
    </Sheet>
  );
};
