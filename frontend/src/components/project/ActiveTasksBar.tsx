/**
 * ActiveTasksBar Component
 * Educational Note: A floating status bar that shows all active/in-progress
 * tasks for the current project. Polls the backend every 3 seconds and
 * displays source processing, studio generation, and chat sending status.
 * Shows chat names and a "Done" button when a chat finishes processing.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  CaretUp,
  CaretDown,
  FileText,
  Sparkle,
  ChatCircle,
  Gear,
  CircleNotch,
  CheckCircle,
  ArrowRight,
} from '@phosphor-icons/react';
import { API_BASE_URL } from '@/lib/api/client';
import axios from 'axios';

interface ActiveTask {
  id: string;
  type: 'source' | 'studio' | 'background' | 'chat';
  label: string;
  detail: string;
  status: string;
  progress?: number;
  created_at: string;
  chatId?: string;
}

interface CompletedChat {
  chatId: string;
  chatName: string;
  completedAt: string;
}

interface ActiveTasksBarProps {
  projectId: string;
  sendingChatIds?: Set<string>;
  chatNames?: Map<string, string>;
  activeChatId?: string | null;
  onOpenChat?: (chatId: string) => void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const TASK_ICONS: Record<string, React.FC<any>> = {
  source: FileText,
  studio: Sparkle,
  background: Gear,
  chat: ChatCircle,
};

/** Format elapsed time since a timestamp */
function formatElapsed(createdAt: string): string {
  const diff = Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000));
  if (diff < 60) return `${diff}s`;
  const mins = Math.floor(diff / 60);
  const secs = diff % 60;
  return `${mins}m ${secs.toString().padStart(2, '0')}s`;
}

const TaskRow: React.FC<{ task: ActiveTask }> = ({ task }) => {
  const [elapsed, setElapsed] = useState(() => formatElapsed(task.created_at));
  const Icon = TASK_ICONS[task.type] || Gear;

  useEffect(() => {
    const id = setInterval(() => setElapsed(formatElapsed(task.created_at)), 1000);
    return () => clearInterval(id);
  }, [task.created_at]);

  return (
    <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-stone-50 border border-stone-100">
      <div className="flex-shrink-0 w-7 h-7 rounded-md bg-amber-50 border border-amber-200 flex items-center justify-center">
        <Icon size={14} className="text-amber-700" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-stone-800 truncate">{task.label}</p>
        <p className="text-[11px] text-stone-500 truncate">{task.detail}</p>
      </div>
      <span className="text-[11px] text-stone-400 font-mono tabular-nums flex-shrink-0">
        {elapsed}
      </span>
      <CircleNotch size={14} className="animate-spin text-amber-600 flex-shrink-0" />
    </div>
  );
};

const CompletedRow: React.FC<{ chat: CompletedChat; onOpen: () => void; onDismiss: () => void }> = ({ chat, onOpen, onDismiss }) => {
  // Auto-dismiss after 15 seconds
  useEffect(() => {
    const t = setTimeout(onDismiss, 15000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  return (
    <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-green-50 border border-green-200">
      <div className="flex-shrink-0 w-7 h-7 rounded-md bg-green-100 border border-green-200 flex items-center justify-center">
        <CheckCircle size={14} className="text-green-700" weight="fill" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-stone-800 truncate">{chat.chatName}</p>
        <p className="text-[11px] text-green-600">Done</p>
      </div>
      <button
        type="button"
        onClick={onOpen}
        className="flex items-center gap-1 text-[11px] font-medium text-amber-700 bg-amber-100 hover:bg-amber-200 px-2 py-1 rounded-md transition-colors flex-shrink-0"
      >
        Open
        <ArrowRight size={11} weight="bold" />
      </button>
    </div>
  );
};

export const ActiveTasksBar: React.FC<ActiveTasksBarProps> = ({
  projectId,
  sendingChatIds,
  chatNames,
  activeChatId,
  onOpenChat,
}) => {
  const [tasks, setTasks] = useState<ActiveTask[]>([]);
  const [completedChats, setCompletedChats] = useState<CompletedChat[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [visible, setVisible] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Track start times per chat ID so timers don't reset on re-renders
  const chatSendStartsRef = useRef<Map<string, string>>(new Map());
  // Track previous sending IDs to detect completions
  const prevSendingRef = useRef<Set<string>>(new Set());

  const fetchTasks = useCallback(async () => {
    try {
      const resp = await axios.get(`${API_BASE_URL}/projects/${projectId}/active-tasks`);
      if (resp.data.success) {
        setTasks(resp.data.tasks || []);
      }
    } catch (_) {
      // Silently ignore polling errors
    }
  }, [projectId]);

  // Poll every 3 seconds
  useEffect(() => {
    fetchTasks();
    pollRef.current = setInterval(fetchTasks, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchTasks]);

  // Sync start times and detect completions
  const currentIds = sendingChatIds || new Set<string>();
  const starts = chatSendStartsRef.current;
  const names = chatNames || new Map<string, string>();

  // Detect chats that just finished (were in prev but not in current)
  const prevIds = prevSendingRef.current;
  for (const id of prevIds) {
    if (!currentIds.has(id)) {
      // This chat just finished — add to completed list
      const name = names.get(id) || 'Chat';
      setCompletedChats(prev => {
        if (prev.some(c => c.chatId === id)) return prev;
        return [...prev, { chatId: id, chatName: name, completedAt: new Date().toISOString() }];
      });
    }
  }
  prevSendingRef.current = new Set(currentIds);

  // Sync start times
  for (const id of currentIds) {
    if (!starts.has(id)) starts.set(id, new Date().toISOString());
  }
  for (const id of starts.keys()) {
    if (!currentIds.has(id)) starts.delete(id);
  }

  // Build the combined task list (API tasks + one entry per sending chat)
  const chatTasks: ActiveTask[] = Array.from(currentIds).map((chatId) => ({
    id: `__chat_sending_${chatId}__`,
    type: 'chat' as ActiveTask['type'],
    label: names.get(chatId) || 'Chat',
    detail: 'Processing...',
    status: 'sending',
    created_at: starts.get(chatId) || new Date().toISOString(),
    chatId,
  }));
  const allTasks: ActiveTask[] = [...chatTasks, ...tasks];

  const count = allTasks.length + completedChats.length;

  // Show/hide with slight delay to avoid flicker
  useEffect(() => {
    if (count > 0) {
      setVisible(true);
    } else {
      const t = setTimeout(() => setVisible(false), 600);
      return () => clearTimeout(t);
    }
  }, [count]);

  const dismissCompleted = useCallback((chatId: string) => {
    setCompletedChats(prev => prev.filter(c => c.chatId !== chatId));
  }, []);

  // Auto-dismiss completed entry if user is already viewing that chat
  useEffect(() => {
    if (activeChatId && completedChats.some(c => c.chatId === activeChatId)) {
      dismissCompleted(activeChatId);
    }
  }, [activeChatId, completedChats, dismissCompleted]);

  if (!visible && count === 0) return null;

  return (
    <div
      className={`fixed bottom-14 right-6 z-40 transition-all duration-300 ease-out ${
        count > 0 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'
      }`}
      style={{ maxWidth: 340, width: '100%' }}
    >
      <div className="bg-white rounded-xl shadow-lg shadow-stone-200/60 border border-stone-200 overflow-hidden">
        {/* Header — always visible */}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-2 px-3.5 py-2.5 hover:bg-stone-50 transition-colors text-left"
        >
          <div className="w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
            {allTasks.length > 0 ? (
              <CircleNotch size={13} className="animate-spin text-amber-600" weight="bold" />
            ) : (
              <CheckCircle size={13} className="text-green-600" weight="fill" />
            )}
          </div>
          <span className="text-[13px] font-semibold text-stone-700 flex-1">
            Active Tasks
          </span>
          <span className="text-[11px] font-semibold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
            {count}
          </span>
          <span className="text-stone-400 ml-0.5">
            {expanded ? <CaretUp size={13} /> : <CaretDown size={13} />}
          </span>
        </button>

        {/* Expanded task list */}
        <div
          className={`overflow-hidden transition-all duration-200 ease-out ${
            expanded ? 'max-h-[400px] opacity-100' : 'max-h-0 opacity-0'
          }`}
        >
          <div className="px-2.5 pb-2.5 space-y-1.5 max-h-[350px] overflow-y-auto">
            {/* Active tasks */}
            {allTasks.map((task) => (
              <TaskRow key={task.id} task={task} />
            ))}
            {/* Completed chats with "Open" button */}
            {completedChats.map((chat) => (
              <CompletedRow
                key={chat.chatId}
                chat={chat}
                onOpen={() => {
                  onOpenChat?.(chat.chatId);
                  dismissCompleted(chat.chatId);
                }}
                onDismiss={() => dismissCompleted(chat.chatId)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
