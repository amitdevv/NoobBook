import { useCallback, useEffect, useState } from 'react';

/**
 * localStorage-backed dev/admin feature flag.
 *
 * Used for opt-in debugging UIs that should NOT ship to regular users.
 * Reads sync from localStorage on mount and re-syncs when any other tab
 * mutates the same key (the 'storage' event only fires cross-tab, so
 * setValue also notifies same-tab listeners via a CustomEvent).
 *
 * Keys are namespaced with `noobbook:dev:` so they're easy to grep and
 * never collide with non-dev preferences.
 */
const PREFIX = 'noobbook:dev:';
const SAME_TAB_EVENT = 'noobbook:dev-flag-change';

function readFlag(key: string): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(PREFIX + key) === '1';
  } catch {
    return false;
  }
}

export function useDevFlag(key: string): [boolean, (next: boolean) => void] {
  const [value, setValueState] = useState<boolean>(() => readFlag(key));

  useEffect(() => {
    const fullKey = PREFIX + key;
    const onStorage = (ev: StorageEvent) => {
      if (ev.key === fullKey) setValueState(ev.newValue === '1');
    };
    const onSameTab = (ev: Event) => {
      const detail = (ev as CustomEvent<{ key: string; value: boolean }>).detail;
      if (detail?.key === key) setValueState(detail.value);
    };
    window.addEventListener('storage', onStorage);
    window.addEventListener(SAME_TAB_EVENT, onSameTab as EventListener);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener(SAME_TAB_EVENT, onSameTab as EventListener);
    };
  }, [key]);

  const setValue = useCallback(
    (next: boolean) => {
      try {
        window.localStorage.setItem(PREFIX + key, next ? '1' : '0');
      } catch {
        // localStorage can throw in privacy modes — ignore, the
        // setting just won't persist across reloads in that session.
      }
      window.dispatchEvent(
        new CustomEvent(SAME_TAB_EVENT, { detail: { key, value: next } }),
      );
      setValueState(next);
    },
    [key],
  );

  return [value, setValue];
}
