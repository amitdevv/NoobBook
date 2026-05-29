import {
  FileText,
  FilePdf,
  FileDoc,
  FilePpt,
  FileCsv,
  FileXls,
  FileHtml,
  FilePng,
  FileJpg,
  MarkdownLogo,
  File,
  MusicNote,
  Image,
  Table,
  Link,
  YoutubeLogo,
  Plug,
  NotionLogo,
} from '@phosphor-icons/react';
import type { Source } from '../../lib/api/sources';

/**
 * Resolve the Phosphor icon for a source.
 *
 * Extension comes from source.name first: it persists across every status
 * transition, whereas embedding_info.file_extension is overwritten with
 * embedding stats once processing completes (so it's only reliable on fresh
 * uploads). The backend `type` field collapses all documents to "DOCUMENT",
 * so it can't distinguish PDF/DOCX/PPTX — it's the fallback for non-file
 * sources (URLs, pasted text) that have no extension.
 */
export const getSourceIcon = (source: Source): typeof File => {
  const name = source.name || '';
  const lastDot = name.lastIndexOf('.');
  const nameExtension = lastDot > 0 ? name.substring(lastDot).toLowerCase() : '';
  const embeddingExtension = ((source.embedding_info as Record<string, string>)?.file_extension || '').toLowerCase();
  const fileExtension = nameExtension || embeddingExtension;

  switch (fileExtension) {
    case '.pdf': return FilePdf;
    case '.docx': return FileDoc;
    case '.pptx': return FilePpt;
    case '.txt': return FileText;
    case '.csv': return FileCsv;
    case '.xlsx': return FileXls;
    case '.database': return Table;
    case '.mcp': return Plug;
    case '.notion': return NotionLogo;
    case '.md': return MarkdownLogo;
    case '.html': return FileHtml;
    case '.json': case '.xml': return FileText;
    case '.mp3': case '.wav': case '.m4a': case '.aac': case '.flac': return MusicNote;
    case '.jpg': case '.jpeg': return FileJpg;
    case '.png': return FilePng;
    case '.gif': case '.webp': return Image;
  }

  switch (source.type || '') {
    case 'YOUTUBE': return YoutubeLogo;
    case 'LINK': case 'RESEARCH': return Link;
    case 'TEXT': return FileText;
    case 'AUDIO': return MusicNote;
    case 'IMAGE': return Image;
    case 'DATA': return Table;
    case 'DATABASE': return Table;
    case 'MCP': return Plug;
    case 'NOTION': return NotionLogo;
    case 'DOCUMENT': return FileText;
    default: return File;
  }
};
