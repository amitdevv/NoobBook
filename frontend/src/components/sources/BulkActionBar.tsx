/**
 * BulkActionBar — bottom-fixed glass pill that appears when 1+ source
 * is selected. Action grammar: Activate · Deactivate · Delete · Cancel.
 *
 * Visual continuity with the editor's writing-room glass pill: dark
 * stone-900 backdrop instead of light, because this surface lives on
 * top of the workspace not the cream paper, and a dark accent gives
 * it the assertive presence a destructive-capable action bar deserves.
 */
import React from 'react';
import { CheckCircle, XCircle, Trash, X } from '@phosphor-icons/react';

interface BulkActionBarProps {
  count: number;
  onActivate: () => void;
  onDeactivate: () => void;
  onDelete: () => void;
  onCancel: () => void;
  busy?: boolean;
}

export const BulkActionBar: React.FC<BulkActionBarProps> = ({
  count,
  onActivate,
  onDeactivate,
  onDelete,
  onCancel,
  busy,
}) => {
  if (count === 0) return null;

  return (
    <div className="pointer-events-none absolute bottom-3 left-3 right-3 z-30 flex justify-center animate-in fade-in slide-in-from-bottom-4 duration-200">
      <div className="pointer-events-auto inline-flex items-center gap-1 rounded-full bg-stone-900/95 backdrop-blur px-2 py-1.5 text-stone-100 shadow-[0_8px_32px_-12px_rgba(0,0,0,0.4)] ring-1 ring-stone-800/60">
        <span className="px-2.5 py-1 text-[12px] font-mono tabular-nums text-stone-300">
          {count} selected
        </span>
        <span className="h-4 w-px bg-stone-700" />

        <button
          type="button"
          onClick={onActivate}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium text-stone-200 hover:bg-stone-800 hover:text-amber-300 disabled:opacity-40 transition-colors"
        >
          <CheckCircle size={13} weight="bold" />
          Activate
        </button>

        <button
          type="button"
          onClick={onDeactivate}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium text-stone-200 hover:bg-stone-800 hover:text-stone-100 disabled:opacity-40 transition-colors"
        >
          <XCircle size={13} weight="bold" />
          Deactivate
        </button>

        <span className="h-4 w-px bg-stone-700" />

        <button
          type="button"
          onClick={onDelete}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium text-rose-300 hover:bg-rose-500/15 hover:text-rose-200 disabled:opacity-40 transition-colors"
        >
          <Trash size={13} weight="bold" />
          Delete
        </button>

        <span className="h-4 w-px bg-stone-700" />

        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          aria-label="Cancel selection"
          className="inline-flex items-center justify-center rounded-full p-1.5 text-stone-400 hover:bg-stone-800 hover:text-stone-100 transition-colors"
        >
          <X size={13} weight="bold" />
        </button>
      </div>
    </div>
  );
};
