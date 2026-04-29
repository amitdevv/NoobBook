/**
 * DocumentEditorDialog — the "writing room" composing surface used by
 * BOTH the Paste tab (create flow) and the source preview's Edit
 * button (edit flow).
 *
 * Aesthetic — "writing room above the workspace":
 *   - No header bar; dialog opens directly to the writing column
 *   - Title is a borderless serif-italic input ('Untitled note')
 *   - Single hairline divider then editor body, both centered at a
 *     680px reading measure with serif body type
 *   - Atmosphere: warm diagonal radial wash + 8% SVG paper grain
 *   - One floating glass pill bottom-right is the only chrome:
 *     word count · '/' commands hint · ⌘↵ Save · Esc discard
 *   - ⌘↵ keyboard shortcut saves; word count auto-updates every 1s
 *
 * The dialog is mode-agnostic — its caller passes `onSave(markdown,
 * name)` and the dialog forwards. Optional `initialMarkdown` /
 * `initialName` prefill the editor for the edit flow. BlockNote is
 * lazy-loaded behind React.lazy so the cost is paid on first open.
 */

import React, { Suspense, useEffect, useRef, useState } from 'react';
import { Dialog, DialogContent, DialogTitle } from '../ui/dialog';
import { ClipboardText, CircleNotch, FloppyDisk } from '@phosphor-icons/react';
import type { DocumentEditorHandle } from './DocumentEditorTab';

const LazyDocumentEditor = React.lazy(() => import('./DocumentEditor'));

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

interface DocumentEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called when the user saves. Caller decides create vs update. */
  onSave: (markdown: string, name: string) => Promise<void>;
  /** Initial markdown body (edit flow). Empty string for create. */
  initialMarkdown?: string;
  /** Initial source name (edit flow). Empty string for create. */
  initialName?: string;
  /** Label on the save action — "Save as source" (create) / "Save changes" (edit). */
  saveLabel?: string;
  /** Disable saving — e.g. project at source limit (create flow only). */
  disabledReason?: string | null;
  /** localStorage key for autosave drafts. When set, the dialog saves
   *  current editor state every ~2s while open and offers a Restore
   *  prompt on next open if a non-empty draft exists. Only set this
   *  for create flows — edit flows would prompt to restore stale work
   *  that conflicts with the source's actual stored content. */
  draftKey?: string | null;
}

interface StoredDraft {
  markdown: string;
  name: string;
  savedAt: number;
}

const DRAFT_NAMESPACE = 'noobbook:doc-editor:draft:';

function loadDraft(key: string): StoredDraft | null {
  try {
    const raw = window.localStorage.getItem(DRAFT_NAMESPACE + key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredDraft;
    if (
      typeof parsed?.markdown === 'string' &&
      typeof parsed?.name === 'string' &&
      typeof parsed?.savedAt === 'number'
    ) {
      return parsed;
    }
  } catch {
    // localStorage can be disabled or full; either way, no draft.
  }
  return null;
}

function saveDraft(key: string, draft: StoredDraft) {
  try {
    window.localStorage.setItem(DRAFT_NAMESPACE + key, JSON.stringify(draft));
  } catch {
    // Quota exceeded etc — silently drop. The user just won't get
    // restore-on-reload for this draft.
  }
}

function clearDraft(key: string) {
  try {
    window.localStorage.removeItem(DRAFT_NAMESPACE + key);
  } catch {
    // ignore
  }
}

function relativeTime(savedAt: number): string {
  const diff = Date.now() - savedAt;
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} min ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} h ago`;
  return `${Math.floor(diff / 86_400_000)} d ago`;
}

export const DocumentEditorDialog: React.FC<DocumentEditorDialogProps> = ({
  open,
  onOpenChange,
  onSave,
  initialMarkdown = '',
  initialName = '',
  saveLabel = 'Save as source',
  disabledReason = null,
  draftKey = null,
}) => {
  const editorRef = useRef<DocumentEditorHandle | null>(null);
  const titleRef = useRef<HTMLInputElement | null>(null);
  const [name, setName] = useState(initialName);
  const [adding, setAdding] = useState(false);
  const [wordCount, setWordCount] = useState(0);
  // Tracks whether the editor has been hydrated with initialMarkdown
  // for this open. Prevents re-hydrating on every render and resets
  // when the dialog closes so the next open starts fresh.
  const [hydrated, setHydrated] = useState(false);
  // Draft restoration — populated on open if a draft exists in
  // localStorage AND we're in create mode (no initialMarkdown). Until
  // the user clicks Restore or Discard, the editor stays empty and
  // the autosave loop is paused so we don't immediately overwrite
  // the saved draft with an empty document.
  const [draftAvailable, setDraftAvailable] = useState<StoredDraft | null>(null);

  const disabled = adding || !!disabledReason;

  // When the dialog opens with initialMarkdown, ask BlockNote to parse
  // and replace its blocks. Runs once per open. The editor handle's
  // `loadMarkdown` is added below in DocumentEditor.tsx.
  useEffect(() => {
    if (!open || hydrated) return;
    setName(initialName);
    if (initialMarkdown && editorRef.current) {
      // Defer to next frame so BlockNote is mounted.
      const id = window.setTimeout(() => {
        editorRef.current?.loadMarkdown?.(initialMarkdown);
        setHydrated(true);
      }, 50);
      return () => window.clearTimeout(id);
    }
    setHydrated(true);
  }, [open, hydrated, initialMarkdown, initialName]);

  // Reset hydration state when dialog closes so the next open starts
  // clean (or re-hydrates with a different source).
  useEffect(() => {
    if (!open) {
      setHydrated(false);
      setWordCount(0);
      setDraftAvailable(null);
    }
  }, [open]);

  // On open, surface a previously-saved draft so the user can choose
  // to restore it. Only runs in create mode (no initialMarkdown) and
  // only when a draftKey was passed — edit flow has its own canonical
  // content and shouldn't fight a stale localStorage draft.
  useEffect(() => {
    if (!open || !draftKey || initialMarkdown) return;
    const existing = loadDraft(draftKey);
    if (existing && existing.markdown.trim().length > 0) {
      setDraftAvailable(existing);
    }
  }, [open, draftKey, initialMarkdown]);

  // Autosave loop — every 2s, snapshot editor state to localStorage.
  // Paused until the user resolves the restore prompt (otherwise the
  // empty doc would overwrite the draft they're about to restore).
  useEffect(() => {
    if (!open || !draftKey || draftAvailable) return;
    const tick = () => {
      const md = editorRef.current?.getMarkdown() ?? '';
      const trimmed = md.trim();
      if (!trimmed) return; // don't write empty drafts
      saveDraft(draftKey, { markdown: md, name, savedAt: Date.now() });
    };
    const id = window.setInterval(tick, 2000);
    return () => window.clearInterval(id);
  }, [open, draftKey, draftAvailable, name]);

  const handleRestoreDraft = () => {
    if (!draftAvailable) return;
    setName(draftAvailable.name);
    editorRef.current?.loadMarkdown(draftAvailable.markdown);
    setDraftAvailable(null);
  };

  const handleDiscardDraft = () => {
    if (draftKey) clearDraft(draftKey);
    setDraftAvailable(null);
  };

  // Poll word count once per second while open. Keeps React out of
  // the keystroke path; cheaper than wiring into BlockNote's change
  // subscription and the latency is fine for an ambient counter.
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

  // Auto-focus the title on open if it's empty (create flow); for
  // edit flow we focus the editor body instead so the user can jump
  // straight back into composing.
  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => {
      if (!initialName) titleRef.current?.focus();
    }, 80);
    return () => window.clearTimeout(t);
  }, [open, initialName]);

  const handleSave = async () => {
    const handle = editorRef.current;
    if (!handle) return;
    const markdown = handle.getMarkdown().trim();
    if (!markdown) return;
    const finalName = name.trim() || handle.getInferredName().trim() || 'Untitled note';

    setAdding(true);
    try {
      await onSave(markdown, finalName);
      handle.reset();
      setName('');
      // The doc is now persisted server-side; toss the local draft so
      // a future open starts clean.
      if (draftKey) clearDraft(draftKey);
      onOpenChange(false);
    } finally {
      setAdding(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      void handleSave();
    }
  };

  const handleOpenChange = (next: boolean) => {
    if (next) {
      onOpenChange(true);
      return;
    }
    if (adding) return;
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        onKeyDown={handleKeyDown}
        className="max-w-[1040px] w-[92vw] h-[88vh] p-0 gap-0 border-stone-200 rounded-2xl overflow-hidden bg-stone-50 [&>button[type=button]]:z-30 [&>button[type=button]]:opacity-50 [&>button[type=button]:hover]:opacity-100"
      >
        <DialogTitle className="sr-only">
          {initialName ? 'Edit document' : 'New document'}
        </DialogTitle>

        {/* Atmosphere — warm diagonal wash + paper grain. */}
        <div
          aria-hidden
          className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_right,rgba(254,243,199,0.55),transparent_60%)]"
        />
        <div
          aria-hidden
          className="absolute inset-0 pointer-events-none opacity-[0.06] mix-blend-multiply"
          style={{ backgroundImage: `url("${PAPER_GRAIN}")`, backgroundSize: '240px 240px' }}
        />

        <div className="relative z-10 flex-1 min-h-0 overflow-y-auto">
          <div className="mx-auto max-w-[680px] px-8 pt-16 pb-32">
            {draftAvailable && (
              <div className="mb-6 rounded-lg border border-amber-200/80 bg-amber-50/80 px-4 py-3 flex items-center gap-3 text-[13px] text-stone-700">
                <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-amber-700">
                  Draft
                </span>
                <span className="flex-1">
                  You have an unsaved draft from {relativeTime(draftAvailable.savedAt)}.
                </span>
                <button
                  type="button"
                  onClick={handleRestoreDraft}
                  className="rounded border border-amber-300 bg-white px-2 py-1 text-[11px] font-medium text-amber-800 hover:bg-amber-100"
                >
                  Restore
                </button>
                <button
                  type="button"
                  onClick={handleDiscardDraft}
                  className="text-[11px] text-stone-500 hover:text-stone-800"
                >
                  Discard
                </button>
              </div>
            )}
            <input
              ref={titleRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={disabled}
              placeholder="Untitled note"
              className="w-full bg-transparent border-0 outline-none ring-0 font-serif italic text-[34px] leading-tight text-stone-900 placeholder:text-stone-300 placeholder:italic focus:outline-none focus:ring-0 px-0"
            />
            <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.2em] text-stone-400">
              {initialName ? 'Editing · Markdown' : 'Draft · Markdown'}
            </div>
            <div className="mt-6 mb-4 border-t border-stone-200/70" />

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

        {/* Floating glass pill — only chrome. */}
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
              onClick={handleSave}
              disabled={disabled || wordCount === 0}
              title={disabledReason ?? undefined}
              className="group inline-flex items-center gap-1.5 text-[11px] font-medium text-stone-700 hover:text-amber-700 disabled:text-stone-400 disabled:hover:text-stone-400 transition"
            >
              {adding ? (
                <>
                  <CircleNotch size={11} className="animate-spin" />
                  Saving
                </>
              ) : initialName ? (
                <>
                  <FloppyDisk size={12} weight="bold" className="text-stone-500 group-hover:text-amber-700" />
                  <kbd className="rounded border border-stone-300 bg-stone-50 px-1 font-mono text-[10px] text-stone-700 group-hover:border-amber-300 group-hover:bg-amber-50">
                    ⌘↵
                  </kbd>
                  {saveLabel}
                </>
              ) : (
                <>
                  <ClipboardText size={12} weight="bold" className="text-stone-500 group-hover:text-amber-700" />
                  <kbd className="rounded border border-stone-300 bg-stone-50 px-1 font-mono text-[10px] text-stone-700 group-hover:border-amber-300 group-hover:bg-amber-50">
                    ⌘↵
                  </kbd>
                  {saveLabel}
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
  );
};
