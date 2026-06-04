/**
 * Hook whistleblower : détecte les comportements suspects côté navigateur
 * et les reporte au backend via POST /auth/security-event.
 *
 * Événements surveillés :
 *  - Ouverture des DevTools (heuristique redimensionnement + debugger)
 *  - Raccourcis clavier liés aux outils de débogage (F12, Ctrl+Shift+I/J/U)
 *  - Copie de contenu depuis des zones marquées comme sensibles
 *  - Clic droit sur des zones sensibles
 *  - Injection d'iframe externe dans le DOM
 *  - Pattern focus/blur anormal (indice d'overlay de phishing)
 */

import { useEffect, useRef } from 'react';
import { API_BASE } from '@/services/api';

type EventType =
  | 'DEVTOOLS_OPENED'
  | 'KEYBOARD_SHORTCUT_BLOCKED'
  | 'CLIPBOARD_EXFILTRATION'
  | 'RIGHT_CLICK_SENSITIVE'
  | 'IFRAME_INJECTION_ATTEMPT'
  | 'FOCUS_BLUR_PATTERN'
  | 'CONSOLE_TAMPERING';

const DEBOUNCE_MS = 3000;

async function reportEvent(type: EventType, detail: string): Promise<void> {
  try {
    const csrfMatch = document.cookie.match(/(?:^|; )secuapp_csrf=([^;]*)/);
    const csrf = csrfMatch ? decodeURIComponent(csrfMatch[1]) : '';
    await fetch(`${API_BASE}/auth/security-event`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrf,
        'X-Request-Timestamp': new Date().toISOString(),
      },
      body: JSON.stringify({
        event_type: type,
        detail: detail.slice(0, 512),
        client_ts: new Date().toISOString(),
      }),
    });
  } catch {
  }
}

export function useSecurityMonitor(): void {
  const lastReport = useRef<Map<EventType, number>>(new Map());

  function throttledReport(type: EventType, detail: string): void {
    const now = Date.now();
    const last = lastReport.current.get(type) ?? 0;
    if (now - last < DEBOUNCE_MS) return;
    lastReport.current.set(type, now);
    void reportEvent(type, detail);
  }

  useEffect(() => {
    const THRESHOLD = 160;
    let devtoolsOpen = false;
    const detectDevtools = (): void => {
      const widthDiff = window.outerWidth - window.innerWidth;
      const heightDiff = window.outerHeight - window.innerHeight;
      const isOpen = widthDiff > THRESHOLD || heightDiff > THRESHOLD;
      if (isOpen && !devtoolsOpen) {
        devtoolsOpen = true;
        throttledReport('DEVTOOLS_OPENED', `outerW=${window.outerWidth} innerW=${window.innerWidth}`);
      } else if (!isOpen) {
        devtoolsOpen = false;
      }
    };
    const devtoolsInterval = setInterval(detectDevtools, 1000);
    const onKeyDown = (e: KeyboardEvent): void => {
      const ctrl = e.ctrlKey || e.metaKey;
      const isDebugShortcut =
        e.key === 'F12' ||
        (ctrl && e.shiftKey && ['i', 'I', 'j', 'J', 'c', 'C'].includes(e.key)) ||
        (ctrl && ['u', 'U'].includes(e.key));
      if (isDebugShortcut) {
        throttledReport('KEYBOARD_SHORTCUT_BLOCKED', `key=${e.key} ctrl=${ctrl} shift=${e.shiftKey}`);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    const onCopy = (e: ClipboardEvent): void => {
      const target = e.target as HTMLElement | null;
      if (target?.closest('[data-sensitive]')) {
        throttledReport('CLIPBOARD_EXFILTRATION', `tag=${target.tagName}`);
      }
    };
    document.addEventListener('copy', onCopy);
    const onContextMenu = (e: MouseEvent): void => {
      const target = e.target as HTMLElement | null;
      if (target?.closest('[data-sensitive]')) {
        throttledReport('RIGHT_CLICK_SENSITIVE', `tag=${target.tagName}`);
      }
    };
    document.addEventListener('contextmenu', onContextMenu);
    const iframeObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (node instanceof HTMLIFrameElement) {
            const src = node.src || '';
            if (src && !src.startsWith(window.location.origin)) {
              throttledReport('IFRAME_INJECTION_ATTEMPT', `src=${src.slice(0, 200)}`);
            }
          }
        }
      }
    });
    iframeObserver.observe(document.body, { childList: true, subtree: true });
    let focusBlurCount = 0;
    let focusBlurTimer: ReturnType<typeof setTimeout> | null = null;
    const onFocusBlur = (): void => {
      focusBlurCount += 1;
      if (!focusBlurTimer) {
        focusBlurTimer = setTimeout(() => {
          if (focusBlurCount > 10) {
            throttledReport('FOCUS_BLUR_PATTERN', `count=${focusBlurCount} in 5s`);
          }
          focusBlurCount = 0;
          focusBlurTimer = null;
        }, 5000);
      }
    };
    window.addEventListener('focus', onFocusBlur);
    window.addEventListener('blur', onFocusBlur);

    return () => {
      clearInterval(devtoolsInterval);
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('copy', onCopy);
      document.removeEventListener('contextmenu', onContextMenu);
      iframeObserver.disconnect();
      window.removeEventListener('focus', onFocusBlur);
      window.removeEventListener('blur', onFocusBlur);
      if (focusBlurTimer) clearTimeout(focusBlurTimer);
    };
  }, []);
}
