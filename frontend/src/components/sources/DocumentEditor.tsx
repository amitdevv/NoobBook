/**
 * DocumentEditor — lazy-loaded BlockNote editor used by DocumentEditorTab.
 *
 * Exports a default forwardRef component so the parent can imperatively
 * extract markdown on submit (`getMarkdown`) and clear after a save
 * (`reset`). The editor is uncontrolled — keeping React out of the
 * keystroke path is BlockNote's recommended pattern.
 *
 * BlockNote ships its own CSS for the toolbar / slash menu / drag
 * handles; we import the Mantine theme stylesheet here so the bundle
 * containing this module pulls it in too (kept out of the main bundle
 * thanks to React.lazy in the parent).
 */

import { forwardRef, useImperativeHandle } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import '@blocknote/mantine/style.css';
import type { Block } from '@blocknote/core';
import type { DocumentEditorHandle } from './DocumentEditorTab';

interface DocumentEditorProps {
  disabled: boolean;
}

const DocumentEditor = forwardRef<DocumentEditorHandle, DocumentEditorProps>(
  ({ disabled }, ref) => {
    const editor = useCreateBlockNote();

    useImperativeHandle(
      ref,
      () => ({
        getMarkdown: () => editor.blocksToMarkdownLossy(),
        getInferredName: () => {
          // Walk top-level blocks looking for the first heading; pull
          // its plain text. We avoid scanning the whole tree because
          // BlockNote keeps headings at the top level by default.
          const blocks = editor.document as Block[];
          for (const block of blocks) {
            if (block.type === 'heading') {
              const text = blockToPlainText(block);
              if (text) return text;
            }
          }
          // Fall back to the first non-empty paragraph's text, capped
          // at 60 chars so the source name doesn't become a paragraph.
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
      }),
      [editor],
    );

    return (
      <BlockNoteView
        editor={editor}
        editable={!disabled}
        theme="light"
      />
    );
  },
);

DocumentEditor.displayName = 'DocumentEditor';

export default DocumentEditor;

// BlockNote inline content is a list of styled-text / link nodes; we
// only need the visible characters, not the styling, so flatten.
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
