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

import { forwardRef, useEffect, useImperativeHandle, useMemo, useState } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import '@blocknote/mantine/style.css';
import {
  BlockNoteSchema,
  defaultBlockSpecs,
  createCodeBlockSpec,
  type Block,
} from '@blocknote/core';
import { uploadEditorImage } from '@/lib/api/editor';
import { createLogger } from '@/lib/logger';
import {
  EDITOR_LANGUAGE_DISPLAY,
  getEditorHighlighter,
} from './editorHighlighter';

const log = createLogger('document-editor');

export interface DocumentEditorHandle {
  getMarkdown: () => string;
  getInferredName: () => string;
  reset: () => void;
  loadMarkdown: (markdown: string) => void;
  /** Plaintext of the current selection (empty string if none). Used
   *  by the dialog's pill to drive the AI-assist buttons. */
  getSelectedText: () => string;
  /** Replace the current selection inline with the given text.
   *  Multi-paragraph results land as additional blocks after the
   *  selection's anchor. */
  replaceSelectionWith: (text: string) => void;
  /** Append a paragraph at the current cursor (no replacement) —
   *  used by Continue when there's no selection. */
  appendAtCursor: (text: string) => void;
}

interface DocumentEditorProps {
  disabled: boolean;
  projectId: string;
  /** Markdown to seed the editor with on first mount. Used by the
   *  Edit-source flow. The editor is uncontrolled afterwards — this
   *  is read-once. */
  initialMarkdown?: string;
}

const DocumentEditor = forwardRef<DocumentEditorHandle, DocumentEditorProps>(
  ({ disabled, projectId, initialMarkdown }, ref) => {
    // Schema is built once per editor instance: replace the default
    // codeBlock with a Shiki-highlighted variant. Memoised so a
    // parent re-render doesn't churn the editor schema (which would
    // remount every existing block in the document).
    const schema = useMemo(
      () =>
        BlockNoteSchema.create({
          blockSpecs: {
            ...defaultBlockSpecs,
            codeBlock: createCodeBlockSpec({
              defaultLanguage: 'text',
              supportedLanguages: EDITOR_LANGUAGE_DISPLAY,
              createHighlighter: getEditorHighlighter,
            }),
          },
        }),
      [],
    );

    const editor = useCreateBlockNote({
      schema,
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

    // Seed the editor with initialMarkdown on first mount. Living
    // inside DocumentEditor (not the parent dialog) means we run
    // *after* useCreateBlockNote has produced the editor instance,
    // so we don't have to play timeout-games with a forwarded ref
    // that's null until BlockNoteView mounts. Runs once.
    const [seeded, setSeeded] = useState(false);
    useEffect(() => {
      if (seeded || !initialMarkdown) return;
      const blocks = editor.tryParseMarkdownToBlocks(initialMarkdown);
      // tryParseMarkdownToBlocks is synchronous in BlockNote 0.49 but
      // we wrap defensively in case a future version flips it async.
      Promise.resolve(blocks).then((parsed) => {
        editor.replaceBlocks(editor.document, parsed);
        setSeeded(true);
      });
    }, [editor, initialMarkdown, seeded]);

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
          // BlockNote 0.49's tryParseMarkdownToBlocks is synchronous
          // (returns Block[], not Promise<Block[]>) — verified against
          // the package types and the compiled implementation. We
          // wrap with Promise.resolve so a future version that flips
          // to async wouldn't silently no-op.
          const result = editor.tryParseMarkdownToBlocks(markdown);
          Promise.resolve(result).then((blocks) => {
            editor.replaceBlocks(editor.document, blocks);
          });
        },
        getSelectedText: () => editor.getSelectedText() ?? '',
        replaceSelectionWith: (text: string) => {
          // First paragraph replaces the selection inline; if the AI
          // returned multiple paragraphs (`\n\n` separated), the
          // remaining ones are inserted as new blocks after the
          // current cursor block.
          const paragraphs = text.split(/\n{2,}/);
          const [first, ...rest] = paragraphs;
          if (first) {
            editor.insertInlineContent([{ type: 'text', text: first, styles: {} }]);
          }
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
        },
        appendAtCursor: (text: string) => {
          // Used when Continue runs without a selection. We append a
          // new paragraph after the current block so we don't disturb
          // whatever the user was already writing.
          const cursorBlock = editor.getTextCursorPosition().block;
          const paragraphs = text.split(/\n{2,}/);
          editor.insertBlocks(
            paragraphs.map((p) => ({
              type: 'paragraph' as const,
              content: [{ type: 'text' as const, text: p, styles: {} }],
            })),
            cursorBlock,
            'after',
          );
        },
      }),
      [editor],
    );

    // Default formatting toolbar — AI buttons used to live here but
    // are now hosted in the dialog's bottom pill (better
    // discoverability, always visible, no selection required for
    // Continue).
    return <BlockNoteView editor={editor} editable={!disabled} theme="light" />;
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

