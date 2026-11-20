"use client";

import { createContext, useContext, useEffect, type ReactNode } from "react";
import type { BrandIdentity } from "@shared/brand";
import { t } from "@/i18n";

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

/**
 * Logo de l'organisation (déjà assaini, rendu en image seulement : un SVG n'y exécute rien), à la
 * taille réservée de la marque (32 px, aucun saut de mise en page) ; sinon la marque MulemaCare.
 * Décoratif : le nom de l'organisation est toujours écrit à côté.
 */
export function BrandLogo({ fallback }: { fallback: ReactNode }) {
  const brand = useBrand();
  if (!brand?.logoSrc) return <>{fallback}</>;
  return <img src={brand.logoSrc} alt="" width={32} height={32} className="bm bm-logo" data-testid="brand-logo" />;
}

/** Nom de l'organisation (texte brut, échappé par React), ou le nom de l'application sans marque. */
export function BrandName() {
  const brand = useBrand();
  return <>{brand?.displayName ?? t("app.name")}</>;
}
