"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useSession } from "@/lib/session";
import { apiGet, apiGetText } from "./client";
import type { CurrentUser, EmployerConsumption, EmployerContractList, InsurerPortfolio } from "./types";

/** Clés préfixées par le jeton : changer de profil ne réutilise aucun cache. */
export const keys = {
  me: (token: string | null) => [token, "me"] as const,
  portfolio: (token: string | null, from: string, to: string) => [token, "portfolio", from, to] as const,
  consumption: (token: string | null, from: string, to: string) => [token, "consumption", from, to] as const,
  contracts: (token: string | null, withinDays: number) => [token, "contracts", withinDays] as const,
};

export function useCurrentUser() {
  const { token } = useSession();
  return useQuery({ queryKey: keys.me(token), queryFn: () => apiGet<CurrentUser>("/v1/me", token), enabled: token !== null, staleTime: 5 * 60_000 });
}

export function useAccess() {
  const me = useCurrentUser();
  const roles = me.data?.roles.map((r) => r.role) ?? [];
  return { roles, has: (role: string) => roles.some((r) => r === role), ready: me.isSuccess, timezone: me.data?.organization.timezone ?? "Africa/Abidjan", organization: me.data?.organization ?? null };
}

/** `getInsurerPortfolio` (assureur, admin) : agrégats k-anonymes de l'organisation du jeton. */
export function useInsurerPortfolio(from: string, to: string, enabled = true) {
  const { token } = useSession();
  return useQuery({ queryKey: keys.portfolio(token, from, to), queryFn: () => apiGet<InsurerPortfolio>("/v1/insurer/portfolio", token, { from, to }), enabled: enabled && token !== null });
}

/** `exportInsurerPortfolio` : mêmes agrégats et mêmes masques, en CSV. */
export function useExportPortfolio() {
  const { token } = useSession();
  return useMutation({ mutationFn: ({ from, to }: { from: string; to: string }) => apiGetText("/v1/insurer/portfolio/export", token, { from, to }) });
}

/** `getEmployerConsumption` (employeur) : consommation agrégée par groupe, sans personne. */
export function useEmployerConsumption(from: string, to: string, enabled = true) {
  const { token } = useSession();
  return useQuery({ queryKey: keys.consumption(token, from, to), queryFn: () => apiGet<EmployerConsumption>("/v1/employer/consumption", token, { from, to }), enabled: enabled && token !== null });
}

/** `listEmployerContracts` (employeur) : contrats de groupe et échéances. */
export function useEmployerContracts(withinDays: number, enabled = true) {
  const { token } = useSession();
  return useQuery({ queryKey: keys.contracts(token, withinDays), queryFn: () => apiGet<EmployerContractList>("/v1/employer/contracts", token, { within_days: withinDays }), enabled: enabled && token !== null });
}
