"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAccess } from "@/api/queries";
import { Loading } from "@/components/states";
import { NAV } from "@/components/shell";

/** L'accueil ouvre l'espace du rôle connecté (assureur ou employeur). */
export function HomeRedirect() {
  const router = useRouter();
  const { roles, ready } = useAccess();
  useEffect(() => {
    if (!ready) return;
    const target = NAV.find((item) => item.roles.some((r) => roles.some((x) => x === r)));
    if (target) router.replace(target.href);
  }, [ready, roles, router]);
  return <Loading rows={3} />;
}
