"use client";

import { createContext, useContext } from "react";

/**
 * Session des espaces partenaires. Le fournisseur d'identité n'est pas choisi (PRD §10 Q2) :
 * l'app ne dépend que de cette interface. En démonstration seulement, le profil se choisit à
 * l'écran et le jeton vaut `demo.<rôle>`.
 */
export type DemoRole = "assureur" | "employeur";
export const DEMO_ROLES: readonly DemoRole[] = ["assureur", "employeur"] as const;

export interface Session {
  mode: "demo" | "unconfigured";
  token: string | null;
  role: DemoRole | null;
  setRole: (role: DemoRole) => void;
}

const PREFIX = "demo.";
export const DEMO_ROLE_STORAGE_KEY = "mulemacare-one.partenaires.demo-role";

export function demoToken(role: DemoRole): string {
  return `${PREFIX}${role}`;
}

export function roleFromDemoToken(token: string | null | undefined): DemoRole | null {
  if (!token?.startsWith(PREFIX)) return null;
  const role = token.slice(PREFIX.length);
  return isDemoRole(role) ? role : null;
}

export function isDemoRole(value: string | null): value is DemoRole {
  return value !== null && (DEMO_ROLES as readonly string[]).includes(value);
}

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession doit être utilisé sous SessionContext.");
  return session;
}
