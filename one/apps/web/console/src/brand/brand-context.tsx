"use client";

import { createContext, useContext, useEffect, type ReactNode } from "react";
import type { BrandIdentity } from "@shared/brand";

/** Identité de l'organisation (nom en texte brut, logo assaini), ou null : marque MulemaCare. */
const BrandContext = createContext<BrandIdentity | null>(null);

export function BrandProvider({ identity, children }: { identity: BrandIdentity | null; children: ReactNode }) {
  return <BrandContext.Provider value={identity}>{children}</BrandContext.Provider>;
}

export function useBrand(): BrandIdentity | null {
  return useContext(BrandContext);
}

/** Développement seulement : dit dans la console du navigateur pourquoi la marque est repliée. */
export function BrandDevNotice({ message }: { message: string }) {
  useEffect(() => {
    console.warn(message);
  }, [message]);
  return null;
}
