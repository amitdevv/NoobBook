/**
 * DocumentEditorTab — replaces the plain-textarea PasteTab with a
 * Notion-style block editor (BlockNote). On submit, the editor doc is
 * serialized to markdown and posted through the existing addTextSource
 * API — the backend pipeline treats markdown as `.txt` and the rest of
 * the chunking + embedding flow is unchanged.
 *
 * BlockNote (~200KB gz) is lazy-loaded behind React.lazy so the cost is
 * paid only when a user actually opens the Add Sources sheet and lands
 * on this tab.
 */

import React, { Suspense, useRef, useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ClipboardText, CircleNotch } from '@phosphor-icons/react';

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
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium mb-2 block">Source Name</label>
        <Input
          placeholder="Auto-detected from the first heading if left blank"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={disabled}
        />
      </div>

      <div>
        <label className="text-sm font-medium mb-2 block">Content</label>
        <div className="rounded-md border bg-background">
          <Suspense
            fallback={
              <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
                <CircleNotch size={16} className="mr-2 animate-spin" />
                Loading editor…
              </div>
            }
          >
            <LazyDocumentEditor ref={editorRef} disabled={disabled} />
          </Suspense>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Type <kbd className="px-1 rounded border text-[10px]">/</kbd> for headings,
          lists, quotes, code, links, and embeds.
        </p>
      </div>

      <Button className="w-full" onClick={handleAdd} disabled={disabled}>
        {adding ? (
          <>
            <CircleNotch size={16} className="mr-2 animate-spin" />
            Adding...
          </>
        ) : (
          <>
            <ClipboardText size={16} className="mr-2" />
            Add Document
          </>
        )}
      </Button>
    </div>
  );
};
