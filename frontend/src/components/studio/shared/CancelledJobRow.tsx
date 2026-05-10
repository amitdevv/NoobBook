/**
 * CancelledJobRow — shared row component for studio jobs the user
 * cancelled mid-generation.
 *
 * The previous Stop attempt deleted cancelled jobs from the output tab
 * (a server-side filter dropping rows with status='cancelled'). Users
 * couldn't tell whether they'd cancelled or whether the product had
 * silently failed, and there was no path back to a re-run. That UX
 * regression was the main reason for the PR #221 revert.
 *
 * This row is the antidote: cancelled jobs stay visible in the list,
 * with an editorial amber treatment (NOT red — red is reserved for
 * `error`) and a one-click "Generate again" affordance that re-triggers
 * the same agent with the same inputs.
 */
import React from 'react';
import { XCircle, ArrowsClockwise } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

interface CancelledJobLike {
  id: string;
  /** ISO timestamp when the cancel landed (stored in job_data.cancelled_at). */
  cancelled_at?: string | null;
  /** Falls back to completed_at or updated_at if cancelled_at isn't set. */
  completed_at?: string | null;
  updated_at?: string | null;
  /** Title / direction the user gave so the row says what got cancelled. */
  direction?: string | null;
  source_name?: string | null;
}

export interface CancelledJobRowProps {
  job: CancelledJobLike;
  /** Triggers a fresh generation with the same inputs. The hook owning the
   *  agent's state should re-call its start handler with the cancelled
   *  job's `direction` / `source_id` etc. */
  onGenerateAgain: () => void;
  /** Optional tail content (e.g. an iconographic source preview). */
  trailing?: React.ReactNode;
  className?: string;
}

const formatTime = (iso?: string | null): string => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  } catch {
    return '';
  }
};

export const CancelledJobRow: React.FC<CancelledJobRowProps> = ({
  job,
  onGenerateAgain,
  trailing,
  className,
}) => {
  const stamp =
    job.cancelled_at || job.completed_at || job.updated_at || null;
  const time = formatTime(stamp);
  const subject =
    (job.direction && job.direction.trim()) ||
    job.source_name ||
    'Untitled generation';

  return (
    <div
      role="listitem"
      className={cn(
        'group relative flex items-start gap-3 rounded-lg border border-amber-200/70 bg-amber-50/40 px-3 py-2.5',
        'transition-colors hover:bg-amber-50',
        className,
      )}
    >
      {/* 3px amber stripe down the left edge. Visually anchors the row
          as "this was your decision" rather than a system error. */}
      <span
        aria-hidden
        className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-amber-500"
      />

      <XCircle
        size={20}
        weight="fill"
        className="mt-0.5 flex-shrink-0 text-amber-600"
        aria-hidden
      />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-stone-800" title={subject}>
          {subject}
        </p>
        <p className="mt-0.5 text-[11px] font-serif italic text-stone-600">
          Cancelled{time ? ` · ${time}` : ''}
        </p>
      </div>

      <div className="flex flex-shrink-0 items-center gap-2">
        <button
          type="button"
          onClick={onGenerateAgain}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium',
            'text-amber-700 transition-colors hover:bg-amber-100 hover:text-amber-900',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-1 focus-visible:ring-offset-amber-50',
          )}
          aria-label={`Generate again: ${subject}`}
        >
          <ArrowsClockwise size={12} weight="bold" />
          Generate again
        </button>
        {trailing}
      </div>
    </div>
  );
};
