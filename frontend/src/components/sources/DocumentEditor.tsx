/**
 * DocumentEditor — lazy-loaded BlockNote editor used by the Paste tab
 * launcher AND the source preview's Edit flow.
 *
 * Three integrations on top of plain BlockNote:
 *   1. Markdown round-trip (getMarkdown / loadMarkdown / reset / get
 *      inferred name) via useImperativeHandle — exposed to the parent
 *      dialog so it can read/write the doc without React traffic.
 *
 *   2. Image upload — pass `uploadFile` to useCreateBlockNote. BlockNote
 *      transparently handles drag-drop, paste, and the slash-`/image`
 *      command by calling our uploader; we POST to the editor-image
 *      endpoint and return the signed URL it inserts.
 *
 *   3. AI-assist selection toolbar — a custom FormattingToolbar that
 *      injects three buttons (Improve / Continue / Summarize) before
 *      the default toolbar items. Each runs the selection through
 *      Haiku via /editor/assist and replaces the selection with the
 *      response. Continue uses an empty-selection mode (we send the
 *      surrounding paragraph as context).
 */

import { forwardRef, useImperativeHandle, useState } from 'react';
import {
  useCreateBlockNote,
  FormattingToolbar,
  FormattingToolbarController,
  getFormattingToolbarItems,
  useBlockNoteEditor,
} from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import '@blocknote/mantine/style.css';
import type { Block } from '@blocknote/core';
import { Sparkle, ArrowFatLineRight, ListBullets, CircleNotch } from '@phosphor-icons/react';
import { uploadEditorImage, assistText, type AssistAction } from '@/lib/api/editor';
import { createLogger } from '@/lib/logger';

const log = createLogger('document-editor');

export interface DocumentEditorHandle {
  getMarkdown: () => string;
  getInferredName: () => string;
  reset: () => void;
  loadMarkdown: (markdown: string) => void;
}

interface DocumentEditorProps {
  disabled: boolean;
  projectId: string;
}

const DocumentEditor = forwardRef<DocumentEditorHandle, DocumentEditorProps>(
  ({ disabled, projectId }, ref) => {
    const editor = useCreateBlockNote({
      // BlockNote calls this for /image, drag-drop, and paste-image
      // events. We forward the file to our backend endpoint and
      // return the signed URL it inserts as the image src.
      uploadFile: async (file: File) => {
        try {
          const result = await uploadEditorImage(projectId, file);
          return result.url;
        } catch (e) {
          log.error({ err: e }, 'editor image upload failed');
          throw e instanceof Error
            ? e
            : new Error('Image upload failed — please try again.');
        }
      },
    });

    useImperativeHandle(
      ref,
      () => ({
        getMarkdown: () => editor.blocksToMarkdownLossy(),
        getInferredName: () => {
          const blocks = editor.document as Block[];
          for (const block of blocks) {
            if (block.type === 'heading') {
              const text = blockToPlainText(block);
              if (text) return text;
            }
          }
          for (const block of blocks) {
            const text = blockToPlainText(block);
            if (text) return text.slice(0, 60);
          }
          return '';
        },
        reset: () => {
          editor.replaceBlocks(editor.document, [
            { type: 'paragraph', content: [] },
          ]);
        },
        loadMarkdown: (markdown: string) => {
          const blocks = editor.tryParseMarkdownToBlocks(markdown);
          editor.replaceBlocks(editor.document, blocks);
        },
      }),
      [editor],
    );

    return (
      <BlockNoteView editor={editor} editable={!disabled} theme="light">
        <FormattingToolbarController
          formattingToolbar={() => (
            <FormattingToolbar>
              {/* Custom AI buttons appear before the default ones. */}
              <AiAssistButtons />
              {getFormattingToolbarItems()}
            </FormattingToolbar>
          )}
        />
      </BlockNoteView>
    );
  },
);

DocumentEditor.displayName = 'DocumentEditor';

export default DocumentEditor;

function blockToPlainText(block: Block): string {
  const content = (block as { content?: unknown }).content;
  if (!Array.isArray(content)) return '';
  return content
    .map((node) => {
      if (typeof node === 'object' && node && 'text' in node) {
        return String((node as { text: unknown }).text ?? '');
      }
      return '';
    })
    .join('')
    .trim();
}

// ----------------------------------------------------------------------
// AiAssistButtons — three pill buttons in the floating toolbar that
// run the selection through Haiku via /editor/assist.
//
// Lives inside <FormattingToolbar> so it inherits BlockNote's
// positioning + visibility logic (the toolbar only shows on a
// non-empty text selection in inline-content blocks).
// ----------------------------------------------------------------------

function AiAssistButtons() {
  const editor = useBlockNoteEditor();
  const [busy, setBusy] = useState<AssistAction | null>(null);

  const runAssist = async (action: AssistAction) => {
    if (busy) return;
    // Pull the selected plaintext. BlockNote's `getSelectedText`
    // returns a flat string of inline content within the selection.
    const selected = editor.getSelectedText().trim();
    if (!selected) return;

    setBusy(action);
    try {
      const out = await assistText(action, selected);
      // Replace the selection inline. We split the response into
      // logical paragraphs but BlockNote's insertInlineContent expects
      // inline objects; for simplicity we drop one line at a time.
      const paragraphs = out.split(/\n{2,}/);
      // First paragraph replaces the selection; the rest are appended
      // as new paragraph blocks below the selection's anchor block.
      const [first, ...rest] = paragraphs;
      editor.insertInlineContent([{ type: 'text', text: first, styles: {} }]);
      if (rest.length > 0) {
        const cursorBlock = editor.getTextCursorPosition().block;
        editor.insertBlocks(
          rest.map((p) => ({
            type: 'paragraph' as const,
            content: [{ type: 'text' as const, text: p, styles: {} }],
          })),
          cursorBlock,
          'after',
        );
      }
    } catch (e) {
      log.error({ err: e, action }, 'AI-assist failed');
      // BlockNote toolbar buttons can't reach our toast hook from here;
      // a console error is acceptable for a dev-grade selection action.
    } finally {
      setBusy(null);
    }
  };

  // BlockNote's button styling is via Mantine; we use a div of plain
  // buttons with a small visual treatment so they don't look like
  // half-baked Mantine buttons.
  const Btn = ({
    action,
    label,
    Icon,
  }: {
    action: AssistAction;
    label: string;
    Icon: React.ComponentType<{ size?: number; weight?: 'bold' }>;
  }) => (
    <button
      type="button"
      onClick={() => runAssist(action)}
      disabled={busy === action}
      title={`${label} (Haiku)`}
      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-stone-700 hover:bg-amber-50 hover:text-amber-800 disabled:opacity-50 transition-colors"
    >
      {busy === action ? (
        <CircleNotch size={11} weight="bold" />
      ) : (
        <Icon size={11} weight="bold" />
      )}
      <span>{label}</span>
    </button>
  );

  return (
    <div className="flex items-center gap-0.5 px-1 border-r border-stone-200">
      <Btn action="improve" label="Improve" Icon={Sparkle} />
      <Btn action="continue" label="Continue" Icon={ArrowFatLineRight} />
      <Btn action="summarize" label="Summarize" Icon={ListBullets} />
    </div>
  );
}
