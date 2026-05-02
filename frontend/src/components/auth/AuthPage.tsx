/**
 * AuthPage — sign in / sign up.
 *
 * Editorial-minimal aesthetic, paired with the rest of the app's voice
 * (`DocumentEditorDialog`, the project header's serif italics). The
 * intent is for the auth surface to feel like the *first page of the
 * book* rather than a generic shadcn card — single column, generous
 * negative space, one warm radial wash, two inputs, one button. The
 * Admin/User portal toggle from the previous version was purely
 * cosmetic (the role is server-assigned from `NOOBBOOK_ADMIN_EMAILS`
 * regardless of which button you pressed) and has been removed.
 */
import React, { useState } from 'react';
import { useToast } from '../ui/use-toast';
import { ToastContainer } from '../ui/toast';
import { authAPI } from '@/lib/api/auth';
import { createLogger } from '@/lib/logger';
import { Eye, EyeSlash, CircleNotch } from '@phosphor-icons/react';

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
    <div className="min-h-screen bg-stone-50 flex items-center justify-center px-6 relative overflow-hidden">
      {/* Atmosphere — single warm radial wash, same vocabulary as
          DocumentEditorDialog. No grain overlay here; the page is meant
          to feel airy, not literary. */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_right,rgba(254,243,199,0.5),transparent_55%)]"
      />

      <div className="relative w-full max-w-[380px]">
        {/* Brand header — serif-italic display, thin amber rule, small-caps
            mono subtitle. Same type system as the project header and the
            document editor's "Untitled note" treatment. */}
        <header className="mb-10">
          <h1 className="font-serif italic text-[44px] leading-none text-stone-900 select-none">
            NoobBook
          </h1>
          <div className="mt-3 h-px w-10 bg-amber-600" />
          <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.22em] text-stone-400">
            {mode === 'signin' ? 'Sign in' : 'Create account'}
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          {/* Bottom-rule inputs — no boxes, no card. The page itself is
              the chrome. Focus state thickens the rule and darkens to
              stone-900 (matches the body text colour). */}
          <div>
            <label
              htmlFor="auth-email"
              className="block font-mono text-[10px] uppercase tracking-[0.18em] text-stone-400 mb-2"
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
              className="w-full bg-transparent border-0 border-b border-stone-300 px-0 py-2.5 text-base text-stone-900 placeholder:text-stone-300 focus:outline-none focus:border-stone-900 transition-colors"
            />
          </div>

          <div>
            <label
              htmlFor="auth-password"
              className="block font-mono text-[10px] uppercase tracking-[0.18em] text-stone-400 mb-2"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="auth-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                placeholder={mode === 'signin' ? '••••••••' : 'Choose a password'}
                className="w-full bg-transparent border-0 border-b border-stone-300 px-0 py-2.5 pr-9 text-base text-stone-900 placeholder:text-stone-300 focus:outline-none focus:border-stone-900 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                tabIndex={-1}
                className="absolute right-0 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700 transition-colors p-1"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Primary action — full-width, amber-600. The only "card-like"
              element on the page; everything else dissolves into the
              wash. */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full mt-2 inline-flex items-center justify-center gap-2 h-11 rounded-md bg-amber-600 text-white text-sm font-medium tracking-wide hover:bg-amber-700 active:bg-amber-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors shadow-[0_1px_0_rgba(0,0,0,0.08)]"
          >
            {submitting && <CircleNotch size={14} className="animate-spin" />}
            {submitLabel}
          </button>
        </form>

        {/* Mode switch — text link, not a tab. Amber underline reads as
            a continuation of the brand rule above the title. */}
        <p className="mt-6 text-sm text-stone-500">
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

        {/* Admin-emails footer — replaces the old Admin/User portal
            toggle. Admins use the same form; the role is granted
            server-side from NOOBBOOK_ADMIN_EMAILS, so there's nothing
            for the user to choose. Surfacing the env var name makes
            this discoverable for the operator who configured it. */}
        <p className="mt-14 text-[11px] text-stone-400 leading-relaxed">
          Administrator privileges are granted automatically to emails
          listed in{' '}
          <code className="font-mono text-stone-500 bg-stone-100 px-1 py-0.5 rounded">
            NOOBBOOK_ADMIN_EMAILS
          </code>
          .
        </p>
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
