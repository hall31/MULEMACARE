/** Alias lisibles sur les types générés depuis specs/openapi.yaml (`make gen-api`). */
import type { components } from "./schema";

type S = components["schemas"];

export type Problem = S["Problem"];
export type ErrorCode = S["ErrorCode"];
export type CurrentUser = S["CurrentUser"];
export type Organization = S["Organization"];
export type Role = S["Role"];

export type KAnonymousValue = S["KAnonymousValue"];
export type StatusCount = S["StatusCount"];
export type MemberStatus = StatusCount["status"];
export type BenefitCategory = S["BenefitCategory"];
export type ProviderShare = S["ProviderShare"];
export type OtherProviders = S["OtherProviders"];
export type InsurerPortfolio = S["InsurerPortfolio"];
export type EmployerGroupConsumption = S["EmployerGroupConsumption"];
export type EmployerConsumption = S["EmployerConsumption"];
export type EmployerContract = S["EmployerContract"];
export type EmployerContractStatus = EmployerContract["status"];
export type EmployerContractList = S["EmployerContractList"];
