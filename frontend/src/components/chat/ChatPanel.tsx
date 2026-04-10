/**
 * ChatPanel Component
 * Educational Note: Main orchestrator for the chat interface.
 * Composes smaller components (ChatHeader, ChatMessages, ChatInput, etc.)
 * and manages chat state and API interactions.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Sparkle } from '@phosphor-icons/react';
import { Skeleton } from '../ui/skeleton';
import { chatsAPI } from '@/lib/api/chats';
import type { Chat, ChatMetadata, StudioSignal } from '@/lib/api/chats';
import { sourcesAPI, type Source } from '@/lib/api/sources';
import { ToastContainer } from '../ui/toast';
import { useToast } from '../ui/use-toast';
import { useVoiceRecording } from '../hooks/useVoiceRecording';
import { ChatHeader } from './ChatHeader';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { ChatList } from './ChatList';
import { ChatEmptyState } from './ChatEmptyState';
import { RawMessageView } from './RawMessageView';
import { exportChatAsPdf } from '@/lib/exportChatPdf';
import { createLogger } from '@/lib/logger';

const log = createLogger('chat-panel');

interface ChatPanelProps {
  projectId: string;
  projectName: string;
  sourcesVersion?: number;
  onCostsChange?: () => void; // Called after message sent to trigger cost refresh
  onSignalsChange?: (signals: StudioSignal[]) => void; // Called when studio signals change
  selectedSourceIds: string[]; // Per-chat source selection from parent
  onActiveChatChange: (chatId: string | null, selectedSourceIds: string[]) => void; // Notify parent of chat change
  sendingChatIds: Set<string>; // All chats currently processing (owned by parent)
  onAddSendingChat: (chatId: string, chatName?: string) => void;
  onRemoveSendingChat: (chatId: string) => void;
  openChatId?: string | null; // When set, ChatPanel switches to this chat
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  projectId,
  projectName,
  sourcesVersion,
  onCostsChange,
  onSignalsChange,
  selectedSourceIds,
  onActiveChatChange,
  sendingChatIds,
  onAddSendingChat,
  onRemoveSendingChat,
  openChatId,
}) => {
  const { toasts, dismissToast, success, error } = useToast();

  // Chat state
  const [message, setMessage] = useState('');
  const [activeChat, setActiveChat] = useState<Chat | null>(null);
  const [showChatList, setShowChatList] = useState(false);
  const [allChats, setAllChats] = useState<ChatMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  // Derive sending state for current chat from parent-owned Set
  const sending = activeChat ? sendingChatIds.has(activeChat.id) : false;
  const [exportingChat, setExportingChat] = useState(false);
  const [rawMode, setRawMode] = useState(false);
  const [streamingAssistantContent, setStreamingAssistantContent] = useState('');
  // AbortController for cancelling in-flight chat requests
  const abortControllerRef = useRef<AbortController | null>(null);
  const canonicalUserMessageReceivedRef = useRef(false);
  const assistantDeltaReceivedRef = useRef(false);

  // Sources state for header display
  const [sources, setSources] = useState<Source[]>([]);

  // Active sources count derived from per-chat selection
  const activeSources = selectedSourceIds.length;

  // Voice recording hook
  const {
    isRecording,
    partialTranscript,
    transcriptionConfigured,
    startRecording,
    stopRecording,
  } = useVoiceRecording({
    onError: error,
    onTranscriptCommit: useCallback((text: string) => {
      // Append committed text to message
      setMessage((prev) => {
        if (prev && !prev.endsWith(' ')) {
          return prev + ' ' + text;
        }
        return prev + text;
      });
    }, []),
  });

  /**
   * Load sources for the project (for header display)
   */
  const loadSources = async () => {
    try {
      const data = await sourcesAPI.listSources(projectId);
      setSources(data);
    } catch (err) {
      log.error({ err }, 'failed to Lloading sourcesE');
    }
  };

  /**
   * Load full chat data including all messages
   */
  const loadFullChat = async (chatId: string) => {
    try {
      const chat = await chatsAPI.getChat(projectId, chatId);
      setActiveChat(chat);
      // Notify parent of per-chat source selection
      onActiveChatChange(chat.id, chat.selected_source_ids ?? []);
    } catch (err) {
      log.error({ err }, 'failed to load chat');
      error('Failed to load chat');
    }
  };

  /**
   * Load all chats for the project
   */
  const loadChats = async () => {
    try {
      setLoading(true);
      const chats = await chatsAPI.listChats(projectId);
      setAllChats(chats);

      // If we have chats and no active chat, load the first one
      if (chats.length > 0 && !activeChat) {
        await loadFullChat(chats[0].id);
      }
    } catch (err) {
      log.error({ err }, 'failed to Lloading chatsE');
      error('Failed to load chats');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Load all chats and sources when component mounts or projectId changes
   */
  useEffect(() => {
    loadChats();
    loadSources();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // Switch to a specific chat when parent requests it (e.g. from ActiveTasksBar "Open" button)
  useEffect(() => {
    if (openChatId && openChatId !== activeChat?.id) {
      loadFullChat(openChatId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openChatId]);

  /**
   * Refetch sources when sourcesVersion changes
   * Educational Note: This triggers when SourcesPanel notifies us that sources
   * have changed (toggle active, delete, processing complete, etc.)
   */
  useEffect(() => {
    if (sourcesVersion !== undefined && sourcesVersion > 0) {
      loadSources();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourcesVersion]);

  /**
   * Notify parent when studio signals change
   * Educational Note: Signals are stored in the chat and loaded/updated
   * when chat is loaded or after messages are sent.
   */
  useEffect(() => {
    if (activeChat) {
      onSignalsChange?.(activeChat.studio_signals || []);
    } else {
      onSignalsChange?.([]);
    }
  }, [activeChat, onSignalsChange]);

  /**
   * Send a message and get AI response
   * Educational Note: We add the user message optimistically to the UI
   * before the API call, so users see their message immediately.
   */
  const handleSend = async () => {
    if (!message.trim() || !activeChat || sending) return;

    const userMessage = message.trim();
    const currentChat = activeChat;
    const sendingChatId = currentChat.id;
    const controller = new AbortController();
    abortControllerRef.current = controller;
    canonicalUserMessageReceivedRef.current = false;
    assistantDeltaReceivedRef.current = false;
    setMessage('');
    setRawMode(false);
    setStreamingAssistantContent('');
    onAddSendingChat(sendingChatId, activeChat.title);

    // Optimistically add user message to UI immediately
    const tempUserMessage = {
      id: `temp-${Date.now()}`,
      role: 'user' as const,
      content: userMessage,
      timestamp: new Date().toISOString(),
    };

    setActiveChat((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        messages: [...prev.messages, tempUserMessage],
      };
    });

    const scheduleChatRefreshes = async (chatId: string) => {
      await loadChats();
      onCostsChange?.();

      setTimeout(async () => {
        try {
          const updatedChat = await chatsAPI.getChat(projectId, chatId);
          setActiveChat(prev => prev && prev.id === chatId
            ? { ...prev, studio_signals: updatedChat.studio_signals || [] }
            : prev
          );
        } catch {
          // Silently ignore - signal update is non-critical
        }
      }, 1000);

      setTimeout(async () => {
        try {
          const updatedChat = await chatsAPI.getChat(projectId, chatId);
          setActiveChat(prev => prev && prev.id === chatId
            ? { ...prev, title: updatedChat.title, studio_signals: updatedChat.studio_signals || [] }
            : prev
          );
          setAllChats(prev => prev.map(c =>
            c.id === chatId ? { ...c, title: updatedChat.title } : c
          ));
        } catch {
          // Silently ignore - title update is non-critical
        }
      }, 4000);
    };

    const replaceTempWithCanonicalUser = (canonicalUserMessage: Chat['messages'][number]) => {
      canonicalUserMessageReceivedRef.current = true;
      setActiveChat((prev) => {
        if (!prev) return null;
        const nextMessages = prev.messages.map((msg) =>
          msg.id === tempUserMessage.id ? canonicalUserMessage : msg
        );
        const alreadyPresent = nextMessages.some((msg) => msg.id === canonicalUserMessage.id);
        return {
          ...prev,
          messages: alreadyPresent ? nextMessages : [...nextMessages.filter((msg) => msg.id !== tempUserMessage.id), canonicalUserMessage],
        };
      });
    };

    const appendAssistantMessage = (assistantMessage: Chat['messages'][number]) => {
      // Append the final message first, THEN clear streaming content in the
      // same React batch. This prevents a flash where neither the streaming
      // bubble nor the final message is visible.
      setActiveChat((prev) => {
        if (!prev) return null;
        const messagesWithoutTemp = prev.messages.filter((m) => m.id !== tempUserMessage.id);
        if (messagesWithoutTemp.some((msg) => msg.id === assistantMessage.id)) {
          return { ...prev, messages: messagesWithoutTemp, updated_at: new Date().toISOString() };
        }
        return {
          ...prev,
          messages: [...messagesWithoutTemp, assistantMessage],
          updated_at: new Date().toISOString(),
        };
      });
      setStreamingAssistantContent('');
    };

    const applyFallbackResponse = (result: { user_message: Chat['messages'][number]; assistant_message: Chat['messages'][number] }) => {
      canonicalUserMessageReceivedRef.current = true;
      setStreamingAssistantContent('');
      setActiveChat((prev) => {
        if (!prev) return null;
        const messagesWithoutTemp = prev.messages.filter((m) => m.id !== tempUserMessage.id);
        return {
          ...prev,
          messages: [...messagesWithoutTemp, result.user_message, result.assistant_message],
          updated_at: new Date().toISOString(),
        };
      });
    };

    try {
      const streamResult = await chatsAPI.streamMessage(
        projectId,
        currentChat.id,
        userMessage,
        {
          onUserMessage: replaceTempWithCanonicalUser,
          onAssistantDelta: (delta) => {
            assistantDeltaReceivedRef.current = true;
            setStreamingAssistantContent((prev) => prev + delta);
          },
          onAssistantDone: appendAssistantMessage,
          onErrorEvent: (payload) => {
            setStreamingAssistantContent('');
            if (payload.assistant_message) {
              appendAssistantMessage(payload.assistant_message);
            }
          },
        },
        controller.signal
      );

      if (streamResult.terminalEvent) {
        await scheduleChatRefreshes(currentChat.id);
      }
    } catch (err) {
      // Don't show error toast if user intentionally stopped
      const isAborted = err instanceof Error && (err.name === 'CanceledError' || err.name === 'AbortError');
      if (isAborted) {
        log.info('Chat request stopped by user');
      } else {
        const shouldFallback = !canonicalUserMessageReceivedRef.current && !assistantDeltaReceivedRef.current;

        if (shouldFallback) {
          try {
            const fallbackResult = await chatsAPI.sendMessage(projectId, currentChat.id, userMessage);
            applyFallbackResponse(fallbackResult);
            await scheduleChatRefreshes(currentChat.id);
          } catch (fallbackError) {
            log.error({ err: fallbackError }, 'failed to send message via fallback');
            error('Failed to send message');
          }
        } else {
          log.error({ err }, 'failed to send message');
          error('Failed to send message');
        }
      }
      setStreamingAssistantContent('');
      if (!canonicalUserMessageReceivedRef.current) {
        setActiveChat((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            messages: prev.messages.filter((m) => m.id !== tempUserMessage.id),
          };
        });
      }
    } finally {
      onRemoveSendingChat(sendingChatId);
      abortControllerRef.current = null;
    }
  };

  /**
   * Stop the current in-flight chat request
   */
  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStreamingAssistantContent('');
  };

  /**
   * Create a new chat
   */
  const handleNewChat = async () => {
    try {
      const newChat = await chatsAPI.createChat(projectId, 'New Chat');
      await loadChats();
      await loadFullChat(newChat.id);
      // New chats start with no sources selected (loadFullChat will call onActiveChatChange)
      setShowChatList(false);
      success('New chat created');
    } catch (err) {
      log.error({ err }, 'failed to Lcreating chatE');
      error('Failed to create chat');
    }
  };

  /**
   * Select a chat from the list
   */
  const handleSelectChat = async (chatId: string) => {
    await loadFullChat(chatId);
    setShowChatList(false);
  };

  /**
   * Delete a chat
   */
  const handleDeleteChat = async (chatId: string) => {
    try {
      await chatsAPI.deleteChat(projectId, chatId);

      // If the deleted chat was active, clear it and reset source selection
      if (activeChat?.id === chatId) {
        setActiveChat(null);
        onActiveChatChange(null, []);
      }

      await loadChats();
      success('Chat deleted');
    } catch (err) {
      log.error({ err }, 'failed to Ldeleting chatE');
      error('Failed to delete chat');
    }
  };

  /**
   * Rename a chat
   */
  const handleRenameChat = async (chatId: string, newTitle: string) => {
    try {
      await chatsAPI.updateChat(projectId, chatId, newTitle);
      await loadChats();

      // Update active chat if it was renamed
      if (activeChat?.id === chatId) {
        setActiveChat(prev => prev ? { ...prev, title: newTitle } : null);
      }

      success('Chat renamed');
    } catch (err) {
      log.error({ err }, 'failed to Lrenaming chatE');
      error('Failed to rename chat');
    }
  };

  /**
   * Toggle recording on/off
   */
  const handleMicClick = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  /**
   * Export the active chat as a PDF file
   */
  const handleExportChat = useCallback(async () => {
    if (!activeChat) return;
    setExportingChat(true);
    try {
      await exportChatAsPdf({ chat: activeChat, projectId, projectName });
      success('Chat exported as PDF');
    } catch (err) {
      log.error({ err }, 'Failed to export chat as PDF');
      error('Failed to export chat');
    } finally {
      setExportingChat(false);
    }
  }, [activeChat, projectId, projectName, success, error]);

  // Loading state
  if (loading) {
    return (
      <div className="flex flex-col h-full bg-card">
        <div className="border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <Sparkle size={20} className="text-primary" />
            <h2 className="font-semibold">Chat</h2>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Ask questions about your sources or request analysis
          </p>
        </div>
        <div className="flex-1 p-6 space-y-4">
          {/* Skeleton message bubbles mimicking a chat conversation */}
          <div className="flex justify-end">
            <Skeleton className="h-10 w-2/3 rounded-2xl" />
          </div>
          <div className="flex justify-start gap-3">
            <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
            <div className="space-y-2 flex-1">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          </div>
          <div className="flex justify-end">
            <Skeleton className="h-8 w-1/2 rounded-2xl" />
          </div>
          <div className="flex justify-start gap-3">
            <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
            <div className="space-y-2 flex-1">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-4/5" />
            </div>
          </div>
        </div>
        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </div>
    );
  }

  // Empty state - no chats exist
  if (allChats.length === 0 && !activeChat) {
    return (
      <>
        <ChatEmptyState projectName={projectName} onNewChat={handleNewChat} />
        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </>
    );
  }

  // Chat list view
  if (showChatList) {
    return (
      <>
        <ChatList
          chats={allChats}
          onSelectChat={handleSelectChat}
          onDeleteChat={handleDeleteChat}
          onRenameChat={handleRenameChat}
          onNewChat={handleNewChat}
        />
        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </>
    );
  }

  // Active chat view
  return (
    <div className="flex flex-col h-full min-h-0 min-w-0 w-full bg-card overflow-hidden">
      <ChatHeader
        activeChat={activeChat}
        allChats={allChats}
        activeSources={activeSources}
        totalSources={sources.length}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onShowChatList={() => setShowChatList(true)}
        onExportChat={handleExportChat}
        exportingChat={exportingChat}
      />

      {rawMode && activeChat ? (
        <RawMessageView projectId={projectId} chatId={activeChat.id} />
      ) : (
        <ChatMessages
          messages={activeChat?.messages || []}
          sending={sending}
          projectId={projectId}
          streamingAssistantContent={streamingAssistantContent}
        />
      )}

      <ChatInput
        message={message}
        partialTranscript={partialTranscript}
        isRecording={isRecording}
        sending={sending}
        transcriptionConfigured={transcriptionConfigured}
        rawMode={rawMode}
        onMessageChange={setMessage}
        onSend={handleSend}
        onStop={handleStop}
        onMicClick={handleMicClick}
        onToggleRawMode={() => setRawMode((prev) => !prev)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
