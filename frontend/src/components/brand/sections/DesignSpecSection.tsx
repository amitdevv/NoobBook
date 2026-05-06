/**
 * DesignSpecSection
 *
 * Long-form design.md spec editor. Renders alongside the structured
 * brand-kit tabs (Colors / Typography / Logos / Icons / Guidelines /
 * Features) — admins paste or draft a markdown specification that gets
 * injected into the system prompt of all brand-aware studio agents.
 *
 * Feels like a designer's manuscript, not a textarea: editorial section
 * header, subtle "ink meter" token gauge, sample banner that whispers
 * instead of shouting, and a 60/40 split between the authoring surface
 * and a tightened-prose preview.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import MDEditor from '@uiw/react-md-editor';
import {
  ArrowCounterClockwise,
  Check,
  CircleNotch,
  Sparkle,
  Warning,
} from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/use-toast';
import { brandAPI } from '@/lib/api/brand';
import { createLogger } from '@/lib/logger';
import { cn } from '@/lib/utils';
import { DesignBootstrapDialog } from './DesignBootstrapDialog';

const log = createLogger('design-spec');

// Rough char→token estimate: ~4 chars/token for English markdown.
// Backend caps at 32k chars (_DESIGN_MD_MAX_CHARS), which is ~8k tokens.
const CHARS_PER_TOKEN = 4;
const TOKEN_WARN = 4000;
const TOKEN_HARD_CAP = 8000;
const CHAR_HARD_CAP = TOKEN_HARD_CAP * CHARS_PER_TOKEN;

const formatNumber = (n: number) => n.toLocaleString();

interface MeterState {
  level: 'safe' | 'warn' | 'over';
  fillClass: string;
  trackClass: string;
  textClass: string;
}

const meterFor = (tokens: number): MeterState => {
  if (tokens >= TOKEN_HARD_CAP) {
    return {
      level: 'over',
      fillClass: 'bg-rose-500',
      trackClass: 'bg-rose-100',
      textClass: 'text-rose-600',
    };
  }
  if (tokens >= TOKEN_WARN) {
    return {
      level: 'warn',
      fillClass: 'bg-amber-500',
      trackClass: 'bg-amber-100',
      textClass: 'text-amber-700',
    };
  }
  return {
    level: 'safe',
    fillClass: 'bg-stone-400',
    trackClass: 'bg-stone-100',
    textClass: 'text-stone-500',
  };
};

export const DesignSpecSection: React.FC = () => {
  const { success: showSuccess, error: showError } = useToast();

  const [content, setContent] = useState('');
  const [savedContent, setSavedContent] = useState('');
  const [isSample, setIsSample] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedRecently, setSavedRecently] = useState(false);
  const [bootstrapOpen, setBootstrapOpen] = useState(false);

  const sampleSnapshotRef = useRef<string | null>(null);
  const savedFlashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadDesignMd = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await brandAPI.getDesignMd();
      if (data.success) {
        setContent(data.design_md);
        setSavedContent(data.is_sample ? '' : data.design_md);
        setIsSample(data.is_sample);
        if (data.is_sample) {
          sampleSnapshotRef.current = data.design_md;
        }
      }
    } catch (err) {
      log.error({ err }, 'failed to load design.md');
      showError('Could not load design spec. Try refreshing.');
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadDesignMd();
    return () => {
      if (savedFlashTimer.current) clearTimeout(savedFlashTimer.current);
    };
  }, [loadDesignMd]);

  const dirty = useMemo(() => content !== savedContent, [content, savedContent]);
  const charCount = content.length;
  const tokenEstimate = Math.round(charCount / CHARS_PER_TOKEN);
  const meter = meterFor(tokenEstimate);
  const overCap = charCount > CHAR_HARD_CAP;
  const fillPct = Math.min(100, (tokenEstimate / TOKEN_HARD_CAP) * 100);

  const handleSave = useCallback(async () => {
    if (overCap) {
      showError(
        `Spec is too long. Trim to under ${formatNumber(TOKEN_HARD_CAP)} tokens (~${formatNumber(CHAR_HARD_CAP)} chars).`,
      );
      return;
    }
    setSaving(true);
    try {
      const { data } = await brandAPI.updateDesignMd(content);
      if (data.success) {
        setSavedContent(content);
        setIsSample(false);
        setSavedRecently(true);
        if (savedFlashTimer.current) clearTimeout(savedFlashTimer.current);
        savedFlashTimer.current = setTimeout(() => setSavedRecently(false), 1500);
      } else {
        showError(data.error || 'Save failed');
      }
    } catch (err) {
      log.error({ err }, 'failed to save design.md');
      showError('Could not save. Try again.');
    } finally {
      setSaving(false);
    }
  }, [content, overCap, showError]);

  const handleResetToSample = useCallback(() => {
    // Always pull the bundled template directly (separate read-only endpoint)
    // — never clear the saved spec just to "reset" the editor view. The admin
    // still has to hit Save to actually persist the template, so their
    // current saved content stays intact until they decide.
    if (sampleSnapshotRef.current) {
      setContent(sampleSnapshotRef.current);
      showSuccess('Reset to bundled template. Edit and Save when ready.');
      return;
    }
    void (async () => {
      try {
        const { data } = await brandAPI.getDesignMdSample();
        if (!data.success) throw new Error('sample fetch failed');
        sampleSnapshotRef.current = data.design_md;
        setContent(data.design_md);
        showSuccess('Reset to bundled template. Edit and Save when ready.');
      } catch (err) {
        log.error({ err }, 'reset failed');
        showError('Could not load the template.');
      }
    })();
  }, [showError, showSuccess]);

  const handleBootstrapResult = useCallback((markdown: string) => {
    setContent(markdown);
    setBootstrapOpen(false);
    showSuccess('Draft generated. Review and Save when you\'re happy with it.');
  }, [showSuccess]);

  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex h-full flex-col bg-white">
        {/* Editorial header — establishes the document frame */}
        <div className="border-b border-stone-200 px-8 pt-6 pb-5">
          <div className="flex items-baseline justify-between gap-6">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-amber-700/80">
                Design Specification
              </p>
              <h2 className="mt-1.5 font-serif text-2xl font-semibold leading-tight text-stone-900">
                Your studio's source of truth
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-stone-600">
                A long-form spec studio agents read alongside your brand kit. Layout
                rules, voice examples, anti-patterns — anything the structured tokens
                can't capture. Markdown.
              </p>
            </div>
            {!loading && (
              <div className="flex shrink-0 items-center gap-2 text-xs text-stone-500">
                <span
                  className={cn(
                    'inline-flex h-1.5 w-1.5 rounded-full transition-colors',
                    dirty ? 'bg-amber-500' : 'bg-stone-300',
                  )}
                  aria-hidden
                />
                {dirty ? 'Unsaved changes' : isSample ? 'Bundled template' : 'Saved'}
              </div>
            )}
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 bg-stone-50/60 px-8 py-3">
          {/* Left: token meter */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="group flex items-center gap-3 rounded-md px-2 py-1 text-left transition-colors hover:bg-stone-100"
              >
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5">
                    <span className={cn('font-mono text-[11px] font-medium tabular-nums', meter.textClass)}>
                      {formatNumber(tokenEstimate)} <span className="text-stone-400">/ {formatNumber(TOKEN_HARD_CAP)} tokens</span>
                    </span>
                    {meter.level === 'over' && <Warning size={12} className="text-rose-500" weight="fill" />}
                  </div>
                  <div className={cn('h-1 w-32 overflow-hidden rounded-full', meter.trackClass)}>
                    <div
                      className={cn('h-full rounded-full transition-[width,background-color] duration-300', meter.fillClass)}
                      style={{ width: `${fillPct}%` }}
                    />
                  </div>
                </div>
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-xs">
              <p className="text-xs leading-relaxed">
                Estimated tokens added to every brand-aware studio prompt. Soft warn at{' '}
                {formatNumber(TOKEN_WARN)}, hard cap at {formatNumber(TOKEN_HARD_CAP)}.
              </p>
            </TooltipContent>
          </Tooltip>

          {/* Right: actions */}
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleResetToSample}
              disabled={loading || saving}
              className="text-stone-600 hover:text-stone-900"
            >
              <ArrowCounterClockwise size={14} className="mr-1.5" />
              Reset to template
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setBootstrapOpen(true)}
              disabled={loading || saving}
              className="border-amber-200 bg-amber-50/50 text-amber-800 hover:bg-amber-100/60 hover:text-amber-900"
            >
              <Sparkle size={14} className="mr-1.5" weight="fill" />
              Bootstrap with AI
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleSave}
              disabled={loading || saving || !dirty || overCap}
              className="bg-amber-600 text-white hover:bg-amber-700 disabled:bg-stone-200 disabled:text-stone-400"
            >
              {saving ? (
                <>
                  <CircleNotch size={14} className="mr-1.5 animate-spin" />
                  Saving
                </>
              ) : savedRecently ? (
                <>
                  <Check size={14} className="mr-1.5" weight="bold" />
                  Saved
                </>
              ) : (
                'Save'
              )}
            </Button>
          </div>
        </div>

        {/* Sample banner */}
        {isSample && !loading && (
          <div className="border-b border-amber-100 bg-amber-50/40 px-8 py-2.5">
            <p className="text-xs italic leading-relaxed text-amber-900/80">
              You're looking at the bundled starting template. Edit it directly, or
              click <span className="not-italic font-medium">Bootstrap with AI</span> to
              draft something tailored. Nothing reaches studio agents until you Save.
            </p>
          </div>
        )}

        {/* Split-pane editor / preview */}
        <div className="flex min-h-0 flex-1">
          {loading ? (
            <div className="flex w-full items-center justify-center text-sm text-stone-500">
              <CircleNotch size={18} className="mr-2 animate-spin text-amber-600" />
              Loading spec…
            </div>
          ) : (
            <>
              <div className="min-w-0 flex-[3] border-r border-stone-200" data-color-mode="light">
                <MDEditor
                  value={content}
                  onChange={(v) => setContent(v ?? '')}
                  preview="edit"
                  hideToolbar={false}
                  height="100%"
                  visibleDragbar={false}
                  textareaProps={{
                    placeholder: 'Start typing your design spec, or click Bootstrap with AI…',
                    spellCheck: true,
                  }}
                  className="!border-0 !shadow-none"
                />
              </div>
              <div className="min-w-0 flex-[2] overflow-y-auto bg-amber-50/10 px-8 py-7">
                {content.trim() ? (
                  <article
                    className={cn(
                      'prose prose-stone max-w-none',
                      'prose-headings:font-serif prose-headings:tracking-tight prose-headings:text-stone-900',
                      'prose-h1:text-2xl prose-h1:mb-3 prose-h1:mt-0',
                      'prose-h2:text-lg prose-h2:mt-8 prose-h2:mb-2 prose-h2:font-semibold',
                      'prose-h3:text-sm prose-h3:uppercase prose-h3:tracking-wider prose-h3:text-amber-800',
                      'prose-p:leading-[1.65] prose-p:text-stone-700',
                      'prose-strong:text-stone-900',
                      'prose-li:my-0.5',
                      'prose-code:rounded prose-code:bg-stone-100 prose-code:px-1 prose-code:py-0.5 prose-code:text-[0.85em] prose-code:font-normal prose-code:text-amber-800 prose-code:before:content-none prose-code:after:content-none',
                      'prose-blockquote:border-l-amber-400 prose-blockquote:bg-amber-50/50 prose-blockquote:py-0.5 prose-blockquote:not-italic',
                      'prose-hr:border-stone-200',
                    )}
                  >
                    <MDEditor.Markdown source={content} style={{ background: 'transparent', color: 'inherit' }} />
                  </article>
                ) : (
                  <div className="flex h-full items-center justify-center text-center">
                    <p className="text-sm italic text-stone-400">Nothing to preview yet.</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <DesignBootstrapDialog
          open={bootstrapOpen}
          onOpenChange={setBootstrapOpen}
          onResult={handleBootstrapResult}
        />
      </div>
    </TooltipProvider>
  );
};
