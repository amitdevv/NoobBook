/**
 * Clipboard helper with a graceful fallback.
 *
 * `navigator.clipboard.writeText` is only available in secure contexts
 * (HTTPS or localhost) and requires the document to be focused. It throws
 * a NotAllowedError in many real-world cases:
 *   • the page is served over plain HTTP (e.g. a custom dev domain)
 *   • the call originates from an iframe or popup that lost focus
 *   • the browser is older than the Clipboard API
 *
 * When the modern API fails we fall back to the legacy
 * `document.execCommand('copy')` trick (write to a temp textarea, select,
 * copy, remove). It's deprecated but still universally supported and is
 * the standard escape hatch for this exact scenario.
 *
 * Returns `true` if either path succeeded, `false` otherwise — callers
 * decide how to surface the failure (toast, inline message, etc.).
 */
import { createLogger } from './logger';

const log = createLogger('clipboard');

export async function copyToClipboard(text: string): Promise<boolean> {
  if (typeof window === 'undefined') return false;

  // Modern path — only attempt when the API is actually exposed. Some
  // browsers omit `navigator.clipboard` entirely in insecure contexts
  // instead of throwing, so guard before the call.
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      log.warn({ err }, 'clipboard API failed; falling back to execCommand');
    }
  }

  // Legacy path — works in non-secure contexts where the modern API is
  // blocked. The textarea is positioned off-screen so the page doesn't
  // visibly flicker while the selection happens.
  try {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.top = '0';
    textarea.style.left = '0';
    textarea.style.opacity = '0';
    textarea.style.pointerEvents = 'none';
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, text.length);
    const ok = document.execCommand('copy');
    document.body.removeChild(textarea);
    return ok;
  } catch (err) {
    log.error({ err }, 'execCommand copy fallback failed');
    return false;
  }
}
