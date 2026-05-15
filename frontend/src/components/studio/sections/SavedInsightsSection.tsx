/**
 * SavedInsightsSection — auto-refreshing chat prompts in the Studio panel.
 *
 * Renders compact library-card rows for each saved insight. Clicking a
 * card opens a 520px detail sheet with full markdown rendering, refresh,
 * and a button that jumps to the source chat for full history.
 *
 * Hidden when there are no saved insights so we don't add empty noise to
 * the Studio panel. Polls every 15s while any insight is mid-refresh so
 * the latest result lands without a manual reload.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Lightbulb } from '@phosphor-icons/react';
import { useStudioContext } from '../studio-hooks';
import { insightsAPI, type SavedInsight } from '@/lib/api/insights';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';
import { InsightCard } from '../savedInsights/InsightCard';
import { InsightDetailSheet } from '../savedInsights/InsightDetailSheet';

const log = createLogger('saved-insights-section');

const POLL_INTERVAL_MS = 15_000;

export const SavedInsightsSection: React.FC = () => {
  const { projectId } = useStudioContext();
  const { success, error } = useToast();

  const [insights, setInsights] = useState<SavedInsight[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [openInsightId, setOpenInsightId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<SavedInsight | null>(null);

  const loadInsights = useCallback(async () => {
    try {
      const rows = await insightsAPI.list(projectId);
      setInsights(rows);
    } catch (err) {
      log.error({ err }, 'failed to load insights');
    } finally {
      setLoaded(true);
    }
  }, [projectId]);

  useEffect(() => {
    loadInsights();
  }, [loadInsights]);

  // Reload when a new insight is saved from the chat. SaveAsInsightButton
  // dispatches this event so the new card appears immediately — without
  // it, the section stays stale until the user reloads the page.
  useEffect(() => {
    const handler = () => loadInsights();
    window.addEventListener('noobbook:insight:saved', handler);
    return () => window.removeEventListener('noobbook:insight:saved', handler);
  }, [loadInsights]);

  // Poll while any insight is refreshing so the latest result lands
  // without a manual reload. Stops cleanly when nothing's running. We
  // also fan a `noobbook:chat:updated` event whenever an insight flips
  // from running → not-running so ChatPanel can re-fetch the source
  // chat if the user happens to be viewing it (the refresh appended a
  // new turn to that chat).
  const prevRunningRef = React.useRef<Set<string>>(new Set());
  useEffect(() => {
    const running = new Set(insights.filter((i) => i.is_running).map((i) => i.id));
    // Anything in prev but not in current = just finished.
    prevRunningRef.current.forEach((id) => {
      if (!running.has(id)) {
        const finished = insights.find((i) => i.id === id);
        const chatId = finished?.chat_id;
        if (chatId) {
          window.dispatchEvent(
            new CustomEvent('noobbook:chat:updated', { detail: { chatId } }),
          );
        }
      }
    });
    prevRunningRef.current = running;

    if (running.size === 0) return;
    const interval = setInterval(loadInsights, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [insights, loadInsights]);

  const handleRefresh = useCallback(
    async (insight: SavedInsight) => {
      const ok = await insightsAPI.refresh(projectId, insight.id);
      if (ok) {
        // Optimistically flip is_running so the spinner shows immediately;
        // the poll picks up the canonical state from the backend.
        setInsights((prev) =>
          prev.map((row) => (row.id === insight.id ? { ...row, is_running: true } : row)),
        );
        success('Refresh started');
      } else {
        error('Could not start refresh');
      }
    },
    [projectId, success, error],
  );

  const handleConfirmDelete = useCallback(async () => {
    if (!pendingDelete) return;
    const insight = pendingDelete;
    setPendingDelete(null);
    if (openInsightId === insight.id) setOpenInsightId(null);
    const ok = await insightsAPI.remove(projectId, insight.id);
    if (ok) {
      setInsights((prev) => prev.filter((row) => row.id !== insight.id));
      success('Insight deleted');
    } else {
      error('Could not delete insight');
    }
  }, [pendingDelete, projectId, openInsightId, success, error]);

  // Switching to the source chat lives on ProjectWorkspace — we fire a
  // window event it listens for. Keeps the studio decoupled from the
  // chat panel's internals.
  const handleJumpToChat = useCallback((insight: SavedInsight) => {
    if (!insight.chat_id) return;
    window.dispatchEvent(
      new CustomEvent('noobbook:chat:open', { detail: { chatId: insight.chat_id } }),
    );
    setOpenInsightId(null);
  }, []);

  const openInsight = insights.find((i) => i.id === openInsightId) || null;

  if (!loaded || insights.length === 0) {
    return null;
  }

  return (
    <section className="space-y-2.5">
      <div className="flex items-center gap-2 px-1">
        <Lightbulb size={16} weight="bold" className="text-amber-600" />
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-700">
          Saved Insights
        </h3>
        <span className="text-[11px] text-stone-400">{insights.length}</span>
      </div>

      <div className="space-y-2">
        {insights.map((insight) => (
          <InsightCard
            key={insight.id}
            insight={insight}
            onOpen={(i) => setOpenInsightId(i.id)}
            onRefresh={handleRefresh}
            onDelete={(i) => setPendingDelete(i)}
            onJumpToChat={handleJumpToChat}
          />
        ))}
      </div>

      <InsightDetailSheet
        insight={openInsight}
        open={!!openInsight}
        onOpenChange={(open) => !open && setOpenInsightId(null)}
        onRefresh={handleRefresh}
        onJumpToChat={handleJumpToChat}
      />

      <AlertDialog open={!!pendingDelete} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete saved insight?</AlertDialogTitle>
            <AlertDialogDescription>
              This stops the scheduled refresh and removes the stored result.
              The chat where it was saved stays intact.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
};
