"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Toaster } from "sonner";
import { ApiError } from "@/api/client";
import { t } from "@/i18n";
import { API_MOCKING } from "@/lib/config";
import {
  DEMO_ROLE_STORAGE_KEY,
  SessionContext,
  demoToken,
  isDemoRole,
  type DemoRole,
  type Session,
} from "@/lib/session";

/** Démarre le service worker MSW avant la première requête (mode démonstration seulement). */
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

function useDemoSession(): Session {
  const [role, setRoleState] = useState<DemoRole>("gestionnaire");
  useEffect(() => {
    const stored = window.localStorage.getItem(DEMO_ROLE_STORAGE_KEY);
    if (isDemoRole(stored)) setRoleState(stored);
  }, []);
  const setRole = useCallback((next: DemoRole) => {
    window.localStorage.setItem(DEMO_ROLE_STORAGE_KEY, next);
    setRoleState(next);
  }, []);
  return useMemo<Session>(
    () =>
      API_MOCKING
        ? { mode: "demo", role, token: demoToken(role), setRole }
        : { mode: "unconfigured", role: null, token: null, setRole },
    [role, setRole],
  );
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // Une erreur métier (4xx) ne se corrige pas en réessayant ; une panne réseau ou 5xx, si.
            retry: (count, error) => count < 2 && (!(error instanceof ApiError) || error.status === 0 || error.status >= 500),
          },
        },
      }),
  );
  const session = useDemoSession();
  const mocksReady = useMockWorker();

  return (
    <SessionContext.Provider value={session}>
      <QueryClientProvider client={client}>
        {mocksReady ? (
          children
        ) : (
          <div role="status" className="grid min-h-screen place-items-center text-fg-2">
            {t("app.loadingSession")}
          </div>
        )}
        <Toaster
          position="bottom-center"
          toastOptions={{
            style: {
              background: "var(--fg)",
              color: "var(--bg)",
              border: "1px solid var(--fg)",
              borderRadius: "var(--r-md)",
              fontFamily: "var(--f-body)",
            },
          }}
        />
      </QueryClientProvider>
    </SessionContext.Provider>
  );
}
