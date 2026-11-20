"use client";

import type { Identification, MemberStatus } from "@/api/types";
import { t } from "@/i18n";
import { formatRateBp, initials } from "@/lib/format";
import type { StatusTone } from "../tones";
import { Button, Pill, ScreenTitle, type IconName } from "../ui";
import { ScreenLayout } from "./ScreenLayout";

/** Droits ouverts → ok ; carence → warn ; suspendus → crit (contrat §5). Icône + mot. */
export const MEMBER_STATUS: Record<MemberStatus, { tone: StatusTone; icon: IconName }> = {
  actif: { tone: "ok", icon: "check" },
  carence: { tone: "warn", icon: "clock" },
  suspendu: { tone: "crit", icon: "x" },
};

interface Props {
  identification: Identification;
  busy: boolean;
  onConfirm: (confirmed: boolean) => void;
}

export function IdentityScreen({ identification, busy, onConfirm }: Props) {
  const person = identification.beneficiary;
  const status = MEMBER_STATUS[person.member_status];
  return (
    <ScreenLayout
      footer={
        <>
          <Button onClick={() => onConfirm(true)} busy={busy} disabled={busy}>
            {t("identity.yes")}
          </Button>
          <Button variant="danger" onClick={() => onConfirm(false)} disabled={busy}>
            {t("identity.no")}
          </Button>
        </>
      }
    >
      <ScreenTitle>{t("identity.title")}</ScreenTitle>
      <section className="member" aria-label={person.display_name}>
        {person.photo_url ? (
          // Photo servie par une URL signée de courte durée hébergée dans le pays : pas d'optimiseur d'images.
          <img src={person.photo_url} alt={t("identity.photoAlt", { name: person.display_name })} width={120} height={120} className="member-photo" />
        ) : (
          <div className="av av-xl" role="img" aria-label={t("identity.noPhoto")}>
            {initials(person.display_name)}
          </div>
        )}
        <p className="member-name">{person.display_name}</p>
        <p className="id text-title">{person.member_number}</p>
        <p>{t("identity.plan", { plan: person.plan_code, rate: formatRateBp(person.coverage_rate_bp) })}</p>
        <Pill tone={status.tone} icon={status.icon}>
          {t(`identity.status.${person.member_status}` as const)}
        </Pill>
      </section>
    </ScreenLayout>
  );
}
