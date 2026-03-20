/**
 * RawMessageView Component
 * Educational Note: Debug view that displays ALL messages in a chat including
 * tool_use and tool_result intermediates that are normally filtered out.
 * Shows the raw JSON content blocks with syntax highlighting so developers
 * can inspect the full Claude API exchange.
 */

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { CaretUp, CaretDown, Copy, Check, CodeBlock, CircleNotch } from '@phosphor-icons/react';
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import json from 'react-syntax-highlighter/dist/esm/languages/hljs/json';
import { githubGist } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import { chatsAPI } from '../../lib/api/chats';
import type { RawMessage } from '../../lib/api/chats';

// Register only JSON language for minimal bundle size
SyntaxHighlighter.registerLanguage('json', json);

interface RawMessageViewProps {
  projectId: string;
  chatId: string;
}

const TYPE_STYLES: Record<string, { bg: string; text: string }> = {
  user_input: { bg: 'bg-blue-100 dark:bg-blue-900/40', text: 'text-blue-700 dark:text-blue-300' },
  ai_response: { bg: 'bg-green-100 dark:bg-green-900/40', text: 'text-green-700 dark:text-green-300' },
  tool_use: { bg: 'bg-teal-100 dark:bg-teal-900/40', text: 'text-teal-700 dark:text-teal-300' },
  tool_result: { bg: 'bg-orange-100 dark:bg-orange-900/40', text: 'text-orange-700 dark:text-orange-300' },
};

const RawMessageCard: React.FC<{ message: RawMessage; index: number }> = ({ message, index }) => {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const typeStyle = TYPE_STYLES[message.message_type] || TYPE_STYLES.ai_response;

  const jsonString = useMemo(() => JSON.stringify(message, null, 2), [message]);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [jsonString]);

  return (
    <div className="border border-stone-200 rounded-lg overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-stone-50 hover:bg-stone-100 transition-colors text-left"
      >
        {/* Role badge */}
        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
          message.role === 'assistant' ? 'bg-stone-200 text-stone-700' : 'bg-stone-300 text-stone-800'
        }`}>
          {message.role === 'assistant' ? 'ASSISTANT' : 'USER'}
        </span>

        {/* Index */}
        <span className="text-xs text-muted-foreground font-mono">#{index + 1}</span>

        {/* Type badge */}
        <span className={`text-xs font-medium px-2 py-0.5 rounded ${typeStyle.bg} ${typeStyle.text}`}>
          {message.message_type}
        </span>

        <div className="flex-1" />

        {/* Expand/collapse */}
        <span className="p-1 rounded hover:bg-stone-200 transition-colors">
          {expanded ? <CaretUp size={14} /> : <CaretDown size={14} />}
        </span>

        {/* Copy */}
        <span
          role="button"
          tabIndex={0}
          onClick={(e) => { e.stopPropagation(); handleCopy(); }}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); handleCopy(); } }}
          className="flex items-center gap-1 text-xs text-muted-foreground px-2 py-1 rounded hover:bg-stone-200 transition-colors"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          Copy
        </span>
      </button>

      {/* Body — syntax-highlighted JSON */}
      {expanded && (
        <SyntaxHighlighter
          language="json"
          style={githubGist}
          customStyle={{
            margin: 0,
            padding: '12px',
            fontSize: '12px',
            lineHeight: '1.5',
            borderRadius: 0,
            background: '#fafaf9',
          }}
          wrapLongLines
        >
          {jsonString}
        </SyntaxHighlighter>
      )}
    </div>
  );
};

const RawMessageViewContent: React.FC<RawMessageViewProps> = ({ projectId, chatId }) => {
  const [messages, setMessages] = useState<RawMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    chatsAPI.getRawMessages(projectId, chatId)
      .then((msgs) => { if (!cancelled) setMessages(msgs); })
      .catch((err) => { if (!cancelled) setError(err.message || 'Failed to load raw messages'); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [projectId, chatId]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <CircleNotch size={28} className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
        {error}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-sm font-medium text-stone-700">
          <CodeBlock size={18} weight="bold" />
          Raw Message Format
        </div>
        <span className="text-xs text-muted-foreground bg-stone-100 px-2 py-1 rounded">
          {messages.length} messages
        </span>
      </div>

      {/* Messages */}
      <div className="space-y-2">
        {messages.map((msg, i) => (
          <RawMessageCard key={msg.id} message={msg} index={i} />
        ))}
      </div>
    </div>
  );
};

export const RawMessageView: React.FC<RawMessageViewProps> = ({ projectId, chatId }) => (
  <RawMessageViewContent key={`${projectId}:${chatId}`} projectId={projectId} chatId={chatId} />
);
