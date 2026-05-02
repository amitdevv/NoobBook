/**
 * Tiny module-level mirror of the current user's admin status.
 *
 * Set once from App.tsx after auth resolves. Read by leaf-level helpers
 * (the toast renderer is the main consumer) so they can decide whether
 * to surface admin-only affordances without prop-drilling `isAdmin`
 * through every component tree.
 *
 * Trade-off acknowledged: this is module-level mutable state, which
 * normally we'd avoid. The alternative — threading isAdmin through
 * every error-toast call site — is worse. The flag is read-only from
 * the consumer's perspective and only flips on auth refresh, so it
 * doesn't introduce render-correctness issues.
 */
let adminMode = false;

export function setAdminMode(value: boolean): void {
  adminMode = value;
}

export function getAdminMode(): boolean {
  return adminMode;
}

/**
 * Window event names dispatched / listened-to globally. Centralized
 * here so producers and consumers can't drift on the string.
 */
export const LOGS_OPEN_EVENT = 'noobbook:open-logs';
export const SESSION_EXPIRED_EVENT = 'noobbook:session-expired';

export function openLogsModal(): void {
  window.dispatchEvent(new CustomEvent(LOGS_OPEN_EVENT));
}

export function notifySessionExpired(): void {
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
}
