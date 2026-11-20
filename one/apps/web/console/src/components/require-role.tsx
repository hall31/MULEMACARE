"use client";

import { LockIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useAccess } from "@/api/queries";
import type { Role } from "@/api/types";
import { t, type MessageKey } from "@/i18n";
import { LoadingRows } from "./states";

/** Garde d'interface : l'API refuse de toute façon (403), on l'explique avant d'appeler. */
export function RequireRole({ roles, children, message = "forbidden.gestionnaireOnly" }: { roles: Role[]; children: ReactNode; message?: MessageKey }) {
  const access = useAccess();
  if (!access.ready) return <LoadingRows rows={3} />;
  if (!roles.some((r) => access.has(r))) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-lg border border-line bg-surface p-5">
        <LockIcon className="size-4 text-fg-2" aria-hidden />
        <div>
          <p className="font-semibold">{t("states.forbiddenTitle")}</p>
          <p className="text-fg-2">{t(message)}</p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
