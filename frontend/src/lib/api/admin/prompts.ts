/**
 * Admin Prompts API client (Roadmap #16).
 *
 * Wraps the four backend endpoints under `/api/v1/settings/prompts/...`.
 * All routes are admin-gated server-side; the client just relays.
 *
 * Backend lives at `backend/app/api/settings/prompts.py`. Shapes are
 * mirrored verbatim — if you tweak one side, tweak the other.
 */
import { api } from '../client';

/** Editable templated fields. Mirrors `_TEMPLATED_FIELDS` on the backend. */
export const TEMPLATED_FIELDS = [
  'system_prompt',
  'user_message',
  'user_message_template',
] as const;

export type TemplatedField = (typeof TEMPLATED_FIELDS)[number];

/**
 * One row in the left rail. Just enough to render a list item.
 */
export interface PromptSummary {
  prompt_name: string;
  name: string;
  description: string;
  model: string | null;
  default_model: string | null;
  max_tokens: number | null;
  temperature: number | null;
  has_override: boolean;
  required_vars: string[];
}

/**
 * Full editor payload. `base` is the shipped default, `effective` is
 * what the system actually uses right now (base merged with override).
 * `override` is the raw delta — null when no admin edit has been made.
 */
export interface PromptDetail {
  prompt_name: string;
  base: PromptConfigBody;
  override: Partial<PromptConfigBody> | null;
  effective: PromptConfigBody;
  required_vars: string[];
  current_vars: string[];
  referenced_by: string[];
  editable_fields: string[];
}

/**
 * Shape of a single prompt config — base, effective, and PUT bodies all
 * share these fields. Fields beyond the editable subset are ignored on PUT.
 */
export interface PromptConfigBody {
  name?: string;
  description?: string;
  model?: string | null;
  max_tokens?: number;
  temperature?: number;
  system_prompt?: string;
  user_message?: string;
  user_message_template?: string;
  version?: string;
  // Allow forward-compatibility with future JSON keys
  [key: string]: unknown;
}

/** Body for `PUT /settings/prompts/<name>`. */
export interface UpdatePromptInput {
  system_prompt?: string;
  user_message?: string;
  user_message_template?: string;
  max_tokens?: number;
  temperature?: number;
}

/**
 * Backend returns a structured 400 when the edit drops a required var.
 * Surfaced in the editor as the failure toast + per-var hint.
 */
export interface PromptValidationError {
  success: false;
  error: string;
  missing_vars?: string[];
  extra_vars?: string[];
}

export const promptsAPI = {
  list: () =>
    api.get<{ success: boolean; prompts: PromptSummary[]; count: number }>(
      '/settings/prompts',
    ),

  get: (promptName: string) =>
    api.get<{ success: boolean; prompt: PromptDetail }>(
      `/settings/prompts/${encodeURIComponent(promptName)}`,
    ),

  update: (promptName: string, body: UpdatePromptInput) =>
    api.put<{
      success: boolean;
      prompt: PromptDetail;
      extra_vars?: string[];
    }>(`/settings/prompts/${encodeURIComponent(promptName)}`, body),

  reset: (promptName: string) =>
    api.delete<{ success: boolean; prompt: PromptDetail }>(
      `/settings/prompts/${encodeURIComponent(promptName)}/override`,
    ),
};
