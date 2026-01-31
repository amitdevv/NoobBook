/**
 * Auth Context & Hook
 *
 * Educational Note: React Context provides a way to pass data through the
 * component tree without prop drilling. The AuthProvider wraps the entire app
 * and makes auth state (user, loading, login/signup/logout functions) available
 * to any component via the useAuth() hook.
 *
 * Auth Flow:
 * 1. On mount, check for existing tokens in localStorage
 * 2. If token exists, validate by calling GET /auth/me
 * 3. If valid → set user. If expired → try refresh. If refresh fails → clear tokens.
 * 4. Login/signup store new tokens and set user state
 * 5. Logout clears tokens and resets user state
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authAPI, tokenStorage } from '@/lib/api/auth';

// ==================== Types ====================

interface AuthUser {
  id: string;
  email: string;
}

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signup: (email: string, password: string, signupKey: string) => Promise<{ success: boolean; error?: string; requiresConfirmation?: boolean }>;
  logout: () => Promise<void>;
}

// ==================== Context ====================

const AuthContext = createContext<AuthContextType | null>(null);

// ==================== Provider ====================

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Check existing session on mount
  useEffect(() => {
    const checkSession = async () => {
      const token = tokenStorage.getAccessToken();
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const response = await authAPI.getMe();
        if (response.data.success && response.data.user) {
          setUser(response.data.user);
        } else {
          tokenStorage.clearTokens();
        }
      } catch {
        // Token might be expired — try refresh
        const refreshToken = tokenStorage.getRefreshToken();
        if (refreshToken) {
          try {
            const refreshResponse = await authAPI.refresh(refreshToken);
            const data = refreshResponse.data;
            if (data.success && data.access_token && data.refresh_token) {
              tokenStorage.setTokens(data.access_token, data.refresh_token);
              // Retry getting user
              const meResponse = await authAPI.getMe();
              if (meResponse.data.success && meResponse.data.user) {
                setUser(meResponse.data.user);
              } else {
                tokenStorage.clearTokens();
              }
            } else {
              tokenStorage.clearTokens();
            }
          } catch {
            tokenStorage.clearTokens();
          }
        } else {
          tokenStorage.clearTokens();
        }
      } finally {
        setLoading(false);
      }
    };

    checkSession();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    try {
      const response = await authAPI.login(email, password);
      const data = response.data;

      if (data.success && data.access_token && data.refresh_token && data.user) {
        tokenStorage.setTokens(data.access_token, data.refresh_token);
        setUser(data.user);
        return { success: true };
      }

      return { success: false, error: data.error || 'Login failed' };
    } catch (err: any) {
      const message = err.response?.data?.error || 'Login failed. Please try again.';
      return { success: false, error: message };
    }
  }, []);

  const signup = useCallback(async (email: string, password: string, signupKey: string) => {
    try {
      const response = await authAPI.signup(email, password, signupKey);
      const data = response.data;

      if (data.requires_confirmation) {
        return { success: true, requiresConfirmation: true };
      }

      if (data.success && data.access_token && data.refresh_token && data.user) {
        tokenStorage.setTokens(data.access_token, data.refresh_token);
        setUser(data.user);
        return { success: true };
      }

      return { success: false, error: data.error || 'Signup failed' };
    } catch (err: any) {
      const message = err.response?.data?.error || 'Signup failed. Please try again.';
      return { success: false, error: message };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authAPI.logout();
    } catch {
      // Proceed with local logout even if server call fails
    }
    tokenStorage.clearTokens();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ==================== Hook ====================

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
