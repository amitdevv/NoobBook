/**
 * PromptEditor — Admin Settings → Prompts detail pane (Roadmap #16).
 *
 * Aesthetic. Editorial / library: warm cream backdrop, fine rules,
 * generous breathing room. The required-variable chips are the only
 * saturated accent — small monospace pills that hover-glow to invite a
 * click. Validation indicator stays tiny and confident, never alarmed.
 *
 * Information hierarchy.
 *   1. Header strip   — name, category-bucket pill, model meta + "Edit
 *                       in Models →" link, "Reset" button if overridden.
 *   2. Numerics       — max_tokens + temperature side-by-side; both
 *                       show the shipped default as ghost text and a
 *                       "use default" link when changed.
 *   3. Body           — system_prompt textarea (always) with chip strip
 *                       above it. user_message / user_message_template
 *                       only when the base has it (chip strip again).
 *   4. Validation     — single-line indicator under the body. Green
 *                       check / red dot / yellow extra-vars warning.
 *   5. Footer         — Save + Discard, only when dirty.
 *   6. Diff           — collapsible "View shipped default" at the bottom.
 *                       Side-by-side stacked when overridden.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowSquareOut,
  Check,
  CircleNotch,
  Sparkle,
  Warning,
  WarningCircle,
} from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useToast } from '@/components/ui/use-toast';
import {
  promptsAPI,
  type PromptDetail,
  type UpdatePromptInput,
} from '@/lib/api/admin/prompts';
import { categoryFor, CATEGORY_LABELS, extractVars, insertAtCursor, missingVars } from './promptsLib';
import { createLogger } from '@/lib/logger';
import axios from 'axios';

const log = createLogger('prompt-editor');

interface PromptEditorProps {
  detail: PromptDetail;
  /** Bubble updated detail upward so the list rail can refresh its "Edited" pill. */
  onChange: (next: PromptDetail) => void;
  /** Switch the parent Settings dialog to a different section (used by "Edit in Models →"). */
  onSwitchSection?: (section: 'models') => void;
}

interface FormState {
  system_prompt: string;
  user_message: string;
  user_message_template: string;
  max_tokens: number | '';
  temperature: number | '';
}

const stringField = (value: unknown): string =>
  typeof value === 'string' ? value : '';

const numberField = (value: unknown): number | '' =>
  typeof value === 'number' && Number.isFinite(value) ? value : '';

function formFromDetail(detail: PromptDetail): FormState {
  const eff = detail.effective || {};
  return {
    system_prompt: stringField(eff.system_prompt),
    user_message: stringField(eff.user_message),
    user_message_template: stringField(eff.user_message_template),
    max_tokens: numberField(eff.max_tokens),
    temperature: numberField(eff.temperature),
  };
}

/** True iff the form differs from `detail.effective`. */
function isDirty(form: FormState, detail: PromptDetail): boolean {
  const eff = formFromDetail(detail);
  return (
    form.system_prompt !== eff.system_prompt ||
    form.user_message !== eff.user_message ||
    form.user_message_template !== eff.user_message_template ||
    form.max_tokens !== eff.max_tokens ||
    form.temperature !== eff.temperature
  );
}

export const PromptEditor: React.FC<PromptEditorProps> = ({
  detail,
  onChange,
  onSwitchSection,
}) => {
  const { success, error } = useToast();

  const [form, setForm] = useState<FormState>(() => formFromDetail(detail));
  const [saving, setSaving] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [diffOpen, setDiffOpen] = useState(false);

  // Re-seed when the loaded detail changes (admin clicked a different prompt).
  useEffect(() => {
    setForm(formFromDetail(detail));
    setDiffOpen(false);
  }, [detail.prompt_name, detail.effective]);

  const base = detail.base || {};
  const requiredVars = detail.required_vars;
  const hasUserMessage = typeof base.user_message === 'string';
  const hasUserMessageTemplate = typeof base.user_message_template === 'string';

  // Live-extract present vars from the merged edited body so the chip
  // strip + validation indicator stay in sync as the admin types.
  const presentVars = useMemo(() => {
    return extractVars(
      [form.system_prompt, form.user_message, form.user_message_template]
        .filter(Boolean)
        .join('\n'),
    );
  }, [form.system_prompt, form.user_message, form.user_message_template]);

  const missing = useMemo(
    () => missingVars(requiredVars, presentVars),
    [requiredVars, presentVars],
  );
  const extras = useMemo(
    () => presentVars.filter((v) => !requiredVars.includes(v)),
    [presentVars, requiredVars],
  );

  const dirty = useMemo(() => isDirty(form, detail), [form, detail]);
  // Empty numerics are not a valid save state. With the backend's merge
  // semantics, a PUT that omits max_tokens/temperature preserves the
  // existing override value — meaning a "cleared" input would silently
  // no-op while showing a success toast. The "use default" link on
  // each NumericKnob is the real path to un-override; we point at it
  // when the admin lands here.
  const numericsBlank = form.max_tokens === '' || form.temperature === '';
  const canSave = dirty && missing.length === 0 && !numericsBlank && !saving;

  // Refs for the textareas so we can insert chip tokens at the caret.
  const systemRef = useRef<HTMLTextAreaElement | null>(null);
  const userMsgRef = useRef<HTMLTextAreaElement | null>(null);
  const userTplRef = useRef<HTMLTextAreaElement | null>(null);

  const handleChipInsert = (
    field: 'system_prompt' | 'user_message' | 'user_message_template',
    varName: string,
  ) => {
    const ref =
      field === 'system_prompt'
        ? systemRef.current
        : field === 'user_message'
          ? userMsgRef.current
          : userTplRef.current;
    if (!ref) return;
    const cursor = ref.selectionStart ?? form[field].length;
    const { value: nextValue, cursor: nextCursor } = insertAtCursor(
      form[field],
      varName,
      cursor,
    );
    setForm((prev) => ({ ...prev, [field]: nextValue }));
    // Restore focus + caret after React commits.
    requestAnimationFrame(() => {
      ref.focus();
      ref.setSelectionRange(nextCursor, nextCursor);
    });
  };

  const handleSave = async () => {
    if (!canSave) return;
    const body: UpdatePromptInput = {};
    const eff = formFromDetail(detail);
    if (form.system_prompt !== eff.system_prompt) body.system_prompt = form.system_prompt;
    if (hasUserMessage && form.user_message !== eff.user_message) {
      body.user_message = form.user_message;
    }
    if (hasUserMessageTemplate && form.user_message_template !== eff.user_message_template) {
      body.user_message_template = form.user_message_template;
    }
    if (form.max_tokens !== eff.max_tokens && form.max_tokens !== '') {
      body.max_tokens = Number(form.max_tokens);
    }
    if (form.temperature !== eff.temperature && form.temperature !== '') {
      body.temperature = Number(form.temperature);
    }

    try {
      setSaving(true);
      const res = await promptsAPI.update(detail.prompt_name, body);
      onChange(res.data.prompt);
      if (res.data.extra_vars && res.data.extra_vars.length > 0) {
        success(
          `Saved. Heads up: new variables added (${res.data.extra_vars
            .map((v) => `{${v}}`)
            .join(', ')}) — make sure the consuming service supplies them.`,
        );
      } else {
        success('Prompt saved');
      }
    } catch (err) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data as { error?: string; missing_vars?: string[] })?.error
        : null;
      log.error({ err, prompt: detail.prompt_name }, 'save failed');
      error(msg || 'Save failed — please try again');
    } finally {
      setSaving(false);
    }
  };

  const handleDiscard = () => {
    setForm(formFromDetail(detail));
  };

  const handleReset = async () => {
    try {
      setResetting(true);
      const res = await promptsAPI.reset(detail.prompt_name);
      onChange(res.data.prompt);
      setResetOpen(false);
      success('Prompt reset to shipped default');
    } catch (err) {
      log.error({ err, prompt: detail.prompt_name }, 'reset failed');
      error('Reset failed — please try again');
    } finally {
      setResetting(false);
    }
  };

  const category = categoryFor(detail.prompt_name);
  const displayName = (base.name as string | undefined) || detail.prompt_name;

  return (
    <div className="flex flex-col h-full">
      {/* ── Header strip ─────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-b border-stone-200 px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase tracking-[0.14em] text-stone-500 font-medium">
                {CATEGORY_LABELS[category]}
              </span>
              {detail.override && (
                <span className="inline-flex items-center gap-1 px-1.5 py-px rounded-full text-[10px] uppercase tracking-wider font-medium bg-amber-50 text-amber-800 border border-amber-200/80">
                  <Sparkle size={9} weight="fill" />
                  Edited
                </span>
              )}
            </div>
            <h2 className="text-lg font-semibold text-stone-900 leading-tight font-serif">
              {displayName}
            </h2>
            {base.description ? (
              <p className="text-[13px] text-stone-600 mt-1.5 leading-relaxed max-w-2xl">
                {String(base.description)}
              </p>
            ) : null}
          </div>

          <div className="flex-shrink-0 flex items-center gap-2">
            {detail.override && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setResetOpen(true)}
                className="text-xs text-stone-600 hover:text-stone-900"
              >
                Reset to default
              </Button>
            )}
          </div>
        </div>

        {/* Model + referenced-by line */}
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11.5px] text-stone-500">
          <span className="inline-flex items-center gap-1.5">
            <span className="text-stone-400">Model</span>
            <span className="font-mono text-stone-700">
              {detail.effective.model ?? base.model ?? '—'}
            </span>
            {onSwitchSection && (
              <button
                type="button"
                onClick={() => onSwitchSection('models')}
                className="ml-1 inline-flex items-center gap-0.5 text-amber-700 hover:text-amber-800 underline-offset-2 hover:underline"
              >
                Edit in Models
                <ArrowSquareOut size={11} />
              </button>
            )}
          </span>
          {detail.referenced_by.length > 0 && (
            <span className="inline-flex items-center gap-1.5 min-w-0">
              <span className="text-stone-400">Used by</span>
              <span className="font-mono text-stone-700 truncate">
                {detail.referenced_by[0].split('/').slice(-1)[0]}
                {detail.referenced_by.length > 1
                  ? ` +${detail.referenced_by.length - 1}`
                  : ''}
              </span>
            </span>
          )}
        </div>
      </div>

      {/* ── Body ─────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-6 py-6 space-y-7 max-w-3xl">
          {/* Numerics */}
          <div className="grid grid-cols-2 gap-4">
            <NumericKnob
              label="max_tokens"
              value={form.max_tokens}
              defaultValue={numberField(base.max_tokens)}
              integer
              onChange={(v) => setForm((p) => ({ ...p, max_tokens: v }))}
            />
            <NumericKnob
              label="temperature"
              value={form.temperature}
              defaultValue={numberField(base.temperature)}
              step={0.1}
              min={0}
              max={2}
              onChange={(v) => setForm((p) => ({ ...p, temperature: v }))}
            />
          </div>

          {/* system_prompt */}
          <PromptField
            label="system_prompt"
            description="The instructions Claude reads first. Sets behavior, tone, output format."
            value={form.system_prompt}
            requiredVars={requiredVars}
            currentVars={presentVars}
            textareaRef={systemRef}
            onChange={(v) => setForm((p) => ({ ...p, system_prompt: v }))}
            onChipClick={(v) => handleChipInsert('system_prompt', v)}
            minRows={16}
          />

          {/* user_message */}
          {hasUserMessage && (
            <PromptField
              label="user_message"
              description="Templated message body. Variables in curly braces are filled at runtime by the consuming service."
              value={form.user_message}
              requiredVars={requiredVars}
              currentVars={presentVars}
              textareaRef={userMsgRef}
              onChange={(v) => setForm((p) => ({ ...p, user_message: v }))}
              onChipClick={(v) => handleChipInsert('user_message', v)}
              minRows={6}
            />
          )}

          {/* user_message_template */}
          {hasUserMessageTemplate && (
            <PromptField
              label="user_message_template"
              description="Template body with runtime variables."
              value={form.user_message_template}
              requiredVars={requiredVars}
              currentVars={presentVars}
              textareaRef={userTplRef}
              onChange={(v) => setForm((p) => ({ ...p, user_message_template: v }))}
              onChipClick={(v) => handleChipInsert('user_message_template', v)}
              minRows={6}
            />
          )}

          {/* Validation indicator */}
          <ValidationLine
            missing={missing}
            extras={extras}
            requiredCount={requiredVars.length}
            blankNumeric={
              form.max_tokens === ''
                ? 'max_tokens'
                : form.temperature === ''
                  ? 'temperature'
                  : null
            }
          />

          {/* Diff / view default */}
          <DiffPanel
            open={diffOpen}
            onToggle={() => setDiffOpen((v) => !v)}
            base={base}
            override={detail.override}
            hasUserMessage={hasUserMessage}
            hasUserMessageTemplate={hasUserMessageTemplate}
          />
        </div>
      </div>

      {/* ── Footer ───────────────────────────────────────────────── */}
      {dirty && (
        <div className="flex-shrink-0 border-t border-stone-200 bg-stone-50/60 px-6 py-3 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleDiscard}
            disabled={saving}
            className="text-xs text-stone-600 hover:text-stone-900 underline-offset-4 hover:underline disabled:opacity-50"
          >
            Discard changes
          </button>
          <Button onClick={handleSave} disabled={!canSave} size="sm" className="gap-1.5">
            {saving ? <CircleNotch size={14} className="animate-spin" /> : null}
            Save changes
          </Button>
        </div>
      )}

      {/* Reset confirm dialog */}
      <Dialog open={resetOpen} onOpenChange={setResetOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Reset to shipped default?</DialogTitle>
            <DialogDescription className="text-[13px] leading-relaxed">
              This will delete your override for{' '}
              <span className="font-mono text-stone-800">{detail.prompt_name}</span>{' '}
              and revert the prompt to whatever ships with the current release.
              You can re-apply your edits manually afterwards if needed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="outline"
              onClick={() => setResetOpen(false)}
              disabled={resetting}
            >
              Cancel
            </Button>
            <Button onClick={handleReset} disabled={resetting} className="gap-1.5">
              {resetting ? <CircleNotch size={14} className="animate-spin" /> : null}
              Reset
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────
// Subcomponents
// ────────────────────────────────────────────────────────────────────

interface NumericKnobProps {
  label: string;
  value: number | '';
  defaultValue: number | '';
  integer?: boolean;
  step?: number;
  min?: number;
  max?: number;
  onChange: (v: number | '') => void;
}

const NumericKnob: React.FC<NumericKnobProps> = ({
  label,
  value,
  defaultValue,
  integer = false,
  step = 1,
  min,
  max,
  onChange,
}) => {
  const isOverridden = value !== '' && value !== defaultValue;
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <Label className="text-[11px] uppercase tracking-wider font-medium text-stone-500 font-mono">
          {label}
        </Label>
        {isOverridden && defaultValue !== '' && (
          <button
            type="button"
            onClick={() => onChange(defaultValue)}
            className="text-[10.5px] text-amber-700 hover:text-amber-800 underline-offset-2 hover:underline"
          >
            use default ({defaultValue})
          </button>
        )}
      </div>
      <Input
        type="number"
        value={value}
        step={integer ? 1 : step}
        min={min}
        max={max}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === '') return onChange('');
          const parsed = integer ? parseInt(raw, 10) : parseFloat(raw);
          onChange(Number.isFinite(parsed) ? parsed : '');
        }}
        className="font-mono text-sm h-9"
        placeholder={defaultValue !== '' ? `default: ${defaultValue}` : undefined}
      />
    </div>
  );
};

interface PromptFieldProps {
  label: string;
  description: string;
  value: string;
  requiredVars: string[];
  currentVars: string[];
  textareaRef: React.MutableRefObject<HTMLTextAreaElement | null>;
  onChange: (v: string) => void;
  onChipClick: (v: string) => void;
  minRows: number;
}

const PromptField: React.FC<PromptFieldProps> = ({
  label,
  description,
  value,
  requiredVars,
  currentVars,
  textareaRef,
  onChange,
  onChipClick,
  minRows,
}) => {
  const presentSet = new Set(currentVars);
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <Label className="text-[11px] uppercase tracking-wider font-medium text-stone-500 font-mono">
          {label}
        </Label>
      </div>
      <p className="text-[12px] text-stone-500 leading-relaxed mb-2.5">
        {description}
      </p>

      {/* Required-variable chip strip — the design accent. */}
      {requiredVars.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <span className="text-[10.5px] text-stone-400 mr-0.5">
            Required:
          </span>
          {requiredVars.map((v) => {
            const present = presentSet.has(v);
            return (
              <button
                key={v}
                type="button"
                onClick={() => onChipClick(v)}
                title={
                  present
                    ? `Insert another {${v}} at cursor`
                    : `Missing — click to insert {${v}}`
                }
                className={[
                  'group inline-flex items-center gap-1 px-2 py-0.5 rounded-md',
                  'font-mono text-[11px] transition-all border cursor-pointer',
                  present
                    ? 'bg-amber-50/70 text-amber-900 border-amber-200/80 hover:bg-amber-100 hover:border-amber-300'
                    : 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100 hover:border-rose-300 ring-1 ring-rose-200/40',
                ].join(' ')}
              >
                {!present && <WarningCircle size={10} weight="fill" className="opacity-80" />}
                <span>{`{${v}}`}</span>
              </button>
            );
          })}
        </div>
      )}

      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={minRows}
        spellCheck={false}
        className="font-mono text-[12.5px] leading-[1.55] resize-y min-h-[8rem]"
      />
    </div>
  );
};

interface ValidationLineProps {
  missing: string[];
  extras: string[];
  requiredCount: number;
  /** Name of the cleared numeric field, if any — drives the hint pointing
   * at the "use default" link, since saving an empty numeric would be
   * a silent no-op under the backend's merge semantics. */
  blankNumeric: 'max_tokens' | 'temperature' | null;
}

const ValidationLine: React.FC<ValidationLineProps> = ({
  missing,
  extras,
  requiredCount,
  blankNumeric,
}) => {
  // Blank numeric is a hard save block — surface it before everything
  // else so the admin knows what to fix.
  if (blankNumeric) {
    return (
      <div className="flex items-start gap-2 text-[12.5px] text-rose-700">
        <WarningCircle size={14} weight="fill" className="mt-0.5 flex-shrink-0" />
        <div>
          <span className="font-medium">{blankNumeric} is empty.</span>{' '}
          Type a value, or use the{' '}
          <span className="font-mono text-[12px]">use default</span>{' '}
          link above the field to clear your override.
        </div>
      </div>
    );
  }

  if (requiredCount === 0 && extras.length === 0) {
    return (
      <div className="text-[12px] text-stone-400 italic">
        No template variables in this prompt.
      </div>
    );
  }

  if (missing.length > 0) {
    return (
      <div className="flex items-start gap-2 text-[12.5px] text-rose-700">
        <WarningCircle size={14} weight="fill" className="mt-0.5 flex-shrink-0" />
        <div>
          <span className="font-medium">Missing required variables: </span>
          <span className="font-mono">
            {missing.map((v) => `{${v}}`).join(', ')}
          </span>
          <p className="text-[11.5px] text-rose-600/90 mt-0.5">
            Removing these would crash the consuming service at runtime. Click a
            chip above to re-insert.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 text-[12.5px] text-emerald-700">
        <Check size={14} weight="bold" />
        <span>
          {requiredCount === 0
            ? 'All required variables present'
            : `All ${requiredCount} required variable${requiredCount === 1 ? '' : 's'} present`}
        </span>
      </div>
      {extras.length > 0 && (
        <div className="flex items-start gap-2 text-[11.5px] text-amber-700">
          <Warning size={12} weight="fill" className="mt-0.5 flex-shrink-0" />
          <span>
            New variable{extras.length === 1 ? '' : 's'}{' '}
            <span className="font-mono">
              {extras.map((v) => `{${v}}`).join(', ')}
            </span>{' '}
            — make sure the consuming service supplies {extras.length === 1 ? 'it' : 'them'}.
          </span>
        </div>
      )}
    </div>
  );
};

interface DiffPanelProps {
  open: boolean;
  onToggle: () => void;
  base: PromptDetail['base'];
  override: PromptDetail['override'];
  hasUserMessage: boolean;
  hasUserMessageTemplate: boolean;
}

const DiffPanel: React.FC<DiffPanelProps> = ({
  open,
  onToggle,
  base,
  override,
  hasUserMessage,
  hasUserMessageTemplate,
}) => {
  return (
    <div className="border-t border-stone-200/80 pt-5 mt-2">
      <button
        type="button"
        onClick={onToggle}
        className="text-[11.5px] uppercase tracking-[0.12em] text-stone-500 hover:text-stone-800 font-medium transition-colors inline-flex items-center gap-1.5"
      >
        <span>{open ? 'Hide' : 'View'} shipped default</span>
        <span className="text-stone-400">{open ? '−' : '+'}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          <DiffSection
            label="system_prompt"
            base={String(base.system_prompt ?? '')}
            override={typeof override?.system_prompt === 'string' ? override.system_prompt : null}
          />
          {hasUserMessage && (
            <DiffSection
              label="user_message"
              base={String(base.user_message ?? '')}
              override={typeof override?.user_message === 'string' ? override.user_message : null}
            />
          )}
          {hasUserMessageTemplate && (
            <DiffSection
              label="user_message_template"
              base={String(base.user_message_template ?? '')}
              override={
                typeof override?.user_message_template === 'string'
                  ? override.user_message_template
                  : null
              }
            />
          )}
        </div>
      )}
    </div>
  );
};

interface DiffSectionProps {
  label: string;
  base: string;
  /** Null when no override has been written for this field. */
  override: string | null;
}

const DiffSection: React.FC<DiffSectionProps> = ({ label, base, override }) => {
  if (override === null) {
    // No override for this field — just show the default.
    return (
      <div>
        <div className="text-[11px] uppercase tracking-wider text-stone-500 font-mono mb-1.5">
          {label} <span className="text-stone-400 normal-case tracking-normal">(default)</span>
        </div>
        <pre className="text-[11.5px] font-mono leading-[1.55] text-stone-700 bg-stone-50/70 border border-stone-200/70 rounded-md p-3 overflow-x-auto whitespace-pre-wrap">
          {base || <span className="text-stone-400 italic">(empty)</span>}
        </pre>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div>
        <div className="text-[11px] uppercase tracking-wider text-stone-500 font-mono mb-1.5">
          {label} <span className="text-stone-400 normal-case tracking-normal">(default)</span>
        </div>
        <pre className="text-[11.5px] font-mono leading-[1.55] text-stone-600 bg-stone-50/70 border border-stone-200/70 rounded-md p-3 overflow-x-auto whitespace-pre-wrap min-h-[6rem]">
          {base || <span className="text-stone-400 italic">(empty)</span>}
        </pre>
      </div>
      <div>
        <div className="text-[11px] uppercase tracking-wider text-amber-800 font-mono mb-1.5">
          {label} <span className="text-amber-700/80 normal-case tracking-normal">(your edit)</span>
        </div>
        <pre className="text-[11.5px] font-mono leading-[1.55] text-stone-800 bg-amber-50/40 border border-amber-200/70 rounded-md p-3 overflow-x-auto whitespace-pre-wrap min-h-[6rem]">
          {override}
        </pre>
      </div>
    </div>
  );
};
