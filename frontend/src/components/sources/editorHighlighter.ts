/**
 * Lazy Shiki highlighter for the BlockNote in-editor code block.
 *
 * BlockNote's `createCodeBlockSpec({ createHighlighter })` accepts a
 * thunk that returns a Promise<Highlighter>. We use a module-level
 * singleton so that mounting the editor twice (e.g. opening the
 * paste tab, closing, opening the preview's edit dialog) only spins
 * up Shiki once.
 *
 * Language registry mirrors the preview-side `react-syntax-highlighter`
 * registry in CodeBlock.tsx so the in-editor and preview-rendered
 * code surfaces look consistent.
 */
import type { Highlighter } from 'shiki';

let highlighterPromise: Promise<Highlighter> | null = null;

export const EDITOR_LANGUAGES = [
  'bash',
  'css',
  'diff',
  'go',
  'html',
  'java',
  'javascript',
  'json',
  'jsx',
  'markdown',
  'python',
  'ruby',
  'rust',
  'shell',
  'sql',
  'tsx',
  'typescript',
  'xml',
  'yaml',
] as const;

/**
 * Display-name + alias map for the BlockNote code-block language
 * dropdown. Lets users pick "TypeScript" while the lang-id stored
 * on the block is `typescript`. Aliases (`ts`, `js`, `py`, etc.)
 * make pasted markdown like ```` ```ts ```` resolve to the
 * canonical id when the editor parses it.
 */
export const EDITOR_LANGUAGE_DISPLAY: Record<
  string,
  { name: string; aliases?: string[] }
> = {
  bash: { name: 'Bash', aliases: ['sh'] },
  css: { name: 'CSS' },
  diff: { name: 'Diff' },
  go: { name: 'Go' },
  html: { name: 'HTML' },
  java: { name: 'Java' },
  javascript: { name: 'JavaScript', aliases: ['js'] },
  json: { name: 'JSON' },
  jsx: { name: 'JSX' },
  markdown: { name: 'Markdown', aliases: ['md'] },
  python: { name: 'Python', aliases: ['py'] },
  ruby: { name: 'Ruby', aliases: ['rb'] },
  rust: { name: 'Rust', aliases: ['rs'] },
  shell: { name: 'Shell' },
  sql: { name: 'SQL' },
  tsx: { name: 'TSX' },
  typescript: { name: 'TypeScript', aliases: ['ts'] },
  xml: { name: 'XML' },
  yaml: { name: 'YAML', aliases: ['yml'] },
};

/**
 * Resolve and cache the Shiki highlighter. The dynamic import means
 * the ~200KB Shiki engine ships in the lazy DocumentEditor chunk,
 * not the entry bundle.
 */
export function getEditorHighlighter(): Promise<Highlighter> {
  if (highlighterPromise) return highlighterPromise;
  highlighterPromise = (async () => {
    const { createHighlighter } = await import('shiki');
    return createHighlighter({
      // `github-light` matches the editor's warm cream surface
      // better than the default dark themes Shiki ships with.
      themes: ['github-light'],
      langs: EDITOR_LANGUAGES as unknown as string[],
    });
  })();
  // If the load fails, clear the cached promise so the next mount
  // can retry (network blip, dev-server hiccup, etc.).
  highlighterPromise.catch(() => {
    highlighterPromise = null;
  });
  return highlighterPromise;
}
