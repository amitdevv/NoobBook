/**
 * Prompt-editor helpers (Roadmap #16).
 *
 * Mirrors the backend's `prompt_var_utils.py`. The two regexes MUST stay
 * in sync — the editor uses this for instant client-side validation
 * (no round trip on each keystroke) and the backend uses its copy as
 * the actual save-time gate.
 */

/**
 * Pull deduped placeholder names out of `text` in document order.
 * Empty / non-string input returns an empty array.
 *
 * Single-token placeholder, matching Python identifier rules:
 *   `{var_name}` ✓     `{varName}` ✗ (uppercase rejected)
 *   `{ x }` ✗           `{"key": "value"}` ✗
 *
 * The regex is created fresh inside the function rather than at module
 * scope, since a stateful global regex can leak `lastIndex` between
 * calls if reused.
 */
export function extractVars(text: string | null | undefined): string[] {
  if (!text || typeof text !== 'string') return [];
  const VAR_RE = /\{([a-z_][a-z0-9_]*)\}/g;
  const seen = new Set<string>();
  const ordered: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = VAR_RE.exec(text)) !== null) {
    const name = match[1];
    if (!seen.has(name)) {
      seen.add(name);
      ordered.push(name);
    }
  }
  return ordered;
}

/**
 * Compute the set of required vars that have gone missing from an edit.
 * Used by the editor's live validation indicator. Returns the missing
 * names in document order from `required` so error text reads stable.
 */
export function missingVars(required: string[], present: string[]): string[] {
  const presentSet = new Set(present);
  return required.filter((v) => !presentSet.has(v));
}

/**
 * Insert `{var_name}` at the textarea's current cursor position.
 * Returns the new value and the new cursor offset (caller should set
 * the textarea's `selectionStart`/`selectionEnd` after React updates).
 *
 * If the cursor is outside the value (negative or past the end) we
 * append at the end — defensive for the rare case the selection is
 * unset on a fresh textarea.
 */
export function insertAtCursor(
  current: string,
  varName: string,
  cursor: number,
): { value: string; cursor: number } {
  const token = `{${varName}}`;
  const safeCursor = Math.max(0, Math.min(cursor ?? current.length, current.length));
  const next = current.slice(0, safeCursor) + token + current.slice(safeCursor);
  return { value: next, cursor: safeCursor + token.length };
}

/**
 * Bucket a prompt into a UI category for the left-rail grouping.
 *
 * Buckets (matching plan + plan-mode rationale):
 *   - chat        — main conversation surfaces (default, chat_naming, memory)
 *   - extraction  — background source processing (anything ending in _extraction
 *                   or csv_processor / summary)
 *   - agents      — query / analyzer / web agents
 *   - studio      — content generation; the catch-all
 *
 * Order returned matches the order categories appear in the rail.
 */
export type PromptCategory = 'chat' | 'studio' | 'extraction' | 'agents';

const CHAT_PROMPTS = new Set(['default', 'chat_naming', 'memory']);

export function categoryFor(promptName: string): PromptCategory {
  if (CHAT_PROMPTS.has(promptName)) return 'chat';
  if (
    promptName.endsWith('_extraction') ||
    promptName === 'csv_processor' ||
    promptName === 'summary'
  ) {
    return 'extraction';
  }
  if (
    promptName.endsWith('_analyzer_agent') ||
    promptName === 'web_agent' ||
    promptName === 'deep_research_agent'
  ) {
    return 'agents';
  }
  return 'studio';
}

/**
 * Display order for category headers in the rail. Chat first because
 * it's the most-edited; agents last because they're the most-niche.
 */
export const CATEGORY_ORDER: PromptCategory[] = ['chat', 'studio', 'extraction', 'agents'];

export const CATEGORY_LABELS: Record<PromptCategory, string> = {
  chat: 'Chat',
  studio: 'Studio',
  extraction: 'Extraction',
  agents: 'Agents',
};
