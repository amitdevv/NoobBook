import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowSquareOut,
  CircleNotch,
  DownloadSimple,
  Hash,
  Info,
  LockKey,
  ChatCircle,
  Globe,
} from '@phosphor-icons/react';
import { ChatMessages } from '../chat/ChatMessages';
import { Button } from '../ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';
import { ToastContainer } from '../ui/toast';
import { useToast } from '../ui/use-toast';
import { ContinueInWorkspaceButton } from './ContinueInWorkspaceButton';
import { shareAPI, type ShareRoot } from '@/lib/api/share';
import type { Chat, ChatMetadata } from '@/lib/api/chats';
import { exportChatAsPdf } from '@/lib/exportChatPdf';
import { createLogger } from '@/lib/logger';

const log = createLogger('share-workspace');

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ready'; root: ShareRoot }
  | { kind: 'error'; status: number; message: string; code?: string };

const HASH_KEY = 'chat=';

function readChatFromHash(): string | null {
  if (typeof window === 'undefined') return null;
  const hash = window.location.hash.replace(/^#/, '');
  if (!hash.startsWith(HASH_KEY)) return null;
  return hash.slice(HASH_KEY.length) || null;
}

function writeChatToHash(chatId: string | null) {
  if (typeof window === 'undefined') return;
  if (chatId) {
    history.replaceState(null, '', `${window.location.pathname}#${HASH_KEY}${chatId}`);
  } else {
    history.replaceState(null, '', window.location.pathname);
  }
}

/**
 * ShareWorkspace
 *
 * The shared, read-only counterpart to ProjectWorkspace. Single-page
 * layout: a quiet top bar, a slim left rail of chats, and the chat
 * detail at the right with a fork CTA at the bottom in place of the
 * input. No project chrome, no navigation to other surfaces.
 *
 * Aesthetic: editorial / library. Generous spacing, fine rules,
 * one accent color. Treat the page like a Notion shared view —
 * inviting to read, never apologetic about being read-only.
 */
export const ShareWorkspace: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { toasts, dismissToast, error } = useToast();

  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [activeChatId, setActiveChatId] = useState<string | null>(readChatFromHash());
  const [activeChat, setActiveChat] = useState<Chat | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [exportingChat, setExportingChat] = useState(false);

  // ── Load share root ──────────────────────────────────────────
  useEffect(() => {
    if (!token) {
      setState({ kind: 'error', status: 404, message: 'Missing share token.' });
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await shareAPI.getRoot(token);
        if (cancelled) return;
        const root = res.data;
        setState({ kind: 'ready', root });
        // For chat-scoped shares the backend returns only one chat —
        // force-select it and ignore any hash that points at a sibling
        // chat the viewer never had access to. Project-wide shares
        // still honor the hash so deep-links survive refresh.
        const initial = root.share.chat_id
          ? root.chats[0]?.id ?? null
          : readChatFromHash() ?? root.chats[0]?.id ?? null;
        setActiveChatId(initial);
      } catch (err) {
        if (cancelled) return;
        const status = (err as { response?: { status?: number } })?.response?.status ?? 500;
        const data = (err as { response?: { data?: { error?: string; code?: string } } })?.response?.data;
        log.warn({ err, status }, 'share root failed');
        setState({
          kind: 'error',
          status,
          message: data?.error || 'Could not load this share link.',
          code: data?.code,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // ── Load active chat detail when selection changes ───────────
  useEffect(() => {
    if (!token || !activeChatId) {
      setActiveChat(null);
      return;
    }
    let cancelled = false;
    setChatLoading(true);
    (async () => {
      try {
        const res = await shareAPI.getChat(token, activeChatId);
        if (cancelled) return;
        setActiveChat(res.data.chat);
      } catch (err) {
        if (cancelled) return;
        log.error({ err, activeChatId }, 'share chat fetch failed');
        error('Could not load that chat.');
        setActiveChat(null);
      } finally {
        if (!cancelled) setChatLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, activeChatId, error]);

  // Persist selection in the URL hash so refresh restores it.
  useEffect(() => {
    writeChatToHash(activeChatId);
  }, [activeChatId]);

  // Rewrite studio asset URLs so <img> tags inside chat messages
  // resolve through the share-token proxy instead of the owner-only
  // /api/v1/projects path (which would 401 without a JWT).
  const studioAssetRewriter = useMemo(() => {
    if (!token) return undefined;
    const re = /\/api\/v1\/projects\/[^/]+\/studio\/([^/]+)\/([^/]+)\/(.+)$/;
    return (url: string): string => {
      const m = url.match(re);
      if (!m) return url;
      const [, kind, jobId, file] = m;
      return shareAPI.studioAssetUrl(token, kind, jobId, file);
    };
  }, [token]);

  // PDF export — declared before any early return so the hook order stays
  // stable across loading / error / ready states (React error #310 guard).
  // We dereference state.root inside via a guard rather than at hook setup.
  const readyRoot = state.kind === 'ready' ? state.root : null;
  const activeChatRef = state.kind === 'ready' ? activeChat : null;
  const handleExport = useCallback(async () => {
    if (!activeChatRef || !readyRoot) return;
    try {
      setExportingChat(true);
      await exportChatAsPdf({
        chat: activeChatRef,
        projectId: readyRoot.project.id,
        projectName: readyRoot.project.name,
      });
    } catch (err) {
      log.error({ err }, 'export failed');
      error('PDF export failed');
    } finally {
      setExportingChat(false);
    }
  }, [activeChatRef, readyRoot, error]);

  // ── Branches ────────────────────────────────────────────────
  if (state.kind === 'loading') {
    return <SplashLoading />;
  }

  if (state.kind === 'error') {
    return (
      <SplashError
        status={state.status}
        message={state.message}
        code={state.code}
        token={token}
        onSignIn={() => {
          // Full navigation (not react-router navigate) so App.tsx re-evaluates
          // the top-level auth gate on a fresh mount and renders <AuthPage />.
          // /auth isn't a route in BrowserRouter; client-side navigate to it
          // would fall through to the dashboard catch-all.
          window.location.assign(
            `/auth?redirect=${encodeURIComponent(window.location.pathname + window.location.hash)}`,
          );
        }}
        onHome={() => navigate('/')}
      />
    );
  }

  const { root } = state;
  const chats = root.chats;
  const isAuthed = root.viewer.is_authenticated;
  // Hide the chat rail entirely when the share is scoped to one chat.
  // Showing a single-row "Chats" list with no navigation value just
  // adds noise; chat-scoped viewers came for one conversation.
  const isChatScopedShare = !!root.share.chat_id;

  return (
    <div className="min-h-screen bg-stone-50/40">
      <TopBar
        root={root}
        token={token!}
        canExport={!!activeChat}
        exportingChat={exportingChat}
        onExport={handleExport}
        onSignIn={() => {
          // Full navigation (not react-router navigate) so App.tsx re-evaluates
          // the top-level auth gate on a fresh mount and renders <AuthPage />.
          // /auth isn't a route in BrowserRouter; client-side navigate to it
          // would fall through to the dashboard catch-all.
          window.location.assign(
            `/auth?redirect=${encodeURIComponent(window.location.pathname + window.location.hash)}`,
          );
        }}
      />

      <div className="mx-auto max-w-[1180px] px-4 sm:px-6 lg:px-8 pb-10">
        <div className="grid grid-cols-12 gap-6">
          {!isChatScopedShare && (
            <aside className="col-span-12 md:col-span-4 lg:col-span-3">
              <ChatRail
                chats={chats}
                activeChatId={activeChatId}
                onSelect={setActiveChatId}
              />
            </aside>
          )}

          <main
            className={
              isChatScopedShare
                ? 'col-span-12'
                : 'col-span-12 md:col-span-8 lg:col-span-9'
            }
          >
            {activeChatId ? (
              <ChatPane
                chat={activeChat}
                loading={chatLoading}
                token={token!}
                isAuthed={isAuthed}
                studioAssetRewriter={studioAssetRewriter}
                projectId={root.project.id}
              />
            ) : (
              <EmptyChatState />
            )}
          </main>
        </div>
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
// Top bar
// ─────────────────────────────────────────────────────────────────

interface TopBarProps {
  root: ShareRoot;
  token: string;
  canExport: boolean;
  exportingChat: boolean;
  onExport: () => void;
  onSignIn: () => void;
}

const TopBar: React.FC<TopBarProps> = ({ root, canExport, exportingChat, onExport, onSignIn }) => {
  const isAuthed = root.viewer.is_authenticated;
  return (
    <header className="border-b bg-background/80 backdrop-blur-sm sticky top-0 z-20">
      <div className="mx-auto max-w-[1180px] px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <span className="inline-flex items-center justify-center h-7 w-7 rounded-md bg-primary/10 text-primary">
            {root.share.mode === 'public' ? (
              <Globe size={14} weight="bold" />
            ) : (
              <LockKey size={14} weight="bold" />
            )}
          </span>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold leading-tight truncate">
              {root.project.name}
            </h1>
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide bg-primary/8 text-primary border border-primary/15">
                Read-only
              </span>
              {root.viewer.email ? (
                <span className="truncate">Signed in as {root.viewer.email}</span>
              ) : (
                <span>Shared via link</span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onExport}
                  disabled={!canExport || exportingChat}
                  className="gap-1.5 h-8"
                >
                  {exportingChat ? (
                    <CircleNotch size={14} className="animate-spin" />
                  ) : (
                    <DownloadSimple size={14} />
                  )}
                  <span className="hidden sm:inline">PDF</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                Download chat as PDF
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {!isAuthed && (
            <Button variant="outline" size="sm" onClick={onSignIn} className="gap-1.5 h-8">
              Sign in
              <ArrowSquareOut size={13} />
            </Button>
          )}
        </div>
      </div>
    </header>
  );
};

// ─────────────────────────────────────────────────────────────────
// Left rail: chats
// ─────────────────────────────────────────────────────────────────

interface ChatRailProps {
  chats: ChatMetadata[];
  activeChatId: string | null;
  onSelect: (id: string) => void;
}

const ChatRail: React.FC<ChatRailProps> = ({ chats, activeChatId, onSelect }) => (
  <div className="sticky top-[calc(56px+24px)]">
    <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground mb-2 px-2">
      Chats
    </div>
    {chats.length === 0 ? (
      <div className="rounded-lg border border-dashed border-border/70 p-4 text-xs text-muted-foreground text-center">
        No chats in this project.
      </div>
    ) : (
      <nav className="space-y-1 max-h-[calc(100vh-160px)] overflow-y-auto pr-1 -mr-1">
        {chats.map((chat) => {
          const isActive = chat.id === activeChatId;
          return (
            <button
              key={chat.id}
              onClick={() => onSelect(chat.id)}
              className={[
                'w-full text-left rounded-md px-2.5 py-2 transition-colors group',
                isActive
                  ? 'bg-primary/10 ring-1 ring-primary/20'
                  : 'hover:bg-muted/60',
              ].join(' ')}
            >
              <div className="flex items-start gap-2">
                <Hash
                  size={13}
                  className={[
                    'mt-0.5 flex-shrink-0',
                    isActive ? 'text-primary' : 'text-muted-foreground/70',
                  ].join(' ')}
                />
                <div className="flex-1 min-w-0">
                  <div className={[
                    'text-[13px] truncate',
                    isActive ? 'font-medium text-foreground' : 'text-foreground/85',
                  ].join(' ')}>
                    {chat.title || 'Untitled'}
                  </div>
                  <div className="text-[10.5px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
                    <span>{chat.message_count} {chat.message_count === 1 ? 'message' : 'messages'}</span>
                    {chat.updated_at && (
                      <>
                        <span aria-hidden>·</span>
                        <span>{relativeTime(chat.updated_at)}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </nav>
    )}
  </div>
);

// ─────────────────────────────────────────────────────────────────
// Right pane: chat detail
// ─────────────────────────────────────────────────────────────────

interface ChatPaneProps {
  chat: Chat | null;
  loading: boolean;
  token: string;
  isAuthed: boolean;
  studioAssetRewriter?: (url: string) => string;
  projectId: string;
}

const ChatPane: React.FC<ChatPaneProps> = ({
  chat,
  loading,
  token,
  isAuthed,
  studioAssetRewriter,
  projectId,
}) => {
  if (loading && !chat) {
    return (
      <div className="rounded-2xl border bg-card overflow-hidden">
        <div className="border-b px-6 py-4">
          <div className="h-4 w-48 bg-muted/60 rounded animate-pulse" />
          <div className="h-3 w-24 bg-muted/40 rounded mt-2 animate-pulse" />
        </div>
        <div className="px-6 py-8 space-y-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-2">
              <div className="h-3 w-40 bg-muted/50 rounded animate-pulse" />
              <div className="h-3 w-3/4 bg-muted/40 rounded animate-pulse" />
              <div className="h-3 w-2/3 bg-muted/40 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!chat) {
    return <EmptyChatState />;
  }

  return (
    <article className="rounded-2xl border bg-card overflow-hidden flex flex-col min-h-[calc(100vh-140px)]">
      <header className="border-b px-6 py-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold truncate">{chat.title}</h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {chat.messages?.length ?? 0} {(chat.messages?.length ?? 0) === 1 ? 'message' : 'messages'}
          </p>
        </div>
      </header>

      {/* flex flex-col here is load-bearing: ChatMessages's outer wrapper
         is `relative flex-1 min-h-0` and its scroll viewport is positioned
         `absolute inset-0`. Without a flex parent, the flex-1 on the
         relative div doesn't claim height, the absolute viewport
         collapses to 0×0, and 15 messages render into nothing — exactly
         the empty pane the share view was showing. */}
      <div className="flex-1 min-h-0 flex flex-col">
        <ChatMessages
          messages={chat.messages || []}
          sending={false}
          projectId={projectId}
          readOnly
          studioAssetRewriter={studioAssetRewriter}
        />
      </div>

      <ContinueInWorkspaceButton
        token={token}
        chatId={chat.id}
        isAuthenticated={isAuthed}
      />
    </article>
  );
};

const EmptyChatState: React.FC = () => (
  <div className="rounded-2xl border border-dashed bg-card/40 px-6 py-16 flex flex-col items-center justify-center text-center">
    <div className="text-stone-400 mb-2.5">
      <ChatCircle size={28} weight="duotone" />
    </div>
    <p className="text-sm font-medium">Select a chat from the left to read it</p>
    <p className="text-xs text-muted-foreground mt-1 max-w-[300px] leading-relaxed">
      Citations, studio outputs, and conversation history are all here in read-only form.
    </p>
  </div>
);

// ─────────────────────────────────────────────────────────────────
// Splash states (loading / error)
// ─────────────────────────────────────────────────────────────────

const SplashLoading: React.FC = () => (
  <div className="min-h-screen flex items-center justify-center bg-stone-50/60">
    <div className="flex flex-col items-center gap-3 text-muted-foreground">
      <CircleNotch size={22} className="animate-spin text-primary" />
      <p className="text-xs uppercase tracking-[0.12em]">Loading shared project</p>
    </div>
  </div>
);

interface SplashErrorProps {
  status: number;
  message: string;
  code?: string;
  token: string | undefined;
  onSignIn: () => void;
  onHome: () => void;
}

const SplashError: React.FC<SplashErrorProps> = ({ status, message, code, onSignIn, onHome }) => {
  const wantsSignIn = status === 401 || code === 'auth_required' || code === 'not_invited';
  const isGone = status === 410 || status === 404;
  const isNotInvited = code === 'not_invited';

  // For not_invited: the viewer IS signed in, just with the wrong email.
  // Sign them out first so AuthPage actually renders on /auth — otherwise
  // the App-level auth gate (`!isAuthenticated`) sees they're already
  // logged in and falls through to the dashboard catch-all route.
  const handleSignIn = async () => {
    if (isNotInvited) {
      try {
        const { authAPI } = await import('@/lib/api/auth');
        await authAPI.signOut();
      } catch {
        // Even if the network call fails, clear local session and proceed.
        const { clearSession } = await import('@/lib/auth/session');
        clearSession();
      }
    }
    onSignIn();
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50/60 px-6">
      <div className="max-w-md w-full text-center">
        <div className="mx-auto mb-5 inline-flex items-center justify-center h-12 w-12 rounded-full bg-stone-200/60 text-stone-500">
          {isGone ? (
            <Info size={20} weight="duotone" />
          ) : (
            <LockKey size={20} weight="duotone" />
          )}
        </div>
        <h1 className="text-base font-semibold text-foreground">
          {isGone ? 'This share link is no longer active' : 'Access required'}
        </h1>
        <p className="text-[13px] text-muted-foreground mt-2 leading-relaxed">
          {message}
        </p>
        <div className="mt-6 flex items-center justify-center gap-2">
          {wantsSignIn && (
            <Button onClick={handleSignIn} size="sm">
              {isNotInvited ? 'Use a different account' : 'Sign in'}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={onHome}>
            Go home
          </Button>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return 'just now';
  const m = Math.round(ms / 60_000);
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.round(h / 24);
  if (d < 7) return `${d}d`;
  const w = Math.round(d / 7);
  if (w < 5) return `${w}w`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
