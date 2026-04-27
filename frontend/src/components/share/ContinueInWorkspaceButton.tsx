import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowSquareOut, CircleNotch, Sparkle } from '@phosphor-icons/react';
import { Button } from '../ui/button';
import { useToast } from '../ui/use-toast';
import { ToastContainer } from '../ui/toast';
import { shareAPI } from '@/lib/api/share';
import { createLogger } from '@/lib/logger';

const log = createLogger('share-fork');

interface ContinueInWorkspaceButtonProps {
  token: string;
  chatId: string | null;
  isAuthenticated: boolean;
  /**
   * Optional override for where to redirect logged-out viewers. Defaults
   * to `/auth?redirect=<current url>` so the AuthPage can bounce them
   * back to the share view after sign-in.
   */
  signInHref?: string;
}

/**
 * ContinueInWorkspaceButton
 *
 * Pinned to the bottom of the chat detail pane in share mode, in place
 * of the input area. Soft amber ring, generous padding, friendly tone.
 *
 * For logged-in viewers: clones the entire shared project — sources,
 * chunks, Pinecone vectors, all chats — into the viewer's account and
 * deep-links them straight to the cloned chat they were reading.
 * For anonymous viewers: shows a sign-in link that round-trips back to
 * the share URL after auth.
 */
export const ContinueInWorkspaceButton: React.FC<ContinueInWorkspaceButtonProps> = ({
  token,
  chatId,
  isAuthenticated,
  signInHref,
}) => {
  const { toasts, dismissToast, error } = useToast();
  const navigate = useNavigate();
  const [forking, setForking] = useState(false);

  const disabled = !chatId || forking;

  const handleFork = async () => {
    if (!chatId) return;
    try {
      setForking(true);
      const res = await shareAPI.fork(token, chatId);
      const result = res.data;
      // Project workspace doesn't deep-link to chats yet, so always
      // navigate to the project root — the cloned chats are visible in
      // the chat list and tagged with their fork lineage.
      navigate(`/projects/${result.project.id}`);
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
      log.error({ err }, 'fork failed');
      error(msg || 'Could not copy this project. Try again?');
      setForking(false);
    }
  };

  const fallbackSignIn = (() => {
    if (signInHref) return signInHref;
    if (typeof window === 'undefined') return '/auth';
    const here = window.location.pathname + window.location.hash;
    return `/auth?redirect=${encodeURIComponent(here)}`;
  })();

  return (
    <div className="px-6 pt-4 pb-6">
      <div className="relative rounded-2xl border border-primary/25 bg-primary/[0.04] px-5 py-4">
        {/* Hairline accent — the only saturated brand mark on the page */}
        <span
          aria-hidden
          className="absolute left-5 right-5 -top-px h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent"
        />
        <div className="flex items-start gap-3.5">
          <div className="flex-shrink-0 mt-0.5 text-primary">
            <Sparkle size={18} weight="fill" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground leading-snug">
              Make this project yours
            </p>
            <p className="text-[12.5px] text-muted-foreground leading-relaxed mt-1">
              We&apos;ll copy the sources, chats, and citations into a new project in your workspace so you can keep working.
            </p>
            <div className="mt-3">
              {isAuthenticated ? (
                <Button
                  onClick={handleFork}
                  disabled={disabled}
                  size="sm"
                  className="gap-2 h-8"
                >
                  {forking ? (
                    <>
                      <CircleNotch size={14} className="animate-spin" />
                      Copying project…
                    </>
                  ) : (
                    <>
                      Make a copy in your workspace
                      <ArrowSquareOut size={14} weight="bold" />
                    </>
                  )}
                </Button>
              ) : (
                <Button asChild size="sm" className="gap-2 h-8">
                  <a href={fallbackSignIn}>
                    Sign in to make a copy
                    <ArrowSquareOut size={14} weight="bold" />
                  </a>
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
