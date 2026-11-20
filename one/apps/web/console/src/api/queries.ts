"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/lib/session";
import { DEFAULT_TIMEZONE } from "@/lib/format";
import { apiRequest, newIdempotencyKey, type Query } from "./client";
import { requireSourcedAnswer, requireSourcedDraft } from "./joe-guard";
import type {
  BrandingSettings,
  ConfigurationTemplate,
  ConfigurationTemplateList,
  CreateConfigurationTemplateRequest,
  CreateOrganizationRequest,
  OrganizationOnboarding,
  UpdateBrandingRequest,
  ClaimDecisionKind,
  DecisionDraft,
  JoeAnswer,
  JoeQuestionRequest,
  ProductMetrics,
  SearchResults,
  ClaimDetail,
  ClaimList,
  ClaimStatus,
  ContributionList,
  CurrentUser,
  Entitlements,
  LedgerAccountList,
  LedgerBalance,
  LedgerEntryList,
  MedicalReason,
  Member,
  MemberList,
  MemberStatus,
  PlanList,
  Role,
  WorkQueue,
} from "./types";

/** Clés TanStack Query, préfixées par le jeton : changer de profil ne réutilise aucun cache. */
export const keys = {
  me: (token: string | null) => [token, "me"] as const,
  workQueue: (token: string | null) => [token, "work-queue"] as const,
  claims: (token: string | null, filters?: ClaimFilters) => [token, "claims", filters ?? {}] as const,
  claim: (token: string | null, id: string) => [token, "claim", id] as const,
  members: (token: string | null, filters?: MemberFilters) => [token, "members", filters ?? {}] as const,
  member: (token: string | null, id: string) => [token, "member", id] as const,
  ledger: (token: string | null) => [token, "ledger"] as const,
  plans: (token: string | null) => [token, "plans"] as const,
  search: (token: string | null, q: string) => [token, "search", q] as const,
  metrics: (token: string | null, from: string, to: string) => [token, "metrics", from, to] as const,
};

function useToken(): string | null {
  return useSession().token;
}

export function useCurrentUser() {
  const token = useToken();
  return useQuery({
    queryKey: keys.me(token),
    queryFn: () => apiRequest<CurrentUser>("/v1/me", { token }),
    enabled: token !== null,
    staleTime: 5 * 60_000,
  });
}

/** Rôles et fuseau de l'utilisateur connecté (issus de /v1/me, jamais supposés). */
export function useAccess(): { roles: Role[]; has: (role: Role) => boolean; timezone: string; ready: boolean } {
  const me = useCurrentUser();
  const roles = me.data?.roles.map((r) => r.role) ?? [];
  return {
    roles,
    has: (role) => roles.includes(role),
    timezone: me.data?.organization.timezone ?? DEFAULT_TIMEZONE,
    ready: me.isSuccess,
  };
}

export function useWorkQueue(enabled = true) {
  const token = useToken();
  return useQuery({
    queryKey: keys.workQueue(token),
    queryFn: () => apiRequest<WorkQueue>("/v1/work-queue", { token }),
    enabled: enabled && token !== null,
  });
}

export interface ClaimFilters {
  status?: ClaimStatus;
  fraudFlagged?: boolean;
  memberId?: string;
  limit?: number;
}

function claimQuery(filters: ClaimFilters): Query {
  return {
    status: filters.status,
    fraud_flagged: filters.fraudFlagged ? true : undefined,
    member_id: filters.memberId,
    limit: filters.limit ?? 50,
  };
}

export function useClaims(filters: ClaimFilters) {
  const token = useToken();
  return useInfiniteQuery({
    queryKey: keys.claims(token, filters),
    queryFn: ({ pageParam }) =>
      apiRequest<ClaimList>("/v1/claims", { token, query: { ...claimQuery(filters), cursor: pageParam } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.page.next_cursor ?? undefined,
    enabled: token !== null,
  });
}

export function useClaim(id: string | null) {
  const token = useToken();
  return useQuery({
    queryKey: keys.claim(token, id ?? ""),
    queryFn: () => apiRequest<ClaimDetail>(`/v1/claims/${encodeURIComponent(id ?? "")}`, { token }),
    enabled: token !== null && id !== null,
  });
}

/**
 * Décision du médecin-conseil. La clé d'idempotence est fixée à l'ouverture de la confirmation :
 * un double clic ou un nouvel essai après coupure ne crée pas deux décisions.
 */
export function useDecideClaim(claimId: string) {
  const token = useToken();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { decision: ClaimDecisionKind; reasonCode: string; idempotencyKey: string }) =>
      apiRequest<ClaimDetail>(`/v1/claims/${encodeURIComponent(claimId)}/decisions`, {
        token,
        method: "POST",
        body: { decision: input.decision, reason_code: input.reasonCode },
        idempotencyKey: input.idempotencyKey,
      }),
    onSuccess: async (detail) => {
      client.setQueryData(keys.claim(token, claimId), detail);
      await Promise.all([
        client.invalidateQueries({ queryKey: [token, "claims"] }),
        client.invalidateQueries({ queryKey: keys.workQueue(token) }),
        client.invalidateQueries({ queryKey: keys.ledger(token) }),
      ]);
    },
  });
}

export { newIdempotencyKey };

/**
 * Lecture du motif médical : action auditée, jamais mise en cache (Cache-Control: no-store).
 * gcTime 0 : dès que plus aucun composant n'observe la lecture (tiroir fermé, « Masquer »),
 * TanStack Query retire la mutation et son motif du MutationCache (secret médical, R6).
 */
export function useReadMedicalReason(claimId: string) {
  const token = useToken();
  return useMutation({
    gcTime: 0,
    mutationFn: () =>
      apiRequest<MedicalReason>(`/v1/claims/${encodeURIComponent(claimId)}/medical-reason`, { token }),
  });
}

export interface MemberFilters {
  status?: MemberStatus;
  q?: string;
}

export function useMembers(filters: MemberFilters) {
  const token = useToken();
  return useInfiniteQuery({
    queryKey: keys.members(token, filters),
    queryFn: ({ pageParam }) =>
      apiRequest<MemberList>("/v1/members", {
        token,
        query: { status: filters.status, q: filters.q, limit: 50, cursor: pageParam },
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.page.next_cursor ?? undefined,
    enabled: token !== null,
  });
}

export function useMember(id: string | null) {
  const token = useToken();
  return useQuery({
    queryKey: keys.member(token, id ?? ""),
    queryFn: () => apiRequest<Member>(`/v1/members/${encodeURIComponent(id ?? "")}`, { token }),
    enabled: token !== null && id !== null,
  });
}

export function useEntitlements(id: string, enabled: boolean) {
  const token = useToken();
  return useQuery({
    queryKey: [...keys.member(token, id), "entitlements"],
    queryFn: () => apiRequest<Entitlements>(`/v1/members/${encodeURIComponent(id)}/entitlements`, { token }),
    enabled: enabled && token !== null,
  });
}

export function useContributions(id: string, enabled: boolean) {
  const token = useToken();
  return useQuery({
    queryKey: [...keys.member(token, id), "contributions"],
    queryFn: () => apiRequest<ContributionList>(`/v1/members/${encodeURIComponent(id)}/contributions`, { token }),
    enabled: enabled && token !== null,
  });
}

export function useLedgerAccounts() {
  const token = useToken();
  return useQuery({
    queryKey: [...keys.ledger(token), "accounts"],
    queryFn: () => apiRequest<LedgerAccountList>("/v1/ledger/accounts", { token }),
    enabled: token !== null,
    staleTime: 10 * 60_000,
  });
}

export function useLedgerEntries(accountCode: string | undefined) {
  const token = useToken();
  return useInfiniteQuery({
    queryKey: [...keys.ledger(token), "entries", accountCode ?? ""],
    queryFn: ({ pageParam }) =>
      apiRequest<LedgerEntryList>("/v1/ledger/entries", {
        token,
        query: { account_code: accountCode, limit: 50, cursor: pageParam },
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.page.next_cursor ?? undefined,
    enabled: token !== null,
  });
}

export function useLedgerBalance() {
  const token = useToken();
  return useQuery({
    queryKey: [...keys.ledger(token), "balance"],
    queryFn: () => apiRequest<LedgerBalance>("/v1/ledger/balance", { token }),
    enabled: token !== null,
  });
}

export function usePlans(enabled = true) {
  const token = useToken();
  return useQuery({
    queryKey: keys.plans(token),
    queryFn: () => apiRequest<PlanList>("/v1/plans", { token }),
    enabled: enabled && token !== null,
    staleTime: 10 * 60_000,
  });
}

/* ------------------------------------------------------------------ L8 : recherche ⌘K et JOE */

/** Recherche ⌘K (operationId `search`) : adhérents, dossiers, prestataires visibles par l'utilisateur. */
export function useSearch(q: string, enabled: boolean) {
  const token = useToken();
  return useQuery({
    queryKey: keys.search(token, q),
    queryFn: ({ signal }) => apiRequest<SearchResults>("/v1/search", { token, query: { q }, signal }),
    enabled: enabled && token !== null && q.length >= 2,
    staleTime: 30_000,
    retry: false,
  });
}

/**
 * Question à JOE (operationId `askJoe`) : lecture seule, réponse avec ses sources. Jamais mise en
 * cache au-delà de l'affichage (gcTime 0) : la réponse peut citer des données d'adhérent.
 */
export function useAskJoe() {
  const token = useToken();
  return useMutation({
    gcTime: 0,
    mutationFn: async (body: JoeQuestionRequest) => requireSourcedAnswer(await apiRequest<JoeAnswer>("/v1/joe/questions", { token, method: "POST", body })),
  });
}

/** Brouillon de décision (operationId `draftClaimDecision`) : jamais appliqué, seul decideClaim décide. */
export function useDraftDecision() {
  const token = useToken();
  return useMutation({
    gcTime: 0,
    mutationFn: async (claimId: string) => requireSourcedDraft(await apiRequest<DecisionDraft>("/v1/joe/decision-drafts", { token, method: "POST", body: { claim_id: claimId } })),
  });
}

/* ------------------------------------------------------------------ P2 : mesure produit */

/** Indicateurs k-anonymes de l'organisation (operationId `getProductMetrics`, gestionnaire et admin). */
export function useProductMetrics(from: string, to: string, enabled = true) {
  const token = useToken();
  return useQuery({
    queryKey: keys.metrics(token, from, to),
    queryFn: () => apiRequest<ProductMetrics>("/v1/metrics/product", { token, query: { from, to } }),
    enabled: enabled && token !== null,
  });
}

// ------------------------------------------------------------------ P3 marque blanche et plateforme
const p3Keys = {
  branding: (token: string | null) => [token, "branding"] as const,
  templates: (token: string | null) => [token, "configuration-templates"] as const,
};

/** Réglages de marque de l'organisation du jeton (admin seulement). */
export function useBrandingSettings() {
  const token = useToken();
  return useQuery({
    queryKey: p3Keys.branding(token),
    queryFn: () => apiRequest<BrandingSettings>("/v1/organization/branding", { token }),
    enabled: token !== null,
    staleTime: 0,
  });
}

export function useUpdateBranding() {
  const token = useToken();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateBrandingRequest) => apiRequest<BrandingSettings>("/v1/organization/branding", { token, method: "PUT", body }),
    onSuccess: (settings) => client.setQueryData(p3Keys.branding(token), settings),
  });
}

/** `verifyBrandingDomain` (CR-P3-02) : preuve DNS TXT de la propriété du domaine personnalisé. */
export function useVerifyBrandingDomain() {
  const token = useToken();
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest<BrandingSettings>("/v1/organization/branding/domain-verification", { token, method: "POST" }),
    onSuccess: (settings) => client.setQueryData(p3Keys.branding(token), settings),
  });
}

export function useConfigurationTemplates() {
  const token = useToken();
  return useQuery({
    queryKey: p3Keys.templates(token),
    queryFn: () => apiRequest<ConfigurationTemplateList>("/v1/platform/configuration-templates", { token }),
    enabled: token !== null,
  });
}

export function useCreateConfigurationTemplate() {
  const token = useToken();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateConfigurationTemplateRequest) => apiRequest<ConfigurationTemplate>("/v1/platform/configuration-templates", { token, method: "POST", body }),
    onSuccess: () => client.invalidateQueries({ queryKey: p3Keys.templates(token) }),
  });
}

export function useCreateOrganization() {
  const token = useToken();
  return useMutation({
    mutationFn: (body: CreateOrganizationRequest) => apiRequest<OrganizationOnboarding>("/v1/platform/organizations", { token, method: "POST", body }),
  });
}
