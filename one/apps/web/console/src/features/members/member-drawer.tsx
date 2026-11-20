"use client";

import { useState } from "react";
import { useAccess, useClaims, useContributions, useEntitlements, useMember } from "@/api/queries";
import type { Member } from "@/api/types";
import { EmptyState, ErrorState, LoadingRows } from "@/components/states";
import { ClaimStatusBadge, ContributionStatusBadge, Meter, MemberStatusBadge } from "@/components/status-badges";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/misc";
import { Sheet, SheetBody, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { t, tDynamic } from "@/i18n";
import { formatDate, formatDateTime, formatMoney, initials } from "@/lib/format";
import { usageTone } from "@/lib/status";

type TabKey = "summary" | "rights" | "claims" | "contributions";

/** Fiche adhérent en lecture : identité, famille, droits, prises en charge, cotisations. Aucune donnée médicale. */
export function MemberDrawer({ memberId, planName, onClose }: { memberId: string; planName: Map<string, string>; onClose: () => void }) {
  const member = useMember(memberId);
  const name = member.data ? `${member.data.holder.given_name} ${member.data.holder.family_name}` : null;

  return (
    <Sheet open onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <SheetContent aria-describedby={undefined}>
        <SheetTitle className="sr-only">{name ? t("member.drawerLabel", { name }) : t("states.loading")}</SheetTitle>
        {member.isPending ? <LoadingRows rows={6} /> : null}
        {member.isError ? (
          <div className="p-5">
            <ErrorState error={member.error} onRetry={() => void member.refetch()} />
          </div>
        ) : null}
        {member.data && name ? <MemberDetail member={member.data} name={name} planName={planName} /> : null}
      </SheetContent>
    </Sheet>
  );
}

function MemberDetail({ member, name, planName }: { member: Member; name: string; planName: Map<string, string> }) {
  const [tab, setTab] = useState<TabKey>("summary");
  const { timezone } = useAccess();

  return (
    <>
      <SheetHeader className="flex items-center gap-3">
        <span aria-hidden className="grid size-11 shrink-0 place-items-center rounded-md bg-brand-soft font-display text-[15px] font-semibold text-brand">
          {initials(name)}
        </span>
        <div className="min-w-0">
          <p className="font-display text-[19px] font-semibold">{name}</p>
          <p className="tabular text-xs text-fg-2">{member.member_number}</p>
        </div>
        <span className="ml-auto">
          <MemberStatusBadge status={member.status} />
        </span>
      </SheetHeader>
      <SheetBody>
        <Tabs value={tab} onValueChange={(v) => setTab(v as TabKey)}>
          <TabsList aria-label={t("member.tabsLabel")}>
            <TabsTrigger value="summary">{t("member.tabSummary")}</TabsTrigger>
            <TabsTrigger value="rights">{t("member.tabRights")}</TabsTrigger>
            <TabsTrigger value="claims">{t("member.tabClaims")}</TabsTrigger>
            <TabsTrigger value="contributions">{t("member.tabContributions")}</TabsTrigger>
          </TabsList>

          <TabsContent value="summary">
            <dl className="grid grid-cols-[140px_minmax(0,1fr)] gap-x-3.5 gap-y-2 text-[13px]">
              <dt className="text-fg-2">{t("member.plan")}</dt>
              <dd>{planName.get(member.plan_code) ?? member.plan_code}</dd>
              <dt className="text-fg-2">{t("member.enrolledOn")}</dt>
              <dd className="tabular-nums">{formatDate(member.enrolled_on)}</dd>
              <dt className="text-fg-2">{t("member.waitingEnds")}</dt>
              <dd className="tabular-nums">{formatDate(member.waiting_period_ends_on)}</dd>
              <dt className="text-fg-2">{t("member.statusSince")}</dt>
              <dd className="tabular-nums">{formatDateTime(member.status_changed_at, timezone)}</dd>
              <dt className="text-fg-2">{t("member.birthDate")}</dt>
              <dd className="tabular-nums">{formatDate(member.holder.birth_date)}</dd>
            </dl>
            <section aria-labelledby="family-title" className="flex flex-col gap-2">
              <h3 id="family-title" className="eyebrow">
                {t("member.family", { count: member.dependents.length + 1 })}
              </h3>
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <li className="rounded-md border border-line p-2.5 text-[13px]">
                  <span className="font-medium">{name}</span>
                  <span className="block text-xs text-fg-2">{t("member.holder")}</span>
                </li>
                {member.dependents.map((d) => (
                  <li key={d.id} className="rounded-md border border-line p-2.5 text-[13px]">
                    <span className="font-medium">
                      {d.given_name} {d.family_name}
                    </span>
                    <span className="block text-xs text-fg-2">{tDynamic("member.relationship", d.relationship)}</span>
                  </li>
                ))}
              </ul>
            </section>
          </TabsContent>

          <TabsContent value="rights">
            <RightsTab memberId={member.id} enabled={tab === "rights"} />
          </TabsContent>
          <TabsContent value="claims">
            <ClaimsTab memberId={member.id} enabled={tab === "claims"} />
          </TabsContent>
          <TabsContent value="contributions">
            <ContributionsTab memberId={member.id} enabled={tab === "contributions"} />
          </TabsContent>
        </Tabs>
      </SheetBody>
    </>
  );
}

function RightsTab({ memberId, enabled }: { memberId: string; enabled: boolean }) {
  const rights = useEntitlements(memberId, enabled);
  if (rights.isPending) return <LoadingRows rows={3} />;
  if (rights.isError) return <ErrorState error={rights.error} onRetry={() => void rights.refetch()} />;
  const r = rights.data;
  const ratio = r.family_annual_ceiling_xof > 0 ? r.consumed_xof / r.family_annual_ceiling_xof : 0;
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Badge tone={r.rights_open ? "ok" : "crit"}>{r.rights_open ? t("member.rightsOpen") : t("member.rightsClosed")}</Badge>
      </div>
      <div className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3">
          <span>{t("member.ceiling")}</span>
          <span className="tabular">{formatMoney(r.family_annual_ceiling_xof)}</span>
        </div>
        <Meter ratio={ratio} tone={usageTone(ratio)} width="w-full" label={t("member.ceilingUsage", { percent: Math.round(ratio * 100) })} />
        <p className="text-xs text-fg-2">{t("member.ceilingUsage", { percent: Math.round(ratio * 100) })}</p>
      </div>
      <dl className="grid grid-cols-[140px_minmax(0,1fr)] gap-x-3.5 gap-y-2 text-[13px]">
        <dt className="text-fg-2">{t("member.consumed")}</dt>
        <dd className="tabular">{formatMoney(r.consumed_xof)}</dd>
        <dt className="text-fg-2">{t("member.remaining")}</dt>
        <dd className="tabular">{formatMoney(r.remaining_xof)}</dd>
        <dt className="text-fg-2">{t("member.waitingEnds")}</dt>
        <dd className="tabular">{formatDate(r.waiting_period_ends_on)}</dd>
      </dl>
    </div>
  );
}

function ClaimsTab({ memberId, enabled }: { memberId: string; enabled: boolean }) {
  const claims = useClaims({ memberId, limit: 20 });
  if (!enabled) return null;
  if (claims.isPending) return <LoadingRows rows={3} />;
  if (claims.isError) return <ErrorState error={claims.error} onRetry={() => void claims.refetch()} />;
  const items = claims.data.pages.flatMap((p) => p.items);
  if (items.length === 0) return <EmptyState title={t("member.noClaims")} next={t("emptyNext.memberNoClaims")} />;
  return (
    <div className="rounded-md border border-line">
      <Table aria-label={t("member.tabClaims")}>
        <TableBody>
          {items.map((c) => (
            <TableRow key={c.id}>
              <TableCell className="tabular text-xs">{c.claim_number}</TableCell>
              <TableCell className="text-fg-2">{c.provider_name}</TableCell>
              <TableCell className="tabular text-right">{formatMoney(c.covered_xof, { unit: false })}</TableCell>
              <TableCell>
                <ClaimStatusBadge status={c.status} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ContributionsTab({ memberId, enabled }: { memberId: string; enabled: boolean }) {
  const contributions = useContributions(memberId, enabled);
  if (contributions.isPending) return <LoadingRows rows={3} />;
  if (contributions.isError) return <ErrorState error={contributions.error} onRetry={() => void contributions.refetch()} />;
  const items = contributions.data.items;
  if (items.length === 0) return <EmptyState title={t("member.noContributions")} next={t("emptyNext.memberNoContributions")} />;
  return (
    <div className="rounded-md border border-line">
      <Table aria-label={t("member.tabContributions")}>
        <TableHeader>
          <TableRow>
            <TableHead>{t("member.colPeriod")}</TableHead>
            <TableHead>{t("member.colDue")}</TableHead>
            <TableHead className="text-right">{t("member.colAmount")}</TableHead>
            <TableHead>{t("member.colChannel")}</TableHead>
            <TableHead>{t("member.colStatus")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((c) => (
            <TableRow key={c.id}>
              <TableCell className="tabular">{formatDate(c.period_start).slice(3)}</TableCell>
              <TableCell className="tabular">{formatDate(c.due_on)}</TableCell>
              <TableCell className="tabular text-right">{formatMoney(c.amount_xof, { unit: false })}</TableCell>
              <TableCell className="text-fg-2">{c.channel ? tDynamic("paymentChannel", c.channel) : t("common.none")}</TableCell>
              <TableCell>
                <ContributionStatusBadge status={c.status} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
