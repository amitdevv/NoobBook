/**
 * ProjectUsageSection Component
 *
 * Renders inside the Project Settings dialog as the "Usage & costs" section.
 * Reads the same CostTracking payload the header chip uses (no new endpoint)
 * and shows three things the small hover tooltip can't:
 *
 *   1. A headline number with a prompt-cache savings line
 *      ("$0.42 spent · saved $0.31 via prompt caching")
 *   2. Per-model rows — Opus / Sonnet / Haiku — each showing input, output,
 *      and cache token counts side-by-side
 *   3. An image-gen rollup if the project has used it
 *
 * Intentionally read-only and inert: no charts, no time series, no refresh
 * button — the parent already refreshes costs after each chat turn via the
 * `costsVersion` counter, so this surface stays in sync automatically.
 */

import React from 'react';
import { CurrencyDollar, Sparkle, ImageSquare } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import type { CostTracking, ModelCostBreakdown } from '../../lib/api';

interface ProjectUsageSectionProps {
  costs: CostTracking | null;
  loading?: boolean;
}

const formatCost = (cost: number): string => {
  if (cost === 0) return '$0.00';
  if (cost < 0.01) return `<$0.01`;
  return `$${cost.toFixed(2)}`;
};

const formatTokens = (n: number): string => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
};

const MODEL_LABELS: Record<keyof CostTracking['by_model'], { name: string; rate: string }> = {
  opus:   { name: 'Opus',   rate: '$5 in / $25 out per 1M' },
  sonnet: { name: 'Sonnet', rate: '$3 in / $15 out per 1M' },
  haiku:  { name: 'Haiku',  rate: '$1 in / $5 out per 1M'  },
};

const isBucketActive = (b: ModelCostBreakdown): boolean =>
  (b.input_tokens ?? 0) > 0 ||
  (b.output_tokens ?? 0) > 0 ||
  (b.cache_creation_tokens ?? 0) > 0 ||
  (b.cache_read_tokens ?? 0) > 0;

export const ProjectUsageSection: React.FC<ProjectUsageSectionProps> = ({ costs, loading }) => {
  const totalCost = costs?.total_cost ?? 0;
  const cacheSavings = costs?.cache_savings ?? 0;
  const hasUsage = totalCost > 0;
  const images = costs?.images ?? {};
  const imageModels = Object.keys(images);

  // Compute the share of cost per model for the inline bar chart on each row.
  const maxBucketCost = costs
    ? Math.max(
        costs.by_model.opus?.cost ?? 0,
        costs.by_model.sonnet?.cost ?? 0,
        costs.by_model.haiku?.cost ?? 0,
      )
    : 0;

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium leading-none">Usage & costs</h3>
        <p className="text-xs text-muted-foreground mt-1">
          API spend for this project, tracked per model. Prompt-cache savings show how much
          caching saved you vs. paying the full input rate.
        </p>
      </div>

      {/* ── Hero card ── */}
      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-mono">
              Total spent
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <CurrencyDollar size={20} weight="duotone" className="text-primary shrink-0" />
              <span className="text-3xl font-semibold tabular-nums leading-none">
                {hasUsage ? totalCost.toFixed(2) : '0.00'}
              </span>
              {loading && (
                <span className="text-xs text-muted-foreground italic">refreshing…</span>
              )}
            </div>
          </div>

          {cacheSavings > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-right">
              <div className="text-[10.5px] uppercase tracking-wider text-amber-700 font-mono inline-flex items-center gap-1.5">
                <Sparkle size={11} weight="fill" />
                Cache savings
              </div>
              <div className="mt-0.5 text-base font-semibold text-amber-700 tabular-nums">
                {formatCost(cacheSavings)}
              </div>
              <div className="text-[10.5px] text-amber-700/80 mt-0.5">
                vs. uncached billing
              </div>
            </div>
          )}
        </div>

        {!hasUsage && (
          <p className="mt-3 text-xs text-muted-foreground">
            No API usage yet. Cost tracking starts on your first chat message or studio generation.
          </p>
        )}
      </div>

      {/* ── Per-model breakdown ── */}
      {hasUsage && costs && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-x-4 px-3 py-2 border-b bg-muted/30 text-[10.5px] uppercase tracking-wider text-muted-foreground font-mono">
            <span>Model</span>
            <span className="text-right">Input</span>
            <span className="text-right">Output</span>
            <span className="text-right">Cache (W / R)</span>
            <span className="text-right">Cost</span>
          </div>

          <div className="divide-y">
            {(Object.keys(MODEL_LABELS) as Array<keyof CostTracking['by_model']>).map((key) => {
              const bucket = costs.by_model[key];
              if (!bucket || !isBucketActive(bucket)) return null;
              const cacheW = bucket.cache_creation_tokens ?? 0;
              const cacheR = bucket.cache_read_tokens ?? 0;
              const shareWidth = maxBucketCost > 0
                ? Math.max(2, Math.round((bucket.cost / maxBucketCost) * 100))
                : 0;

              return (
                <div key={key} className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-x-4 px-3 py-3 items-center">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{MODEL_LABELS[key].name}</span>
                      <span className="text-[10.5px] text-muted-foreground font-mono hidden sm:inline">
                        {MODEL_LABELS[key].rate}
                      </span>
                    </div>
                    {/* Cost share bar — purely visual, gives a glance comparison */}
                    <div className="mt-1.5 h-1 w-full bg-muted/60 rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          key === 'opus' && 'bg-primary',
                          key === 'sonnet' && 'bg-primary/70',
                          key === 'haiku' && 'bg-primary/40',
                        )}
                        style={{ width: `${shareWidth}%` }}
                        aria-hidden="true"
                      />
                    </div>
                  </div>
                  <span className="text-xs tabular-nums text-right text-muted-foreground">
                    {formatTokens(bucket.input_tokens)}
                  </span>
                  <span className="text-xs tabular-nums text-right text-muted-foreground">
                    {formatTokens(bucket.output_tokens)}
                  </span>
                  <span className="text-xs tabular-nums text-right text-muted-foreground">
                    {cacheW === 0 && cacheR === 0 ? (
                      <span className="text-muted-foreground/50">—</span>
                    ) : (
                      <>
                        {formatTokens(cacheW)} <span className="text-muted-foreground/50">/</span> {formatTokens(cacheR)}
                      </>
                    )}
                  </span>
                  <span className="text-sm font-medium tabular-nums text-right">
                    {formatCost(bucket.cost)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Image-gen rollup, only if used ── */}
      {imageModels.length > 0 && (
        <div className="rounded-lg border bg-card p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ImageSquare size={14} className="text-muted-foreground" weight="duotone" />
              <span className="text-sm font-medium">Image generation</span>
            </div>
            <span className="text-xs text-muted-foreground font-mono">
              {imageModels.length} {imageModels.length === 1 ? 'model' : 'models'}
            </span>
          </div>
          <div className="divide-y -mx-3">
            {imageModels.map((m) => {
              const bucket = images[m];
              return (
                <div key={m} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
                  <span className="truncate" title={m}>{m}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {bucket.count.toLocaleString()} {bucket.count === 1 ? 'image' : 'images'}
                  </span>
                  <span className="font-medium tabular-nums">{formatCost(bucket.cost)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
