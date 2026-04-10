/**
 * Export Chat as PDF
 *
 * Converts a chat conversation into a styled PDF with proper rendering of:
 * - Code blocks (dark background, monospace)
 * - Tables (bordered, striped rows)
 * - Blockquotes (amber left border)
 * - Lists, bold, italic, strikethrough
 * - Citations as numbered superscripts with a reference section
 *
 * Uses `marked` for markdown→HTML and `html2pdf.js` for HTML→PDF.
 */

import html2pdf from 'html2pdf.js';
import { Marked } from 'marked';
import { parseCitations } from './citations';
import { sourcesAPI, type ChunkContent } from './api/sources';
import type { Chat } from './api/chats';

// Isolated marked instance so we don't pollute the global singleton.
// Raw HTML rendering is disabled to prevent XSS — any <script>, <img onerror>, etc.
// in message content is escaped instead of injected into the DOM.
const pdfMarked = new Marked({
  gfm: true,
  breaks: true,
  renderer: {
    html({ text }: { text: string }) {
      return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },
  },
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 50);
}

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return (
    date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    }) +
    ' at ' +
    date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// PDF Styles — matches the NoobBook warm amber / stone design system
// ---------------------------------------------------------------------------

const PDF_STYLES = `
  .pdf-export * { margin: 0; padding: 0; box-sizing: border-box; }

  .pdf-export {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: #292524;
    line-height: 1.65;
    font-size: 13.5px;
  }

  /* ── Document header ───────────────────────────────────────── */
  .pdf-export .doc-header { margin-bottom: 22px; }
  .pdf-export .doc-title {
    font-size: 24px;
    font-weight: 700;
    color: #0c0a09;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 3px solid #D97706;
  }
  .pdf-export .doc-meta { color: #78716c; font-size: 11.5px; }
  .pdf-export .doc-meta p { margin: 2px 0; }
  .pdf-export .doc-meta strong { color: #44403c; }

  .pdf-export .separator {
    border: none;
    border-top: 1px solid #e7e5e4;
    margin: 18px 0;
  }

  /* ── Messages ──────────────────────────────────────────────── */
  .pdf-export .message {
    margin-bottom: 18px;
    page-break-inside: avoid;
  }
  .pdf-export .msg-header {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 4px;
  }
  .pdf-export .role { font-weight: 700; font-size: 13px; }
  .pdf-export .role-user { color: #292524; }
  .pdf-export .role-assistant { color: #B45309; }
  .pdf-export .timestamp { font-size: 10.5px; color: #a8a29e; }

  .pdf-export .msg-body {
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 13.5px;
    line-height: 1.7;
  }
  .pdf-export .body-user {
    background: #fafaf9;
    border: 1px solid #e7e5e4;
  }
  .pdf-export .body-assistant {
    background: #fffbeb;
    border: 1px solid #fde68a;
  }

  /* ── Markdown elements inside messages ─────────────────────── */
  .pdf-export .msg-body h1 { font-size: 19px; font-weight: 700; margin: 14px 0 6px; color: #0c0a09; }
  .pdf-export .msg-body h2 { font-size: 16px; font-weight: 600; margin: 12px 0 5px; color: #1c1917; }
  .pdf-export .msg-body h3 { font-size: 14.5px; font-weight: 600; margin: 10px 0 4px; color: #292524; }
  .pdf-export .msg-body h4 { font-size: 13.5px; font-weight: 600; margin: 8px 0 3px; color: #44403c; }

  .pdf-export .msg-body p { margin: 5px 0; }
  .pdf-export .msg-body strong { font-weight: 700; }
  .pdf-export .msg-body em { font-style: italic; }
  .pdf-export .msg-body del { text-decoration: line-through; color: #78716c; }

  /* Code blocks */
  .pdf-export .msg-body pre {
    background: #1c1917;
    color: #e7e5e4;
    padding: 10px 14px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 8px 0;
    font-size: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .pdf-export .msg-body pre code {
    background: none;
    padding: 0;
    color: inherit;
    font-size: inherit;
    border-radius: 0;
  }
  .pdf-export .msg-body code {
    font-family: 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', monospace;
    background: #f5f5f4;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
    color: #c2410c;
  }

  /* Tables */
  .pdf-export .msg-body table {
    border-collapse: collapse;
    width: 100%;
    margin: 8px 0;
    font-size: 12.5px;
  }
  .pdf-export .msg-body th,
  .pdf-export .msg-body td {
    border: 1px solid #d6d3d1;
    padding: 6px 10px;
    text-align: left;
  }
  .pdf-export .msg-body th {
    background: #f5f5f4;
    font-weight: 600;
    color: #1c1917;
  }
  .pdf-export .msg-body tr:nth-child(even) td { background: #fafaf9; }

  /* Blockquotes */
  .pdf-export .msg-body blockquote {
    border-left: 3px solid #D97706;
    padding: 6px 12px;
    margin: 8px 0;
    background: #fffbeb;
    color: #57534e;
    font-style: italic;
  }
  .pdf-export .msg-body blockquote p { margin: 2px 0; }

  /* Lists */
  .pdf-export .msg-body ul, .pdf-export .msg-body ol { padding-left: 22px; margin: 5px 0; }
  .pdf-export .msg-body li { margin: 2px 0; }

  /* Links */
  .pdf-export .msg-body a { color: #D97706; text-decoration: underline; }

  /* Images */
  .pdf-export .msg-body img { max-width: 100%; border-radius: 6px; margin: 6px 0; }

  /* Horizontal rules */
  .pdf-export .msg-body hr { border: none; border-top: 1px solid #e7e5e4; margin: 10px 0; }

  /* ── Citation superscripts ─────────────────────────────────── */
  .pdf-export .cite-ref {
    display: inline;
    font-size: 9.5px;
    font-weight: 700;
    color: #D97706;
    vertical-align: super;
    line-height: 0;
    margin-left: 1px;
  }

  /* ── Citations footer section ──────────────────────────────── */
  .pdf-export .citations-section {
    margin-top: 28px;
    padding-top: 14px;
    border-top: 2px solid #D97706;
  }
  .pdf-export .citations-title {
    font-size: 17px;
    font-weight: 700;
    color: #0c0a09;
    margin-bottom: 10px;
  }
  .pdf-export .cite-entry {
    margin-bottom: 8px;
    padding: 7px 10px;
    background: #fafaf9;
    border-radius: 6px;
    border-left: 3px solid #D97706;
    page-break-inside: avoid;
  }
  .pdf-export .cite-num {
    font-weight: 700;
    color: #D97706;
    font-size: 11.5px;
    margin-right: 4px;
  }
  .pdf-export .cite-source {
    font-weight: 600;
    color: #292524;
    font-size: 12.5px;
  }
  .pdf-export .cite-content {
    color: #57534e;
    font-size: 11.5px;
    margin-top: 3px;
    line-height: 1.5;
  }

  /* ── Footer ────────────────────────────────────────────────── */
  .pdf-export .doc-footer {
    margin-top: 28px;
    padding-top: 10px;
    border-top: 1px solid #e7e5e4;
    text-align: center;
    color: #a8a29e;
    font-size: 10.5px;
  }
`;

// ---------------------------------------------------------------------------
// Main export function
// ---------------------------------------------------------------------------

interface ExportChatOptions {
  chat: Chat;
  projectId: string;
  projectName: string;
}

export async function exportChatAsPdf({
  chat,
  projectId,
  projectName,
}: ExportChatOptions): Promise<void> {
  const messages = chat.messages || [];

  // ── Step 1: Build global citation map across all assistant messages ──
  const globalChunkToFootnote = new Map<string, number>();
  let footnoteCounter = 1;

  for (const msg of messages) {
    if (msg.role !== 'assistant') continue;
    const parsed = parseCitations(msg.content);
    for (const entry of parsed.uniqueCitations) {
      if (!globalChunkToFootnote.has(entry.chunkId)) {
        globalChunkToFootnote.set(entry.chunkId, footnoteCounter++);
      }
    }
  }

  // ── Step 2: Fetch all citation contents in parallel ──
  const citationContents = new Map<string, ChunkContent>();
  const fetchPromises = Array.from(globalChunkToFootnote.keys()).map(
    async (chunkId) => {
      try {
        const content = await sourcesAPI.getCitationContent(projectId, chunkId);
        citationContents.set(chunkId, content);
      } catch {
        // Gracefully skip citations that fail to fetch
      }
    },
  );
  await Promise.all(fetchPromises);

  // ── Step 3: Build the HTML document ──
  const parts: string[] = [];

  parts.push(`<style>${PDF_STYLES}</style>`);

  // Document header
  parts.push(`
    <div class="doc-header">
      <div class="doc-title">${escapeHtml(chat.title || 'Chat Export')}</div>
      <div class="doc-meta">
        <p><strong>Project:</strong> ${escapeHtml(projectName)}</p>
        <p><strong>Created:</strong> ${formatDate(chat.created_at)}</p>
        <p><strong>Exported:</strong> ${formatDate(new Date().toISOString())}</p>
        <p><strong>Messages:</strong> ${messages.length}</p>
      </div>
    </div>
    <hr class="separator">
  `);

  // Messages
  for (const msg of messages) {
    const isUser = msg.role === 'user';
    const roleName = isUser ? 'You' : 'NoobBook';

    // Convert markdown to HTML via marked
    let renderedContent = pdfMarked.parse(msg.content) as string;

    // Replace citation markers with styled superscript references
    if (!isUser && globalChunkToFootnote.size > 0) {
      renderedContent = renderedContent.replace(
        /\[\[cite:([a-zA-Z0-9_-]+_page_\d+_chunk_\d+)\]\]/g,
        (_match: string, chunkId: string) => {
          const num = globalChunkToFootnote.get(chunkId);
          return num ? `<span class="cite-ref">[${num}]</span>` : '';
        },
      );
    }

    parts.push(`
      <div class="message">
        <div class="msg-header">
          <span class="role ${isUser ? 'role-user' : 'role-assistant'}">${roleName}</span>
          <span class="timestamp">${formatDate(msg.timestamp)}</span>
        </div>
        <div class="msg-body ${isUser ? 'body-user' : 'body-assistant'}">
          ${renderedContent}
        </div>
      </div>
    `);
  }

  // Citations section
  if (globalChunkToFootnote.size > 0) {
    parts.push(`<div class="citations-section"><div class="citations-title">Citations</div>`);

    for (const [chunkId, footnoteNum] of globalChunkToFootnote) {
      const citation = citationContents.get(chunkId);
      if (citation) {
        const location =
          citation.chunk_index > 0
            ? `Page ${citation.page_number}, Section ${citation.chunk_index}`
            : `Page ${citation.page_number}`;
        const snippet =
          citation.content.length > 300
            ? citation.content.slice(0, 300) + '...'
            : citation.content;
        parts.push(`
          <div class="cite-entry">
            <span class="cite-num">[${footnoteNum}]</span>
            <span class="cite-source">${escapeHtml(citation.source_name)} — ${location}</span>
            <div class="cite-content">${escapeHtml(snippet)}</div>
          </div>
        `);
      } else {
        parts.push(`
          <div class="cite-entry">
            <span class="cite-num">[${footnoteNum}]</span>
            <span class="cite-source">Citation not available</span>
          </div>
        `);
      }
    }
    parts.push(`</div>`);
  }

  // Footer
  parts.push(`<div class="doc-footer">Exported from NoobBook — noobbooklm.com</div>`);

  // ── Step 4: Render to PDF ──
  // Container must stay in the viewport for html2canvas to render it.
  // We hide it behind everything with z-index instead of moving it offscreen.
  const container = document.createElement('div');
  container.className = 'pdf-export';
  container.innerHTML = parts.join('');
  container.style.position = 'fixed';
  container.style.left = '0';
  container.style.top = '0';
  container.style.width = '180mm';
  container.style.zIndex = '-9999';
  container.style.pointerEvents = 'none';
  document.body.appendChild(container);

  const filename = `${slugify(chat.title || 'chat-export') || 'chat-export'}-${new Date().toISOString().slice(0, 10)}.pdf`;

  try {
    // pagebreak is a valid html2pdf.js option but missing from the bundled types
    await html2pdf()
      .set({
        margin: [12, 15, 12, 15],
        filename,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
        pagebreak: { mode: ['avoid-all', 'css', 'legacy'] },
      } as Record<string, unknown>)
      .from(container)
      .save();
  } finally {
    document.body.removeChild(container);
  }
}
