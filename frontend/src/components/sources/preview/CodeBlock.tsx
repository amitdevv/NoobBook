/**
 * CodeBlock — fenced-code-block renderer used by MarkdownView via
 * react-markdown's `pre` component override.
 *
 * Why override `pre` and not `code`? react-markdown calls `code` for
 * both inline and block code. The cleanest way to tell them apart is
 * to override the `pre` wrapper that only block code lives inside.
 * We extract the inner `<code>`'s className (`language-ts`, etc.) for
 * the language hint.
 *
 * Highlighting uses react-syntax-highlighter's `Light` build with a
 * curated language list (registered once at module load) so we don't
 * pull every grammar into the lazy chunk. Copy button appears on hover
 * and shows a 1.5-second "Copied" confirmation.
 */
import React, { useState } from 'react';
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import bash from 'react-syntax-highlighter/dist/esm/languages/hljs/bash';
import css from 'react-syntax-highlighter/dist/esm/languages/hljs/css';
import diff from 'react-syntax-highlighter/dist/esm/languages/hljs/diff';
import go from 'react-syntax-highlighter/dist/esm/languages/hljs/go';
import javaLang from 'react-syntax-highlighter/dist/esm/languages/hljs/java';
import javascript from 'react-syntax-highlighter/dist/esm/languages/hljs/javascript';
import json from 'react-syntax-highlighter/dist/esm/languages/hljs/json';
import markdown from 'react-syntax-highlighter/dist/esm/languages/hljs/markdown';
import python from 'react-syntax-highlighter/dist/esm/languages/hljs/python';
import ruby from 'react-syntax-highlighter/dist/esm/languages/hljs/ruby';
import rust from 'react-syntax-highlighter/dist/esm/languages/hljs/rust';
import shell from 'react-syntax-highlighter/dist/esm/languages/hljs/shell';
import sql from 'react-syntax-highlighter/dist/esm/languages/hljs/sql';
import typescript from 'react-syntax-highlighter/dist/esm/languages/hljs/typescript';
import xml from 'react-syntax-highlighter/dist/esm/languages/hljs/xml';
import yaml from 'react-syntax-highlighter/dist/esm/languages/hljs/yaml';
import { Copy, Check } from '@phosphor-icons/react';
import { MermaidBlock } from './MermaidBlock';

// Track registered language IDs so we can decide whether to fall
// through to plain rendering. SyntaxHighlighter doesn't expose its
// internal language registry on the Light build.
const REGISTERED = new Set<string>([
  'bash', 'sh', 'shell', 'css', 'diff', 'go', 'java', 'javascript',
  'js', 'jsx', 'json', 'markdown', 'md', 'python', 'py', 'ruby', 'rb',
  'rust', 'rs', 'sql', 'typescript', 'ts', 'tsx', 'html', 'xml',
  'yaml', 'yml',
]);

// Register the languages we expect to see in pasted notes / extracted
// docs. Less common ones fall through to plaintext rendering — still
// gets a copy button + monospace font, just no coloring.
SyntaxHighlighter.registerLanguage('bash', bash);
SyntaxHighlighter.registerLanguage('sh', bash);
SyntaxHighlighter.registerLanguage('shell', shell);
SyntaxHighlighter.registerLanguage('css', css);
SyntaxHighlighter.registerLanguage('diff', diff);
SyntaxHighlighter.registerLanguage('go', go);
SyntaxHighlighter.registerLanguage('java', javaLang);
SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('js', javascript);
SyntaxHighlighter.registerLanguage('jsx', javascript);
SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('markdown', markdown);
SyntaxHighlighter.registerLanguage('md', markdown);
SyntaxHighlighter.registerLanguage('python', python);
SyntaxHighlighter.registerLanguage('py', python);
SyntaxHighlighter.registerLanguage('ruby', ruby);
SyntaxHighlighter.registerLanguage('rb', ruby);
SyntaxHighlighter.registerLanguage('rust', rust);
SyntaxHighlighter.registerLanguage('rs', rust);
SyntaxHighlighter.registerLanguage('sql', sql);
SyntaxHighlighter.registerLanguage('typescript', typescript);
SyntaxHighlighter.registerLanguage('ts', typescript);
SyntaxHighlighter.registerLanguage('tsx', typescript);
SyntaxHighlighter.registerLanguage('html', xml);
SyntaxHighlighter.registerLanguage('xml', xml);
SyntaxHighlighter.registerLanguage('yaml', yaml);
SyntaxHighlighter.registerLanguage('yml', yaml);

interface CodeBlockProps {
  language: string | null;
  code: string;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);

  // Special-case: ```mermaid``` blocks render as the diagram itself.
  // Source still gets a copy button via the wrapper layout.
  if (language === 'mermaid') {
    const handleCopyMermaid = async () => {
      try {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      } catch {
        /* ignore */
      }
    };
    return (
      <div className="group relative my-4">
        <button
          type="button"
          onClick={handleCopyMermaid}
          aria-label={copied ? 'Copied' : 'Copy mermaid source'}
          className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 focus:opacity-100 transition rounded border border-stone-200 bg-white/90 px-2 py-1 text-[10px] font-medium text-stone-600 hover:text-stone-900 inline-flex items-center gap-1"
        >
          {copied ? (
            <>
              <Check size={11} weight="bold" />
              Copied
            </>
          ) : (
            <>
              <Copy size={11} />
              Copy source
            </>
          )}
        </button>
        <MermaidBlock source={code} />
      </div>
    );
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Some sandboxed iframes block clipboard API; fail silently
      // rather than throwing a toast at the user.
    }
  };

  return (
    <div className="group relative my-4 rounded-lg overflow-hidden border border-stone-800">
      {/* Top bar: language label (left) + copy button (right). */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-stone-900 border-b border-stone-800">
        <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-stone-500">
          {language || 'text'}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          aria-label={copied ? 'Copied' : 'Copy code'}
          className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition inline-flex items-center gap-1 text-[10px] font-medium text-stone-400 hover:text-stone-100"
        >
          {copied ? (
            <>
              <Check size={11} weight="bold" />
              Copied
            </>
          ) : (
            <>
              <Copy size={11} />
              Copy
            </>
          )}
        </button>
      </div>

      {language && REGISTERED.has(language) ? (
        <SyntaxHighlighter
          language={language}
          style={atomOneDark}
          customStyle={{
            margin: 0,
            padding: '14px 16px',
            background: 'rgb(28 25 23)', // stone-900
            fontSize: '13px',
            lineHeight: 1.6,
          }}
          codeTagProps={{
            style: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' },
          }}
        >
          {code}
        </SyntaxHighlighter>
      ) : (
        // Fallback: plain monospace render. Still gets the copy button
        // and the dark surface; just no coloring.
        <pre className="m-0 p-4 bg-stone-900 text-stone-100 overflow-x-auto text-[13px] leading-relaxed font-mono">
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
};
