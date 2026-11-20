/** Alias lisibles sur les types générés depuis specs/openapi.yaml (pnpm gen:api). */
import type { components } from "./schema";

type S = components["schemas"];

export type Problem = S["Problem"];
export type ErrorCode = S["ErrorCode"];
export type CurrentUser = S["CurrentUser"];
export type Organization = S["Organization"];
export type Role = S["Role"];
export type WorkQueue = S["WorkQueue"];

export type ClaimStatus = S["ClaimStatus"];
export type ClaimSummary = S["ClaimSummary"];
export type ClaimList = S["ClaimList"];
export type ClaimDetail = S["ClaimDetail"];
export type ClaimItem = S["ClaimItem"];
export type ClaimDecisionRecord = S["ClaimDecisionRecord"];
export type Authorization = S["Authorization"];
export type DecideClaimRequest = S["DecideClaimRequest"];
export type ClaimDecisionKind = DecideClaimRequest["decision"];
export type MedicalReason = S["MedicalReason"];
export type RuleRef = S["RuleRef"];

export type MemberStatus = S["MemberStatus"];
export type MemberSummary = S["MemberSummary"];
export type MemberList = S["MemberList"];
export type Member = S["Member"];
export type Dependent = S["Dependent"];
export type Entitlements = S["Entitlements"];
export type Contribution = S["Contribution"];
export type ContributionList = S["ContributionList"];
export type PaymentChannel = S["PaymentChannel"];

export type LedgerAccount = S["LedgerAccount"];
export type LedgerAccountList = S["LedgerAccountList"];
export type LedgerEntry = S["LedgerEntry"];
export type LedgerEntryList = S["LedgerEntryList"];
export type LedgerLine = S["LedgerLine"];
export type LedgerBalance = S["LedgerBalance"];

export type Plan = S["Plan"];
export type PlanList = S["PlanList"];
export type PlanVersion = S["PlanVersion"];
export type PlanVersionState = S["PlanVersionState"];
export type Coverage = S["Coverage"];

export type AuditEvent = S["AuditEvent"];

// ------------------------------------------------------------------ L8 JOE et recherche ⌘K
export type Source = S["Source"];
export type SearchHit = S["SearchHit"];
export type SearchResults = S["SearchResults"];
export type JoeQuestionRequest = S["JoeQuestionRequest"];
export type JoeAnswer = S["JoeAnswer"];
export type DecisionDraftRequest = S["DecisionDraftRequest"];
export type DecisionDraft = S["DecisionDraft"];
export type AiAction = S["AiAction"];
export type AiActionList = S["AiActionList"];

// ------------------------------------------------------------------ P2 mesure produit
export type ProductMetricKey = S["ProductMetricKey"];
export type ProductMetric = S["ProductMetric"];
export type ProductMetrics = S["ProductMetrics"];

// ------------------------------------------------------------------ P3 marque blanche et plateforme
export type HexColor = S["HexColor"];
export type BrandTokenOverrides = S["BrandTokenOverrides"];
export type BrandTheme = S["BrandTheme"];
export type BrandLogo = S["BrandLogo"];
export type BrandingSettings = S["BrandingSettings"];
export type UpdateBrandingRequest = S["UpdateBrandingRequest"];
export type FieldError = S["FieldError"];
export type ConfigurationTemplate = S["ConfigurationTemplate"];
export type ConfigurationTemplateList = S["ConfigurationTemplateList"];
export type CreateConfigurationTemplateRequest = S["CreateConfigurationTemplateRequest"];
export type CreateOrganizationRequest = S["CreateOrganizationRequest"];
export type OrganizationOnboarding = S["OrganizationOnboarding"];
export type OrganizationCapability = CreateOrganizationRequest["capabilities"][number];
export type CountryCode = Organization["country_code"];
