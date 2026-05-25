/**
 * ActivityFeed — dev-only inline panel showing every tool call Claude
 * makes during a chat turn (main-chat tools + nested analyzer-agent
 * inner tools).
 *
 * Rendered above the streaming assistant message. Two states:
 *   - In-flight: each tool starts as a spinning row, flips to a check
 *     or X when its `end` event arrives. Sticks expanded so the user
 *     can watch progress.
 *   - Completed (turn done): auto-collapses to a "Used N tools" pill.
 *     Click to expand and review.
 *
 * Persistence: this version is LIVE-ONLY. Once the turn finishes and
 * the parent unmounts (e.g. on navigation), the feed is gone. A
 * persisted variant would lazy-load /raw and rebuild events from
 * tool_use/tool_result pairs — TODO for a follow-up.
 *
 * Gated by `useDevFlag('tool_activity_feed')` in the caller — never
 * render this without checking the flag, otherwise regular users see
 * developer internals.
 */

import React, { useMemo, useState } from 'react';
import {
  CaretDown,
  CaretRight,
  Check,
  CircleNotch,
  X,
  Wrench,
} from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import type { ToolEventPayload } from '@/lib/api/chats';

interface ActivityRow {
  tool_id: string;
  parent_tool_id?: string;
  name: string;
  input?: Record<string, unknown>;
  result_preview?: string;
  duration_ms?: number;
  status: 'running' | 'done' | 'error';
  children: ActivityRow[];
}

interface ActivityFeedProps {
  events: ToolEventPayload[];
  /** True while the turn is still streaming. Drives auto-collapse. */
  inFlight: boolean;
}

/**
 * Fold a flat stream of start/end events into a parent/child tree.
 *
 * Events without a `tool_id` are dropped — they can't be tracked or
 * updated. (Shouldn't happen in practice; backend always stamps one.)
 */
function buildTree(events: ToolEventPayload[]): ActivityRow[] {
  const byId = new Map<string, ActivityRow>();
  const roots: ActivityRow[] = [];

  for (const ev of events) {
    if (!ev.tool_id) continue;

    let row = byId.get(ev.tool_id);
    if (!row) {
      row = {
        tool_id: ev.tool_id,
        parent_tool_id: ev.parent_tool_id,
        name: ev.name,
        status: 'running',
        children: [],
      };
      byId.set(ev.tool_id, row);
      // Attach to parent if known, else root. If the parent hasn't
      // arrived yet (rare — events can reorder), reparent later by
      // walking the map; for now, push to roots and let the next
      // event with the parent id correct it.
      if (ev.parent_tool_id && byId.has(ev.parent_tool_id)) {
        byId.get(ev.parent_tool_id)!.children.push(row);
      } else {
        roots.push(row);
      }
    }

    if (ev.phase === 'start') {
      if (ev.input !== undefined) row.input = ev.input;
    } else if (ev.phase === 'end' || ev.phase === 'error') {
      row.status = ev.is_error || ev.phase === 'error' ? 'error' : 'done';
      if (ev.result_preview !== undefined) row.result_preview = ev.result_preview;
      if (ev.duration_ms !== undefined) row.duration_ms = ev.duration_ms;
    }
  }

  // Second pass: any row whose parent showed up after it should be
  // moved out of roots. Cheap because the trees are small (≤ 50 rows).
  return roots.filter((r) => {
    if (r.parent_tool_id && byId.has(r.parent_tool_id)) {
      const parent = byId.get(r.parent_tool_id)!;
      if (!parent.children.includes(r)) parent.children.push(r);
      return false;
    }
    return true;
  });
}

function countAll(rows: ActivityRow[]): number {
  let n = 0;
  for (const r of rows) n += 1 + countAll(r.children);
  return n;
}

function formatDuration(ms?: number): string {
  if (ms === undefined) return '';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

const ToolRow: React.FC<{ row: ActivityRow; depth: number }> = ({ row, depth }) => {
  const [expanded, setExpanded] = useState(false);
  const hasDetails =
    !!row.input ||
    !!row.result_preview ||
    row.children.length > 0;

  const statusIcon = () => {
    if (row.status === 'running') {
      return (
        <CircleNotch
          size={14}
          weight="bold"
          className="animate-spin text-amber-600 shrink-0"
        />
      );
    }
    if (row.status === 'error') {
      return <X size={14} weight="bold" className="text-red-600 shrink-0" />;
    }
    return <Check size={14} weight="bold" className="text-emerald-600 shrink-0" />;
  };

  // Render a compact one-line summary of the input (e.g. query="...").
  // Falls back to the bare tool name if no input or only opaque ids.
  const inputSummary = useMemo(() => {
    if (!row.input) return null;
    const entries = Object.entries(row.input);
    if (entries.length === 0) return null;
    // Prefer human-readable fields first; ids are noisy.
    const ordered = [...entries].sort(([a], [b]) => {
      const score = (k: string) =>
        /id$|uuid/i.test(k) ? 1 : /query|keyword|message|sql|input/i.test(k) ? -1 : 0;
      return score(a) - score(b);
    });
    return ordered
      .slice(0, 2)
      .map(([k, v]) => {
        const str =
          typeof v === 'string' ? v : JSON.stringify(v);
        const trimmed = str.length > 60 ? str.slice(0, 60) + '…' : str;
        return `${k}=${typeof v === 'string' ? `"${trimmed}"` : trimmed}`;
      })
      .join('  ');
  }, [row.input]);

  return (
    <div>
      <button
        type="button"
        onClick={() => hasDetails && setExpanded((e) => !e)}
        className={cn(
          'flex w-full items-center gap-2 rounded px-1.5 py-1 text-left',
          'font-mono text-[11px] text-stone-700',
          hasDetails && 'hover:bg-stone-100 cursor-pointer',
          !hasDetails && 'cursor-default',
        )}
        style={{ paddingLeft: depth * 14 + 6 }}
        aria-expanded={expanded}
      >
        {hasDetails ? (
          expanded ? (
            <CaretDown size={10} className="text-stone-400 shrink-0" />
          ) : (
            <CaretRight size={10} className="text-stone-400 shrink-0" />
          )
        ) : (
          <span className="w-[10px] shrink-0" />
        )}
        {statusIcon()}
        <span className="font-medium text-stone-800 shrink-0">{row.name}</span>
        {inputSummary && (
          <span className="truncate text-stone-500">{inputSummary}</span>
        )}
        {row.duration_ms !== undefined && (
          <span className="ml-auto text-stone-400 shrink-0">
            {formatDuration(row.duration_ms)}
          </span>
        )}
      </button>

      {expanded && hasDetails && (
        <div
          className="mt-0.5 mb-1 rounded border border-stone-200 bg-stone-50 px-2 py-1.5 font-mono text-[10.5px] text-stone-700"
          style={{ marginLeft: depth * 14 + 26 }}
        >
          {row.input && (
            <div className="mb-1.5">
              <div className="mb-0.5 text-[9.5px] uppercase tracking-wide text-stone-400">
                Input
              </div>
              <pre className="whitespace-pre-wrap break-all text-stone-800">
                {JSON.stringify(row.input, null, 2)}
              </pre>
            </div>
          )}
          {row.result_preview && (
            <div>
              <div className="mb-0.5 text-[9.5px] uppercase tracking-wide text-stone-400">
                Result
              </div>
              <pre className="whitespace-pre-wrap break-all text-stone-800">
                {row.result_preview}
              </pre>
            </div>
          )}
        </div>
      )}

      {row.children.length > 0 && (
        <div>
          {row.children.map((child) => (
            <ToolRow key={child.tool_id} row={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
};

export const ActivityFeed: React.FC<ActivityFeedProps> = ({ events, inFlight }) => {
  const rows = useMemo(() => buildTree(events), [events]);
  const total = useMemo(() => countAll(rows), [rows]);

  // Auto-collapse once the turn finishes. User can re-expand for review.
  // Stays expanded while in-flight so the user can watch progress.
  const [open, setOpen] = useState(true);
  React.useEffect(() => {
    if (!inFlight && total > 0) setOpen(false);
  }, [inFlight, total]);

  if (rows.length === 0) return null;

  return (
    <div className="mb-2 max-w-[640px] rounded-md border border-stone-200 bg-white/60">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-[11px] text-stone-600 hover:bg-stone-50"
        aria-expanded={open}
      >
        {open ? (
          <CaretDown size={11} className="text-stone-400" />
        ) : (
          <CaretRight size={11} className="text-stone-400" />
        )}
        <Wrench size={12} className="text-stone-500" />
        <span className="font-medium text-stone-700">
          {inFlight ? 'Running tools' : `Used ${total} tool${total === 1 ? '' : 's'}`}
        </span>
        {inFlight && (
          <CircleNotch
            size={11}
            weight="bold"
            className="ml-1 animate-spin text-amber-600"
          />
        )}
      </button>

      {open && (
        <div className="border-t border-stone-200 px-1.5 py-1.5">
          {rows.map((row) => (
            <ToolRow key={row.tool_id} row={row} depth={0} />
          ))}
        </div>
      )}
    </div>
  );
};
