/**
 * DocumentEditorTab — Notion-style block editor (BlockNote) wrapped in
 * a centered Dialog that opens above the Add Sources sheet.
 *
 * Aesthetic — "writing room above the workspace":
 *   - No visible header bar; the dialog feels like a notebook page
 *   - Title is a borderless serif-italic input that sits where a
 *     magazine column-head would (no label, no background)
 *   - Single hairline divider separates the title from the editor body
 *   - One floating glass pill in the bottom-right is the only chrome:
 *     word count, slash hint, ⌘↵ save, Esc discard
 *   - Warm cream paper feel via diagonal gradient + 8% SVG-noise
 *
 * BlockNote (~350KB gz) is lazy-loaded behind React.lazy so the cost
 * is paid on intent.
 */

import React, { Suspense, useEffect, useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '../ui/dialog';
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

// Inline SVG → data URI for a low-frequency turbulence noise. Used as
// a paper-grain overlay; keeps the asset out of the repo and avoids
// an extra HTTP request.
const PAPER_GRAIN =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240">
       <filter id="n">
         <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch"/>
         <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.45 0"/>
       </filter>
       <rect width="100%" height="100%" filter="url(#n)" opacity="0.55"/>
     </svg>`,
  );

export const DocumentEditorTab: React.FC<DocumentEditorTabProps> = ({
  onAddText,
  isAtLimit,
}) => {
  const [open, setOpen] = useState(false);
  const editorRef = useRef<DocumentEditorHandle | null>(null);
  const titleRef = useRef<HTMLInputElement | null>(null);
  const [name, setName] = useState('');
  const [adding, setAdding] = useState(false);
  const [wordCount, setWordCount] = useState(0);

  const disabled = isAtLimit || adding;

  // Keep word-count in sync without React-rendering on every keystroke.
  // We poll the editor's serialized output once per second while the
  // dialog is open — cheap enough and avoids wiring into BlockNote's
  // change subscription (which would tie us to its event API).
  useEffect(() => {
    if (!open) return;
    const tick = () => {
      const md = editorRef.current?.getMarkdown() ?? '';
      const words = md.trim() ? md.trim().split(/\s+/).length : 0;
      setWordCount(words);
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [open]);

  // Focus the title field on open so the user can start typing
  // immediately without a click.
  useEffect(() => {
    if (open) {
      const t = window.setTimeout(() => titleRef.current?.focus(), 80);
      return () => window.clearTimeout(t);
    }
  }, [open]);

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

  // ⌘↵ saves, Esc closes (Esc is also the dialog's default).
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      void handleAdd();
    }
  };

  const handleOpenChange = (next: boolean) => {
    if (next) {
      setOpen(true);
      return;
    }
    if (adding) return;
    setOpen(false);
    setName('');
    setWordCount(0);
  };

  return (
    <>
      {/* Launcher CTA — the only thing inside the AddSources sheet for
          the Paste tab. Clicking it opens the writing room above. */}
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

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent
          onKeyDown={handleKeyDown}
          // The shadcn DialogContent renders its own close X at top-4
          // right-4. We let it through, just gentle the styling so it
          // sits on top of the gradient/grain layers without a halo.
          className="max-w-[1040px] w-[92vw] h-[88vh] p-0 gap-0 border-stone-200 rounded-2xl overflow-hidden bg-stone-50 [&>button[type=button]]:z-30 [&>button[type=button]]:opacity-50 [&>button[type=button]:hover]:opacity-100"
        >
          <DialogTitle className="sr-only">New document</DialogTitle>

          {/* Atmosphere layers — diagonal warm wash + paper grain. The
              grain image is positioned absolutely so it doesn't shift
              with scroll. */}
          <div
            aria-hidden
            className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_right,rgba(254,243,199,0.55),transparent_60%)]"
          />
          <div
            aria-hidden
            className="absolute inset-0 pointer-events-none opacity-[0.06] mix-blend-multiply"
            style={{ backgroundImage: `url("${PAPER_GRAIN}")`, backgroundSize: '240px 240px' }}
          />

          {/* Scrollable writing surface. Centered measure of text +
              generous top space so the title doesn't kiss the edge. */}
          <div className="relative z-10 flex-1 min-h-0 overflow-y-auto">
            <div className="mx-auto max-w-[680px] px-8 pt-16 pb-32">
              {/* Title as inline document head — borderless, italic
                  serif. Magazine column-head feel. */}
              <input
                ref={titleRef}
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={adding}
                placeholder="Untitled note"
                className="w-full bg-transparent border-0 outline-none ring-0 font-serif italic text-[34px] leading-tight text-stone-900 placeholder:text-stone-300 placeholder:italic focus:outline-none focus:ring-0 px-0"
              />

              <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.2em] text-stone-400">
                Draft · Markdown
              </div>

              <div className="mt-6 mb-4 border-t border-stone-200/70" />

              {/* Editor body. The DocumentEditor's BlockNote view fills
                  whatever container it's given and inherits typography
                  from this column. */}
              <div className="font-serif text-[17px] leading-[1.75] text-stone-800">
                <Suspense
                  fallback={
                    <div className="h-64 flex items-center justify-center text-sm text-stone-500">
                      <CircleNotch size={16} className="mr-2 animate-spin" />
                      Loading editor…
                    </div>
                  }
                >
                  <LazyDocumentEditor ref={editorRef} disabled={adding} />
                </Suspense>
              </div>
            </div>
          </div>

          {/* The single persistent piece of chrome. Glassmorphic pill
              in the bottom-right with word count, slash hint, and the
              two real keyboard shortcuts. ⌘↵ is also the save trigger. */}
          <div className="absolute bottom-5 right-5 z-20">
            <div className="flex items-center gap-3 rounded-full border border-stone-200/80 bg-white/85 backdrop-blur px-4 py-2 shadow-[0_4px_24px_-12px_rgba(0,0,0,0.12)]">
              <span className="font-mono text-[11px] tabular-nums text-stone-600">
                {wordCount.toLocaleString()} {wordCount === 1 ? 'word' : 'words'}
              </span>
              <span className="h-3 w-px bg-stone-200" />
              <span className="text-[11px] text-stone-500">
                <kbd className="font-mono text-stone-700">/</kbd> commands
              </span>
              <span className="h-3 w-px bg-stone-200" />
              <button
                type="button"
                onClick={handleAdd}
                disabled={disabled || wordCount === 0}
                className="group inline-flex items-center gap-1.5 text-[11px] font-medium text-stone-700 hover:text-amber-700 disabled:text-stone-400 disabled:hover:text-stone-400 transition"
              >
                {adding ? (
                  <>
                    <CircleNotch size={11} className="animate-spin" />
                    Saving
                  </>
                ) : (
                  <>
                    <kbd className="rounded border border-stone-300 bg-stone-50 px-1 font-mono text-[10px] text-stone-700 group-hover:border-amber-300 group-hover:bg-amber-50">
                      ⌘↵
                    </kbd>
                    Save as source
                  </>
                )}
              </button>
              <span className="h-3 w-px bg-stone-200" />
              <button
                type="button"
                onClick={() => handleOpenChange(false)}
                disabled={adding}
                className="text-[11px] text-stone-500 hover:text-stone-800 transition"
              >
                <kbd className="rounded border border-stone-300 bg-stone-50 px-1 font-mono text-[10px] text-stone-700 mr-1">
                  Esc
                </kbd>
                discard
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
