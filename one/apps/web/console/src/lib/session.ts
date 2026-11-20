"use client";

import { createContext, useContext } from "react";

/**
 * Session de la console. Le fournisseur d'identité n'est pas choisi (PRD §10 Q2) :
 * la console dépend seulement de cette interface. L'implémentation de démonstration
 * (profil choisi à l'écran, jeton `demo.<rôle>`) n'existe qu'en mode mock.
 */
export type DemoRole = "gestionnaire" | "medecin_conseil" | "admin" | "admin_plateforme";

/**
 * Profils de démonstration. P3 : `admin` (administrateur de l'organisation : réglage de la marque)
 * et `admin_plateforme` (accueil d'organisations, gabarits ; aucun accès métier, Q-P3-01).
 */
export const DEMO_ROLES: readonly DemoRole[] = ["gestionnaire", "medecin_conseil", "admin", "admin_plateforme"] as const;

export interface Session {
  mode: "demo" | "unconfigured";
  /** Jeton porteur envoyé à l'API ; null si aucune connexion n'est configurée. */
  token: string | null;
  role: DemoRole | null;
  setRole: (role: DemoRole) => void;
}

const DEMO_TOKEN_PREFIX = "demo.";

export function demoToken(role: DemoRole): string {
  return `${DEMO_TOKEN_PREFIX}${role}`;
}

export function roleFromDemoToken(token: string | null | undefined): DemoRole | null {
  if (!token?.startsWith(DEMO_TOKEN_PREFIX)) return null;
  const role = token.slice(DEMO_TOKEN_PREFIX.length);
  return (DEMO_ROLES as readonly string[]).includes(role) ? (role as DemoRole) : null;
}

export function isDemoRole(value: string | null): value is DemoRole {
  return value !== null && (DEMO_ROLES as readonly string[]).includes(value);
}

export const DEMO_ROLE_STORAGE_KEY = "mulemacare-one.console.demo-role";

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession doit être utilisé sous <SessionProvider>.");
  return session;
}
