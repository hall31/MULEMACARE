"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError } from "@/api/client";
import { API_MOCKING } from "@/lib/config";
import { DEMO_ROLE_STORAGE_KEY, SessionContext, demoToken, isDemoRole, type DemoRole, type Session } from "@/lib/session";

/** Service worker MSW démarré avant la première requête (démonstration seulement). */
function useMockWorker(): boolean {
  const [ready, setReady] = useState(!API_MOCKING);
  useEffect(() => {
    if (!API_MOCKING) return;
    let cancelled = false;
    void import("@/mocks/browser").then(async ({ worker }) => {
      await worker.start({ onUnhandledRequest: "bypass", quiet: true });
      if (!cancelled) setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return ready;
}

function useDemoSession(mocksReady: boolean): Session {
  const [role, setRoleState] = useState<DemoRole>("assureur");
  useEffect(() => {
    const stored = window.localStorage.getItem(DEMO_ROLE_STORAGE_KEY);
    if (isDemoRole(stored)) setRoleState(stored);
  }, []);
  const setRole = useCallback((next: DemoRole) => {
    window.localStorage.setItem(DEMO_ROLE_STORAGE_KEY, next);
    setRoleState(next);
  }, []);
  return useMemo<Session>(
    // Le jeton n'existe qu'une fois les mocks prêts : l'écran se rend tout de suite (rendu serveur
    // compris, LCP), seules les lectures attendent.
    () => (API_MOCKING ? { mode: "demo", role, token: mocksReady ? demoToken(role) : null, setRole } : { mode: "unconfigured", role: null, token: null, setRole }),
    [role, setRole, mocksReady],
  );
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            refetchOnWindowFocus: false,
            // Une erreur métier (4xx) ne se corrige pas en réessayant ; une panne réseau ou 5xx, si.
            retry: (count, error) => count < 2 && (!(error instanceof ApiError) || error.status === 0 || error.status >= 500),
          },
        },
      }),
  );
  const ready = useMockWorker();
  const session = useDemoSession(ready);
  return (
    <SessionContext.Provider value={session}>
      <QueryClientProvider client={client}>
        {children}
      </QueryClientProvider>
    </SessionContext.Provider>
  );
}
