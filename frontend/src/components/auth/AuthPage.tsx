/**
 * AuthPage — sign in / sign up.
 *
 * Built on the shadcn `login-03` Card pattern (`npx shadcn add login-03`)
 * but folded into NoobBook's existing voice rather than rendered with the
 * generated component. The design metaphor is the inside front cover of
 * a notebook: warm cream wash, serif-italic title, mono small-caps
 * subtitle, a white card hosting the form, generous negative space.
 *
 * The shadcn template's Apple/Google OAuth buttons are dropped — the
 * NoobBook backend (`backend/app/api/auth/routes.py:41-77`) only accepts
 * email/password, and surfacing OAuth where no real flow exists would be
 * confusing. The "Forgot password" link is dropped for the same reason
 * (admins reset passwords from the Team table). The terms-of-service
 * footer is dropped — no such page exists.
 *
 * Functional behaviour (auth, share-link redirect, password show/hide,
 * toast errors) matches the previous AuthPage version one-for-one.
 */
import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../ui/card';
import { useToast } from '../ui/use-toast';
import { ToastContainer } from '../ui/toast';
import { authAPI } from '@/lib/api/auth';
import { createLogger } from '@/lib/logger';
import {
  CircleNotch,
  Eye,
  EyeSlash,
  Ghost,
} from '@phosphor-icons/react';

const log = createLogger('auth-page');

interface AuthPageProps {
  onAuthenticated: () => Promise<void> | void;
}

export const AuthPage: React.FC<AuthPageProps> = ({ onAuthenticated }) => {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const { toasts, dismissToast, success, error } = useToast();

  /**
   * Pull a same-origin redirect target out of the URL.
   *
   * Share links bounce logged-out viewers here as `/auth?redirect=/share/...`
   * — without this, sign-in lands them on the dashboard (which then shows
   * "no projects" for brand-new accounts created via the share flow).
   *
   * Only relative paths are honoured to avoid open-redirect abuse.
   */
  const getRedirectTarget = (): string | null => {
    if (typeof window === 'undefined') return null;
    const params = new URLSearchParams(window.location.search);
    const raw = params.get('redirect');
    if (!raw) return null;
    if (!raw.startsWith('/') || raw.startsWith('//')) return null;
    return raw;
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!email || !password) {
      error('Email and password are required');
      return;
    }

    setSubmitting(true);
    try {
      const result =
        mode === 'signin'
          ? await authAPI.signIn(email, password)
          : await authAPI.signUp(email, password);

      if (!result.success) {
        error(result.error || 'Authentication failed');
        return;
      }

      success(mode === 'signin' ? 'Signed in' : 'Account created');

      // If the user came from a share link, send them back to it.
      // Use a full navigation so the share viewer remounts with the
      // freshly-issued JWT (avoids stale `is_authenticated=false` state).
      const redirect = getRedirectTarget();
      if (redirect) {
        window.location.assign(redirect);
        return;
      }

      await onAuthenticated();
    } catch (err) {
      log.error({ err }, 'authentication failed');
      error('Authentication failed');
    } finally {
      setSubmitting(false);
    }
  };

  const submitLabel = submitting
    ? mode === 'signin'
      ? 'Signing in…'
      : 'Creating account…'
    : mode === 'signin'
      ? 'Continue'
      : 'Create account';

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center px-6 py-10 relative overflow-hidden">
      {/* Atmosphere — warm radial wash from the top-right corner, same
          vocabulary as DocumentEditorDialog. Establishes "this is the
          NoobBook surface" before the user reads a single word. */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_right,rgba(254,243,199,0.55),transparent_55%)]"
      />
      {/* Faint diagonal hairline — paper-stationery cue, sub-perceptual
          but adds depth. Stops the cream from looking like flat CSS. */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none opacity-[0.025]"
        style={{
          backgroundImage:
            'repeating-linear-gradient(135deg, rgba(120, 53, 15, 0.4) 0px, rgba(120, 53, 15, 0.4) 1px, transparent 1px, transparent 8px)',
        }}
      />

      <div className="relative w-full max-w-[400px] auth-fade-in">
        {/* Brand header — sits OUTSIDE the card so the identity moment is
            distinct from the form moment. Ghost icon nods to the favicon
            convention; serif italic title matches the
            DocumentEditorDialog "Untitled note" treatment. */}
        <header className="mb-7 flex flex-col items-center text-center select-none">
          <Ghost
            size={28}
            weight="duotone"
            className="text-amber-600 mb-3"
          />
          <h1 className="font-serif italic text-[42px] leading-none text-stone-900 tracking-tight">
            NoobBook
          </h1>
          <div className="mt-3 h-px w-10 bg-amber-600/80" />
        </header>

        <Card className="border-amber-100/70 shadow-[0_2px_24px_-8px_rgba(120,53,15,0.12)] bg-white/95 backdrop-blur-sm">
          <CardHeader className="pb-2 pt-6 text-center">
            <CardTitle className="font-mono text-[10px] uppercase tracking-[0.22em] text-stone-400 font-normal">
              {mode === 'signin' ? 'Sign in' : 'Create account'}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-7 pb-7 pt-2">
            <form onSubmit={handleSubmit} className="grid gap-5" noValidate>
              <div className="grid gap-2">
                <label
                  htmlFor="auth-email"
                  className="text-[12px] font-medium text-stone-700"
                >
                  Email
                </label>
                <input
                  id="auth-email"
                  type="email"
                  autoComplete="email"
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={submitting}
                  placeholder="you@example.com"
                  className="h-10 w-full rounded-md border border-stone-200 bg-stone-50/40 px-3 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-200/60 focus:bg-white transition-colors disabled:opacity-60"
                />
              </div>

              <div className="grid gap-2">
                <label
                  htmlFor="auth-password"
                  className="text-[12px] font-medium text-stone-700"
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    id="auth-password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete={
                      mode === 'signin' ? 'current-password' : 'new-password'
                    }
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={submitting}
                    placeholder={mode === 'signin' ? '••••••••' : 'Choose a password'}
                    className="h-10 w-full rounded-md border border-stone-200 bg-stone-50/40 px-3 pr-10 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-200/60 focus:bg-white transition-colors disabled:opacity-60"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full mt-1 inline-flex items-center justify-center gap-2 h-11 rounded-md bg-amber-600 text-white text-sm font-medium tracking-wide shadow-[0_1px_0_rgba(0,0,0,0.06),0_2px_8px_-2px_rgba(217,119,6,0.4)] hover:bg-amber-700 hover:shadow-[0_1px_0_rgba(0,0,0,0.06),0_4px_12px_-2px_rgba(217,119,6,0.5)] active:bg-amber-700 active:shadow-[0_1px_0_rgba(0,0,0,0.06)] disabled:opacity-60 disabled:cursor-not-allowed transition-all"
              >
                {submitting && (
                  <CircleNotch size={14} className="animate-spin" />
                )}
                {submitLabel}
              </button>
            </form>
          </CardContent>
        </Card>

        {/* Mode toggle — text link, amber underline as a continuation of
            the rule under the brand title. Sits below the card so it
            reads as supporting metadata rather than a primary action. */}
        <p className="mt-6 text-center text-sm text-stone-500">
          {mode === 'signin' ? 'New here? ' : 'Already have an account? '}
          <button
            type="button"
            onClick={() => {
              setMode((m) => (m === 'signin' ? 'signup' : 'signin'));
              setShowPassword(false);
            }}
            disabled={submitting}
            className="text-stone-900 underline underline-offset-4 decoration-amber-600 decoration-2 hover:decoration-stone-900 transition-colors disabled:opacity-60"
          >
            {mode === 'signin' ? 'Create an account' : 'Sign in instead'}
          </button>
        </p>

        {/* Admin-emails footer — replaces login-03's terms-of-service
            footer. NoobBook's role assignment is deterministic from
            an env var; surfacing the var name makes the convention
            discoverable for the operator who set it up. */}
        <p className="mt-12 text-center text-[11px] text-stone-400 leading-relaxed max-w-[340px] mx-auto">
          Administrator privileges are granted automatically to emails
          listed in{' '}
          <code className="font-mono text-stone-500 bg-stone-100 px-1 py-0.5 rounded">
            NOOBBOOK_ADMIN_EMAILS
          </code>
          .
        </p>
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      <style>{`
        @keyframes auth-fade-in {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .auth-fade-in {
          animation: auth-fade-in 360ms cubic-bezier(0.2, 0.65, 0.3, 1) both;
        }
      `}</style>
    </div>
  );
};
