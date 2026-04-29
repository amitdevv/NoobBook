/**
 * DocumentEditorTab — replaces the plain-textarea PasteTab with a
 * Notion-style block editor (BlockNote).
 *
 * The 600px-wide Add Sources sheet is too narrow for a real writing
 * surface — long pasted markdown overflows and there's no internal
 * scroll. So the Paste tab body is a *launcher*: clicking the big CTA
 * opens the editor in a centered Dialog that overlays the sheet,
 * giving the user a full-width composing surface. Submit from the
 * dialog runs the existing addTextSource flow and closes the dialog.
 *
 * BlockNote (~350KB gz) is lazy-loaded behind React.lazy and only
 * mounts once the dialog opens, so the cost is paid on intent.
 */

import React, { Suspense, useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ClipboardText, CircleNotch, ArrowsOut } from '@phosphor-icons/react';

export interface DocumentEditorHandle {
  /** Serialize the current editor doc to markdown (lossy on unsupported nodes). */
  getMarkdown: () => string;
  /** Best-effort title taken from the first heading block, or empty. */
  getInferredName: () => string;
  /** Reset the editor to a single empty paragraph. */
  reset: () => void;
}

const LazyDocumentEditor = React.lazy(() => import('./DocumentEditor'));

interface DocumentEditorTabProps {
  onAddText: (content: string, name: string) => Promise<void>;
  isAtLimit: boolean;
}

export const DocumentEditorTab: React.FC<DocumentEditorTabProps> = ({
  onAddText,
  isAtLimit,
}) => {
  const [open, setOpen] = useState(false);
  const editorRef = useRef<DocumentEditorHandle | null>(null);
  const [name, setName] = useState('');
  const [adding, setAdding] = useState(false);
  const disabled = isAtLimit || adding;

  const handleAdd = async () => {
    const handle = editorRef.current;
    if (!handle) return;

    const markdown = handle.getMarkdown().trim();
    if (!markdown) return;

    const finalName = name.trim() || handle.getInferredName().trim() || 'Untitled note';

    setAdding(true);
    try {
      await onAddText(markdown, finalName);
      setName('');
      handle.reset();
      setOpen(false);
    } finally {
      setAdding(false);
    }
  };

  // Discard-without-save closes the dialog and resets the form so the
  // next open starts blank. The editor instance is unmounted along
  // with the dialog so we don't need to manually call reset() here.
  const handleOpenChange = (next: boolean) => {
    if (next) {
      setOpen(true);
      return;
    }
    if (adding) return; // don't dismiss mid-submit
    setOpen(false);
    setName('');
  };

  return (
    <>
      <div className="space-y-4">
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
              <p className="text-base font-medium text-stone-900">
                Open Document Editor
              </p>
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
      </div>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-w-4xl w-[92vw] h-[85vh] p-0 gap-0 flex flex-col bg-stone-50 overflow-hidden">
          <DialogHeader className="flex-shrink-0 border-b border-stone-200 bg-white px-6 py-4">
            <DialogTitle className="text-base font-medium text-stone-900">
              New document
            </DialogTitle>
          </DialogHeader>

          <div className="flex-shrink-0 border-b border-stone-200 bg-white px-6 py-3">
            <label className="text-xs font-medium text-stone-500 uppercase tracking-wider mb-1.5 block">
              Source name
            </label>
            <Input
              placeholder="Auto-detected from the first heading if left blank"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={adding}
              className="h-9 border-stone-200 focus-visible:ring-1 focus-visible:ring-amber-300"
            />
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto bg-white">
            <Suspense
              fallback={
                <div className="h-full flex items-center justify-center text-sm text-stone-500">
                  <CircleNotch size={16} className="mr-2 animate-spin" />
                  Loading editor…
                </div>
              }
            >
              <LazyDocumentEditor ref={editorRef} disabled={adding} />
            </Suspense>
          </div>

          <div className="flex-shrink-0 flex items-center justify-end gap-2 border-t border-stone-200 bg-white px-6 py-3">
            <Button
              variant="ghost"
              onClick={() => handleOpenChange(false)}
              disabled={adding}
            >
              Cancel
            </Button>
            <Button onClick={handleAdd} disabled={disabled}>
              {adding ? (
                <>
                  <CircleNotch size={16} className="mr-2 animate-spin" />
                  Adding…
                </>
              ) : (
                <>
                  <ClipboardText size={16} className="mr-2" />
                  Add Document
                </>
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
