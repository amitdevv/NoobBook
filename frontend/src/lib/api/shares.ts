/**
 * Project Shares API — owner side (Roadmap #15).
 *
 * Owner-side client for managing share links on a project they own.
 * The viewer-side client lives in `share.ts` (no `s`) and uses a
 * separate URL space (`/api/v1/share/...`) that doesn't require a JWT.
 */
import { api } from './client';

export type ShareMode = 'public' | 'invited';

/**
 * `expires_in_days` accepts 7, 30, or null (never). The backend
 * validates the value; we type it loosely for forward compatibility.
 */
export type ShareExpiry = 7 | 30 | null;

export interface ProjectShare {
  id: string;
  project_id: string;
  token: string;
  url: string;
  mode: ShareMode;
  invited_emails: string[];
  created_by: string;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  is_active: boolean;
}

export interface CreateShareInput {
  mode: ShareMode;
  invited_emails?: string[];
  expires_in_days?: ShareExpiry;
}

export interface InvitableUser {
  id: string;
  email: string;
}

export const sharesAPI = {
  list: (projectId: string) =>
    api.get<{ success: boolean; shares: ProjectShare[] }>(
      `/projects/${projectId}/shares`,
    ),

  create: (projectId: string, input: CreateShareInput) =>
    api.post<{ success: boolean; share: ProjectShare }>(
      `/projects/${projectId}/shares`,
      input,
    ),

  revoke: (projectId: string, shareId: string) =>
    api.delete<{ success: boolean }>(
      `/projects/${projectId}/shares/${shareId}`,
    ),

  /**
   * Prefix-search for users to invite. Backend caps results at 25 and
   * excludes the requester. Empty `q` returns an empty list.
   */
  searchUsers: (projectId: string, q: string, limit = 8) =>
    api.get<{ success: boolean; users: InvitableUser[] }>(
      `/projects/${projectId}/shares/users-search`,
      { params: { q, limit } },
    ),
};
