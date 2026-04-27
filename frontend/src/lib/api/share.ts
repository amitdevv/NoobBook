/**
 * Shared Project — viewer-side API client (Roadmap #15).
 *
 * Hits `/api/v1/share/{token}/...` which is the only URL space the
 * backend exposes without a JWT. Public-mode shares work for
 * anonymous viewers; invited-mode shares attach the viewer's JWT
 * (via `api`'s default Authorization header) so the backend can match
 * email against the invite list.
 *
 * Returned types are intentionally minimal — we mirror the shapes the
 * existing chat components already consume so they can be reused with
 * a single `readOnly` flag.
 */
import { api } from './client';
import type { Chat, ChatMetadata } from './chats';

export interface ShareViewer {
  is_authenticated: boolean;
  user_id: string | null;
  email: string | null;
}

export interface ShareRoot {
  share: {
    project_id: string;
    mode: 'public' | 'invited';
    url: string;
  };
  project: {
    id: string;
    name: string;
    description: string;
  };
  chats: ChatMetadata[];
  viewer: ShareViewer;
}

export interface SharedCitationChunk {
  content: string;
  chunk_id: string;
  source_id: string;
  source_name: string;
  page_number: number;
  chunk_index: number;
}

/**
 * Returned by `POST /share/{token}/chats/{chat_id}/fork`. The fork now
 * clones the entire project (sources + chunks + chats + Pinecone vectors),
 * so `project` is always present. `chat` is the cloned counterpart of the
 * chat the viewer was reading — null in the unlikely case it didn't survive
 * the clone, in which case the UI should fall back to `/projects/{id}`.
 */
export interface ForkResult {
  project: { id: string; name: string };
  chat: {
    id: string;
    project_id: string;
  } | null;
  stats?: {
    source_count: number;
    chat_count: number;
  };
}

export const shareAPI = {
  getRoot: (token: string) =>
    api.get<{ success: boolean } & ShareRoot>(`/share/${token}`),

  getChat: (token: string, chatId: string) =>
    api.get<{ success: boolean; chat: Chat }>(
      `/share/${token}/chats/${chatId}`,
    ),

  getCitation: (token: string, chatId: string, chunkId: string) =>
    api.get<{ success: boolean; chunk: SharedCitationChunk }>(
      `/share/${token}/chats/${chatId}/citations/${encodeURIComponent(chunkId)}`,
    ),

  /**
   * Build the URL the frontend should set on `<img>` / `<audio>` /
   * `<video>` etc. for studio output thumbnails inside the share view.
   * The browser fetches it directly (no auth header needed because the
   * route is whitelisted in the global JWT gate and the token is in the
   * path).
   */
  studioAssetUrl: (
    token: string,
    kind: string,
    jobId: string,
    filename: string,
  ): string =>
    `/api/v1/share/${token}/studio/${encodeURIComponent(kind)}/${encodeURIComponent(jobId)}/${filename
      .split('/')
      .map(encodeURIComponent)
      .join('/')}`,

  fork: (token: string, chatId: string) =>
    api.post<{ success: boolean } & ForkResult>(
      `/share/${token}/chats/${chatId}/fork`,
      {},
    ),
};
