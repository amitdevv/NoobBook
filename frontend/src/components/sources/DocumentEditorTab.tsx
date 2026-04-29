/**
 * DocumentEditorTab — Paste-tab launcher.
 *
 * The tab body is a single CTA card. Clicking opens
 * DocumentEditorDialog in "create" mode; on save we hand the markdown
 * + chosen name back to the existing addTextSource flow.
 *
 * The actual writing surface lives in DocumentEditorDialog so it can
 * be reused by the source preview's Edit flow.
 */

import React, { useState } from 'react';
import { ClipboardText, ArrowsOut } from '@phosphor-icons/react';
import { DocumentEditorDialog } from './DocumentEditorDialog';

// Re-export for backward-compat with anyone importing the handle type
// from this module's old location.
export type { DocumentEditorHandle } from './DocumentEditor';

interface DocumentEditorTabProps {
  onAddText: (content: string, name: string) => Promise<void>;
  isAtLimit: boolean;
}

export const DocumentEditorTab: React.FC<DocumentEditorTabProps> = ({
  onAddText,
  isAtLimit,
}) => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={isAtLimit}
        className="group w-full rounded-xl border border-dashed border-stone-300 bg-gradient-to-br from-stone-50 to-amber-50/30 px-6 py-10 text-left transition hover:border-amber-400 hover:from-amber-50/40 hover:to-amber-50/60 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <div className="flex items-start gap-4">
          <div className="rounded-lg bg-white border border-stone-200 p-2.5 shadow-sm group-hover:border-amber-300">
            <ClipboardText size={22} className="text-amber-700" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-base font-medium text-stone-900">Open Document Editor</p>
            <p className="mt-1 text-sm text-stone-600 leading-relaxed">
              Compose with headings, lists, quotes, code, links, and embeds.
              Type <kbd className="px-1 rounded border bg-white text-[10px]">/</kbd> for the slash menu.
            </p>
            <p className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 group-hover:text-amber-800">
              <ArrowsOut size={12} weight="bold" />
              Open in larger window
            </p>
          </div>
        </div>
      </button>

      <DocumentEditorDialog
        open={open}
        onOpenChange={setOpen}
        onSave={async (markdown, name) => {
          await onAddText(markdown, name);
        }}
        saveLabel="Save as source"
        disabledReason={isAtLimit ? 'Source limit reached' : null}
      />
    </>
  );
};
