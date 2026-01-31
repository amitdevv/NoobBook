/**
 * Auth API Service + Token Storage
 *
 * Educational Note: This module handles all authentication-related API calls
 * and manages JWT tokens in localStorage. Tokens are stored client-side so
 * they persist across page refreshes and browser sessions.
 *
 * Token Flow:
 * 1. User logs in → backend returns access_token + refresh_token
 * 2. Tokens stored in localStorage
 * 3. Every API request includes access_token via interceptor (client.ts)
 * 4. When access_token expires, refresh_token is used to get a new one
 */

import { api } from './client';

// ==================== Token Storage ====================

const TOKEN_KEY = 'noobbook_access_token';
const REFRESH_TOKEN_KEY = 'noobbook_refresh_token';

export const tokenStorage = {
  getAccessToken: (): string | null => localStorage.getItem(TOKEN_KEY),
  getRefreshToken: (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY),

  setTokens: (accessToken: string, refreshToken: string) => {
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },

  clearTokens: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

// ==================== Auth Types ====================

interface AuthUser {
  id: string;
  email: string;
}

interface AuthResponse {
  success: boolean;
  user?: AuthUser;
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  requires_confirmation?: boolean;
  error?: string;
  message?: string;
}

// ==================== Auth API ====================

export const authAPI = {
  signup: (email: string, password: string, signupKey: string) =>
    api.post<AuthResponse>('/auth/signup', {
      email,
      password,
      signup_key: signupKey,
    }),

  login: (email: string, password: string) =>
    api.post<AuthResponse>('/auth/login', { email, password }),

  logout: () => api.post('/auth/logout'),

  getMe: () => api.get<{ success: boolean; user: AuthUser }>('/auth/me'),

  refresh: (refreshToken: string) =>
    api.post<AuthResponse>('/auth/refresh', { refresh_token: refreshToken }),
};
