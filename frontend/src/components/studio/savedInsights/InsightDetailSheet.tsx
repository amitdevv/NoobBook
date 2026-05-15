/**
 * InsightDetailSheet — right-side reading surface for one saved insight.
 *
 * Why a Sheet (not inline expand or modal):
 * - The Studio panel is ~25vw, way too narrow to render rich markdown.
 *   The sheet opens at ~480px and overlays the chat, giving the result
 *   real reading width while keeping the chat one click away.
 * - Modals trap attention; sheets feel like a peek you can dismiss
 *   with one esc/click. Matches the cozy editorial vibe of the rest of
 *   the app — like flipping over a library card to read the back.
 */
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowsClockwise,
  ArrowUpRight,
  CircleNotch,
  Warning,
} from '@phosphor-icons/react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import type { SavedInsight } from '@/lib/api/insights';

const cadenceLabel = (c: SavedInsight['cadence']) => (c === 'daily' ? 'Daily' : 'Weekly');

const formatLastRun = (iso: string | null): string => {
  if (!iso) return 'Never run';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Never run';
  const diffMs = Date.now() - d.getTime();
  const mins = Math.round(diffMs / 60_000);
  if (mins < 1) return 'refreshed just now';
  if (mins < 60) return `refreshed ${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `refreshed ${hours}h ago`;
  const days = Math.round(hours / 24);
  return `refreshed ${days}d ago`;
};

interface Props {
  insight: SavedInsight | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRefresh: (insight: SavedInsight) => void;
  onJumpToChat: (insight: SavedInsight) => void;
}

export const InsightDetailSheet: React.FC<Props> = ({
  insight,
  open,
  onOpenChange,
  onRefresh,
  onJumpToChat,
}) => {
  if (!insight) return null;

  const running = insight.is_running;
  const hasResult = !!(insight.last_result && insight.last_result.trim());

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        // Override shadcn's default sm:max-w-sm (384px) — the editorial
        // markdown needs more reading width to breathe.
        className="w-full sm:max-w-[520px] p-0 bg-[#fcfaf6] flex flex-col"
      >
        {/* Header — masthead-style with serif title and meta */}
        <SheetHeader className="px-6 pt-6 pb-4 space-y-3 border-b border-stone-200/70">
          <p className="text-[10px] uppercase tracking-[0.18em] text-amber-700 font-semibold">
            ━━ Insight
          </p>
          <SheetTitle className="font-serif italic text-2xl leading-tight text-stone-900 text-left">
            {insight.title}
          </SheetTitle>
          <SheetDescription className="text-xs text-stone-500 text-left">
            <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-700 mr-2">
              {cadenceLabel(insight.cadence)}
            </span>
            {running ? 'refreshing now…' : formatLastRun(insight.last_run_at)}
          </SheetDescription>

          <div className="flex items-center gap-2 pt-1">
            <Button
              size="sm"
              onClick={() => onRefresh(insight)}
              disabled={running}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              {running ? (
                <>
                  <CircleNotch size={14} className="mr-1.5 animate-spin" />
                  Refreshing
                </>
              ) : (
                <>
                  <ArrowsClockwise size={14} weight="bold" className="mr-1.5" />
                  Refresh now
                </>
              )}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onJumpToChat(insight)}
              disabled={!insight.chat_id}
              title={insight.chat_id ? 'Open the source chat' : 'No chat linked yet'}
            >
              <ArrowUpRight size={14} weight="bold" className="mr-1.5" />
              Open the chat
            </Button>
          </div>
        </SheetHeader>

        {/* Body — prompt + result with proper markdown rendering */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Prompt block — set off as a quote so the question reads */}
          {/* like an editor's note before the article. */}
          <section>
            <p className="text-[10px] uppercase tracking-[0.16em] text-stone-500 font-medium mb-1.5">
              Prompt
            </p>
            <blockquote className="border-l-2 border-amber-300 pl-3 py-1 text-sm italic text-stone-700 whitespace-pre-wrap">
              {insight.prompt}
            </blockquote>
          </section>

          {insight.last_error && (
            <section className="rounded-md bg-rose-50 border border-rose-200 px-3 py-2.5">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-rose-700">
                <Warning size={12} weight="bold" />
                Last refresh failed
              </div>
              <p className="mt-1 text-xs text-rose-800 whitespace-pre-wrap">
                {insight.last_error}
              </p>
            </section>
          )}

          <section>
            <p className="text-[10px] uppercase tracking-[0.16em] text-stone-500 font-medium mb-2">
              {hasResult ? 'Latest answer' : 'No answer yet'}
            </p>
            {hasResult ? (
              <div className="prose prose-sm prose-stone max-w-none prose-headings:font-serif prose-headings:italic prose-pre:bg-stone-900 prose-pre:text-stone-100">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {insight.last_result ?? ''}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="text-sm text-stone-500 italic">
                Hit <span className="font-medium text-amber-700">Refresh now</span> to fetch the
                first answer. The scheduler will keep it updated on its{' '}
                {cadenceLabel(insight.cadence).toLowerCase()} cadence after that.
              </p>
            )}
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
};
