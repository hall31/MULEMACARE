import type { ReactNode } from "react";
import { MemberShell } from "@/member/MemberShell";

/** Écrans authentifiés de l'adhérent (rôle `adherent`, contrat tiré du jeton). */
export default function EspaceLayout({ children }: { children: ReactNode }) {
  return <MemberShell>{children}</MemberShell>;
}
