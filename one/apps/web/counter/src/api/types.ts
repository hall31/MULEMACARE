import type { components } from "./schema";

/** Alias des schémas du contrat (specs/openapi.yaml, généré par `pnpm gen:api`). */
type S = components["schemas"];
export type Problem = S["Problem"];
export type ErrorCode = S["ErrorCode"];
export type CurrentUser = S["CurrentUser"];
export type Identification = S["Identification"];
export type Beneficiary = S["Beneficiary"];
export type MemberStatus = S["MemberStatus"];
export type StartIdentificationRequest = S["StartIdentificationRequest"];
export type PhotoConfirmationRequest = S["PhotoConfirmationRequest"];
export type CodeSent = S["CodeSent"];
export type CodeVerificationRequest = S["CodeVerificationRequest"];
export type CreateClaimRequest = S["CreateClaimRequest"];
export type ClaimCreated = S["ClaimCreated"];
export type Decision = S["Decision"];
export type RuleRef = S["RuleRef"];
export type RuleCheck = S["RuleCheck"];
export type ClaimItemInput = S["ClaimItemInput"];
export type TariffItem = S["TariffItem"];
export type OfflinePolicy = S["OfflinePolicy"];
export type RegisterCounterDeviceRequest = S["RegisterCounterDeviceRequest"];
export type CounterDevice = S["CounterDevice"];
export type OfflineAuthorizationInput = S["OfflineAuthorizationInput"];
export type OfflineSyncRequest = S["OfflineSyncRequest"];
export type OfflineSyncResult = S["OfflineSyncResult"];
export type OfflineSyncItemResult = S["OfflineSyncItemResult"];
