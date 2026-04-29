/**
 * SourceTags — archive-label tag system for source rows + filter UI.
 *
 * Aesthetic: "library card catalog" — lowercase, monospace, no border,
 * tinted backgrounds. The `#` prefix is muted so the tag name stays
 * the visual anchor.
 *
 * Three exports:
 *   - <TagStrip>     row inline display (truncates to first 3 + `+N`)
 *   - <TagFilterBar> horizontal-scrolling chip strip above the list
 *   - <TagEditor>    popover trigger for editing a row's tags
 */
import React, { useMemo, useRef, useState } from 'react';
import { Hash, Plus, X } from '@phosphor-icons/react';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';
import { Input } from '../ui/input';

const TAG_RE = /^[a-z0-9][a-z0-9_-]{0,31}$/;

function normalize(raw: string): string {
  return raw.trim().toLowerCase().replace(/\s+/g, '-').slice(0, 32);
}

interface ChipProps {
  tag: string;
  active?: boolean;
  onClick?: () => void;
  onRemove?: () => void;
  size?: 'xs' | 'sm';
}

const Chip: React.FC<ChipProps> = ({ tag, active, onClick, onRemove, size = 'xs' }) => {
  const sizing = size === 'xs'
    ? 'text-[10px] px-1.5 py-0.5'
    : 'text-[11px] px-2 py-0.5';
  const tone = active
    ? 'bg-amber-100 text-amber-800 border border-amber-300'
    : 'bg-stone-100/80 text-stone-600 hover:bg-stone-200';
  return (
    <span
      onClick={
        onClick
          ? (e) => {
              e.stopPropagation();
              onClick();
            }
          : undefined
      }
      className={`inline-flex items-center gap-0.5 rounded-sm font-mono leading-none transition-colors ${sizing} ${tone} ${
        onClick ? 'cursor-pointer' : ''
      }`}
    >
      <span className={active ? 'text-amber-500' : 'text-stone-400'}>#</span>
      <span>{tag}</span>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="ml-0.5 rounded-sm p-0.5 hover:bg-stone-300/40 text-stone-500 hover:text-stone-700"
          aria-label={`Remove ${tag}`}
        >
          <X size={9} weight="bold" />
        </button>
      )}
    </span>
  );
};

interface TagStripProps {
  tags: string[];
  onTagClick?: (tag: string) => void;
  max?: number;
}

export const TagStrip: React.FC<TagStripProps> = ({ tags, onTagClick, max = 3 }) => {
  if (!tags || tags.length === 0) return null;
  const visible = tags.slice(0, max);
  const overflow = tags.length - visible.length;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {visible.map((tag) => (
        <Chip key={tag} tag={tag} onClick={onTagClick ? () => onTagClick(tag) : undefined} />
      ))}
      {overflow > 0 && (
        <span className="font-mono text-[10px] text-stone-400">+{overflow}</span>
      )}
    </span>
  );
};

interface TagFilterBarProps {
  allTags: string[];
  selected: string[];
  onToggle: (tag: string) => void;
  onClear: () => void;
}

export const TagFilterBar: React.FC<TagFilterBarProps> = ({
  allTags,
  selected,
  onToggle,
  onClear,
}) => {
  if (allTags.length === 0) return null;
  return (
    <div className="px-2 pt-1 pb-2">
      <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
        {allTags.map((tag) => (
          <Chip
            key={tag}
            tag={tag}
            active={selected.includes(tag)}
            size="sm"
            onClick={() => onToggle(tag)}
          />
        ))}
        {selected.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="flex-shrink-0 ml-1 text-[10px] text-stone-500 hover:text-stone-800 underline underline-offset-2"
          >
            clear
          </button>
        )}
      </div>
    </div>
  );
};

interface TagEditorProps {
  tags: string[];
  /** Other tags already used in this project — shown as suggestions. */
  suggestions: string[];
  /** Called whenever the tag set changes. Caller is responsible for
   *  persisting (PUT to backend); the UI is optimistic. */
  onChange: (next: string[]) => void;
  /** Trigger element — defaults to a small Hash button. */
  children?: React.ReactNode;
}

export const TagEditor: React.FC<TagEditorProps> = ({
  tags,
  suggestions,
  onChange,
  children,
}) => {
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Suggestions = project-tags minus already-applied. Filter by
  // current input prefix for live narrowing.
  const filteredSuggestions = useMemo(() => {
    const q = input.trim().toLowerCase();
    return suggestions
      .filter((t) => !tags.includes(t))
      .filter((t) => !q || t.startsWith(q))
      .slice(0, 8);
  }, [suggestions, tags, input]);

  const addTag = (raw: string) => {
    const tag = normalize(raw);
    if (!tag) return;
    if (!TAG_RE.test(tag)) {
      setError('Letters, digits, _ or - only');
      return;
    }
    if (tags.includes(tag)) {
      setError('Already added');
      return;
    }
    setError(null);
    onChange([...tags, tag]);
    setInput('');
    // Keep focus for rapid multi-tag entry
    inputRef.current?.focus();
  };

  const removeTag = (tag: string) => {
    onChange(tags.filter((t) => t !== tag));
  };

  return (
    <Popover>
      <PopoverTrigger asChild onClick={(e) => e.stopPropagation()}>
        {children ?? (
          <button
            type="button"
            className="flex items-center gap-1 text-[10px] font-mono text-stone-400 hover:text-amber-700 transition-colors"
            aria-label="Edit tags"
          >
            <Hash size={11} weight="bold" />
            <span className="hidden group-hover:inline">tag</span>
          </button>
        )}
      </PopoverTrigger>
      <PopoverContent
        className="w-60 p-0 border-stone-200 bg-stone-50"
        align="start"
        side="bottom"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-3 py-2 border-b border-stone-200/70">
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              if (error) setError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addTag(input);
              }
              if (e.key === 'Backspace' && !input && tags.length > 0) {
                removeTag(tags[tags.length - 1]);
              }
            }}
            placeholder="Add a tag…"
            className="h-7 px-0 border-0 bg-transparent text-[12px] font-mono placeholder:text-stone-400 focus-visible:ring-0 focus-visible:ring-offset-0"
            autoFocus
          />
          {error && (
            <p className="mt-1 text-[10px] text-rose-600">{error}</p>
          )}
        </div>

        {tags.length > 0 && (
          <div className="px-3 py-2 border-b border-stone-200/70">
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-400 mb-1.5 font-mono">
              Applied
            </p>
            <div className="flex flex-wrap gap-1">
              {tags.map((tag) => (
                <Chip key={tag} tag={tag} size="sm" onRemove={() => removeTag(tag)} />
              ))}
            </div>
          </div>
        )}

        <div className="px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.18em] text-stone-400 mb-1.5 font-mono">
            {filteredSuggestions.length > 0 ? 'Suggested' : 'No suggestions'}
          </p>
          {filteredSuggestions.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {filteredSuggestions.map((tag) => (
                <Chip
                  key={tag}
                  tag={tag}
                  size="sm"
                  onClick={() => addTag(tag)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="px-3 py-2 border-t border-stone-200/70 flex items-center justify-between text-[10px] text-stone-400">
          <span className="font-mono">
            <kbd className="text-stone-500">Enter</kbd> to add
          </span>
          <span className="inline-flex items-center gap-1">
            <Plus size={10} weight="bold" />
            <span>archive label</span>
          </span>
        </div>
      </PopoverContent>
    </Popover>
  );
};
