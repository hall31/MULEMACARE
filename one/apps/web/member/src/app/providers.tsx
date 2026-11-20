"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { createMemberQueryClient } from "@/lib/query-client";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(createMemberQueryClient);

  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
  }, []);

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
