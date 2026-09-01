"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import {
  enterResidentContext,
  exitResidentContext,
  type ResidentContextResponse,
} from "@ev-chargeops/api-client";

const STORAGE_KEY = "ev-chargeops.resident-context";

/** The active context, held where it belongs: outside React.
 *
 * It lives in `sessionStorage` and not in a cookie because nothing about
 * impersonating a unit should outlive the tab or travel to another one. The
 * server is the authority regardless — this copy only decides which header to
 * send and what the banner says.
 */
const listeners = new Set<() => void>();
let snapshot: ResidentContextResponse | null = null;
let hydrated = false;
let expiryTimer: number | undefined;

function parse(raw: string | null): ResidentContextResponse | null {
  if (raw == null) return null;
  try {
    const parsed = JSON.parse(raw) as ResidentContextResponse;
    return Date.parse(parsed.expiresAt) > Date.now() ? parsed : null;
  } catch {
    return null;
  }
}

function emit(): void {
  for (const listener of listeners) listener();
}

/** Drop the context exactly when the server stops honouring it.
 *
 * A stale context left on screen would make the banner lie about what the
 * reader is seeing, which is the one thing this banner exists to prevent.
 */
function scheduleExpiry(): void {
  if (expiryTimer != null) window.clearTimeout(expiryTimer);
  expiryTimer = undefined;
  if (snapshot == null) return;
  const remaining = Date.parse(snapshot.expiresAt) - Date.now();
  expiryTimer = window.setTimeout(() => store.clear(), Math.max(remaining, 0));
}

const store = {
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  getSnapshot(): ResidentContextResponse | null {
    if (!hydrated) {
      hydrated = true;
      snapshot = parse(window.sessionStorage.getItem(STORAGE_KEY));
      scheduleExpiry();
    }
    return snapshot;
  },
  getServerSnapshot(): ResidentContextResponse | null {
    return null;
  },
  set(context: ResidentContextResponse): void {
    hydrated = true;
    snapshot = context;
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(context));
    scheduleExpiry();
    emit();
  },
  clear(): void {
    hydrated = true;
    snapshot = null;
    window.sessionStorage.removeItem(STORAGE_KEY);
    scheduleExpiry();
    emit();
  },
};

type ResidentContextState = {
  context: ResidentContextResponse | null;
  enter: (unitId: string) => Promise<ResidentContextResponse>;
  exit: () => Promise<void>;
};

const ResidentContextValue = createContext<ResidentContextState | null>(null);

export function ResidentContextProvider({
  accessToken,
  apiUrl,
  children,
}: {
  accessToken: string;
  apiUrl: string;
  children: ReactNode;
}) {
  const context = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot,
  );

  const enter = useCallback(
    async (unitId: string) => {
      const entered = await enterResidentContext(unitId, accessToken, {
        baseUrl: apiUrl,
      });
      store.set(entered);
      return entered;
    },
    [accessToken, apiUrl],
  );

  const exit = useCallback(async () => {
    const active = snapshot;
    store.clear();
    if (active == null) return;
    try {
      await exitResidentContext(active.id, accessToken, { baseUrl: apiUrl });
    } catch {
      // The context is already gone from this tab. A failed audit of the exit
      // must not trap the manager inside the resident view.
    }
  }, [accessToken, apiUrl]);

  const value = useMemo(
    () => ({ context, enter, exit }),
    [context, enter, exit],
  );

  // The banner is not rendered here on purpose: the shell owns the layout, and
  // a strip floating outside its grid neither spans the page nor sticks.
  return (
    <ResidentContextValue.Provider value={value}>
      {children}
    </ResidentContextValue.Provider>
  );
}

export function useResidentContext(): ResidentContextState {
  const value = useContext(ResidentContextValue);
  if (value == null) {
    throw new Error("useResidentContext requires ResidentContextProvider");
  }
  return value;
}

export function ResidentBanner({
  context,
  onExit,
}: {
  context: ResidentContextResponse;
  onExit: () => Promise<void>;
}) {
  return (
    <div className="resident-banner" role="status">
      <span className="resident-banner-mark" aria-hidden="true" />
      <p>
        Você está vendo a fatura como o morador da unidade{" "}
        <strong>{context.unitCode}</strong> ({context.unitName}).{" "}
        <span className="resident-banner-readonly">Somente leitura.</span>
      </p>
      <button type="button" onClick={() => void onExit()}>
        Sair da visão do morador
      </button>
    </div>
  );
}
