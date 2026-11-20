"use client";

import { useCallback, useEffect, useRef } from "react";
import { useAccess } from "@/api/queries";
import { API_BASE_URL } from "./config";
import { useSession } from "./session";
import { Telemetry, sendToApi, telemetryEnabled, type EventProps, type ProductEventName } from "./telemetry";

/**
 * Mesure produit de la console : une instance par rôle (le rôle désigne l'écran pour l'API), jeton
 * de la session courante. Hors ligne, les événements attendent le retour du réseau.
 */
export function useTrack(): (name: ProductEventName, props?: EventProps) => void {
  const session = useSession();
  const { roles } = useAccess();
  const role = session.role ?? roles[0] ?? null;
  const tokenRef = useRef(session.token);
  tokenRef.current = session.token;
  const instance = useRef<{ role: string; telemetry: Telemetry } | null>(null);

  useEffect(() => {
    const onOnline = () => instance.current?.telemetry.flush();
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, []);

  return useCallback(
    (name, props) => {
      if (!role) return;
      if (instance.current?.role !== role) {
        instance.current = {
          role,
          telemetry: new Telemetry({
            surface: "console",
            role,
            send: sendToApi(API_BASE_URL),
            isOnline: () => navigator.onLine,
            isEnabled: telemetryEnabled,
            getToken: () => tokenRef.current,
          }),
        };
      }
      instance.current.telemetry.track(name, props);
    },
    [role],
  );
}
