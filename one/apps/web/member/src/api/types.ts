import type { components } from "./schema";

/** Alias des schémas du contrat (specs/openapi.yaml, généré par `make gen-api`). */
type S = components["schemas"];
export type Problem = S["Problem"];
export type ErrorCode = S["ErrorCode"];
export type CurrentUser = S["CurrentUser"];
export type Entitlements = S["Entitlements"];
export type MemberStatus = S["MemberStatus"];
export type RuleRef = S["RuleRef"];
export type ClaimStatus = S["ClaimStatus"];
export type PaymentChannel = S["PaymentChannel"];
export type PaymentLink = S["PaymentLink"];
export type PublicPaymentLink = S["PublicPaymentLink"];
export type CheckoutRequest = S["CheckoutRequest"];
export type Checkout = S["Checkout"];
export type BeneficiaryRelationship = S["BeneficiaryRelationship"];
export type MyCard = S["MyCard"];
export type MyBeneficiary = S["MyBeneficiary"];
export type MyBeneficiaryList = S["MyBeneficiaryList"];
export type MyClaim = S["MyClaim"];
export type MyClaimList = S["MyClaimList"];
export type TrackingStep = S["TrackingStep"];
export type ClaimTracking = S["ClaimTracking"];
export type MyContribution = S["MyContribution"];
export type MyContributions = S["MyContributions"];
export type ContributionStatus = MyContribution["status"];
