/**
 * InsightCard — compact, editorial library-card row for one saved insight.
 *
 * Design notes:
 * - 3px amber-600 left bar accents the "this is a clipping" mental model
 * - Serif italic title matches the existing "Jump to latest" pill voice
 * - Status dot is pre-attentive: emerald (fresh), stone (never run), rose (failed)
 * - Hover surfaces the inline icon row to keep the resting state quiet
 * - Whole card is the click target for the detail sheet; the small arrow
 *   button in the bottom-right is a separate target that jumps directly
 *   to the source chat for users who want full history instead of a peek.
 */
import React from 'react';
import { ArrowsClockwise, ArrowUpRight, CircleNotch, Trash, Warning } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import type { SavedInsight } from '@/lib/api/insights';

const cadenceLabel = (c: SavedInsight['cadence']) => (c === 'daily' ? 'Daily' : 'Weekly');

const formatLastRun = (iso: string | null): string => {
  if (!iso) return 'Never run';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Never run';
  const diffMs = Date.now() - d.getTime();
  const mins = Math.round(diffMs / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
};

type Status = 'fresh' | 'never' | 'failed';

const statusOf = (i: SavedInsight): Status => {
  if (i.last_error) return 'failed';
  if (!i.last_run_at) return 'never';
  return 'fresh';
};

const statusDotClass: Record<Status, string> = {
  fresh: 'bg-emerald-500',
  never: 'bg-stone-300',
  failed: 'bg-rose-500',
};

interface Props {
  insight: SavedInsight;
  onOpen: (insight: SavedInsight) => void;
  onRefresh: (insight: SavedInsight) => void;
  onDelete: (insight: SavedInsight) => void;
  onJumpToChat: (insight: SavedInsight) => void;
}

export const InsightCard: React.FC<Props> = ({
  insight,
  onOpen,
  onRefresh,
  onDelete,
  onJumpToChat,
}) => {
  const status = statusOf(insight);
  const running = insight.is_running;

  const stop = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(insight)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen(insight);
        }
      }}
      className={cn(
        'group relative overflow-hidden rounded-lg border border-stone-200 bg-white pl-4 pr-3 py-3',
        'transition-all duration-150',
        'hover:border-stone-300 hover:shadow-[0_2px_8px_-2px_rgba(120,113,108,0.12)] hover:-translate-y-px',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-1',
        'cursor-pointer',
      )}
    >
      {/* amber accent bar */}
      <span
        aria-hidden
        className="absolute left-0 top-0 bottom-0 w-[3px] bg-amber-600"
      />

      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <p className="font-serif italic text-[15px] leading-snug text-stone-800 line-clamp-2">
            {insight.title}
          </p>
          <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
            <span
              aria-hidden
              className={cn('inline-block h-1.5 w-1.5 rounded-full', statusDotClass[status])}
            />
            <span className="inline-flex items-center rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-700">
              {cadenceLabel(insight.cadence)}
            </span>
            <span className="text-[11px] text-stone-500">
              {running ? 'refreshing…' : formatLastRun(insight.last_run_at)}
            </span>
            {status === 'failed' && !running && (
              <span className="inline-flex items-center gap-0.5 text-[10px] text-rose-600">
                <Warning size={10} weight="bold" />
                failed
              </span>
            )}
          </div>
        </div>

        {/* Hover-revealed action row — keeps resting state tidy */}
        <div className="flex-shrink-0 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
          <button
            type="button"
            onClick={(e) => {
              stop(e);
              onRefresh(insight);
            }}
            disabled={running}
            title="Refresh now"
            aria-label="Refresh insight"
            className="p-1 rounded text-stone-500 hover:text-amber-700 hover:bg-amber-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running ? (
              <CircleNotch size={13} className="animate-spin" />
            ) : (
              <ArrowsClockwise size={13} weight="bold" />
            )}
          </button>
          <button
            type="button"
            onClick={(e) => {
              stop(e);
              onJumpToChat(insight);
            }}
            disabled={!insight.chat_id}
            title="Open the chat"
            aria-label="Open source chat"
            className="p-1 rounded text-stone-500 hover:text-amber-700 hover:bg-amber-50 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ArrowUpRight size={13} weight="bold" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              stop(e);
              onDelete(insight);
            }}
            title="Delete insight"
            aria-label="Delete insight"
            className="p-1 rounded text-stone-500 hover:text-rose-600 hover:bg-rose-50"
          >
            <Trash size={13} weight="bold" />
          </button>
        </div>
      </div>
    </div>
  );
};
