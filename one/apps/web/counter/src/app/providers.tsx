"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          // Le comptoir gère lui-même le hors ligne : pas de mise en pause silencieuse.
          queries: { networkMode: "always", retry: false, refetchOnWindowFocus: false, staleTime: 5 * 60_000 },
          mutations: { networkMode: "always", retry: false },
        },
      }),
  );

  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
  }, []);

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
