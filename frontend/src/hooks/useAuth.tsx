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
 * 3. If valid → set user. If expired → clear tokens.
 * 4. Login/signup store new tokens and set user state
 * 5. Logout clears tokens and resets user state
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authAPI } from '@/lib/api/auth';
import { getAccessToken, clearSession } from '@/lib/auth/session';

// ==================== Types ====================

interface AuthUser {
  id: string;
  email: string | null;
}

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signup: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
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
      const token = getAccessToken();
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const response = await authAPI.me();
        if (response.success && response.user) {
          setUser({ id: response.user.id, email: response.user.email || null });
        } else {
          clearSession();
        }
      } catch {
        clearSession();
      } finally {
        setLoading(false);
      }
    };

    checkSession();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    try {
      const result = await authAPI.signIn(email, password);

      if (result.success && result.user) {
        setUser({ id: result.user.id, email: result.user.email || null });
        return { success: true };
      }

      return { success: false, error: result.error || 'Login failed' };
    } catch (err: any) {
      const message = err.response?.data?.error || 'Login failed. Please try again.';
      return { success: false, error: message };
    }
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    try {
      const result = await authAPI.signUp(email, password);

      if (result.success && result.user) {
        setUser({ id: result.user.id, email: result.user.email || null });
        return { success: true };
      }

      return { success: false, error: result.error || 'Signup failed' };
    } catch (err: any) {
      const message = err.response?.data?.error || 'Signup failed. Please try again.';
      return { success: false, error: message };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authAPI.signOut();
    } catch {
      // Proceed with local logout even if server call fails
    }
    clearSession();
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
