"use client";

import { useEffect } from "react";
import { useNotifications } from "./useNotifications";

/**
 * Compte des notifications non lues, remonté à la cloche ; ne rend rien (chargé à part). Monté
 * après l'écran : il observe les lectures sans relancer celles en erreur (l'écran garde son erreur
 * et son bouton « Réessayer »).
 */
export default function UnreadProbe({ onChange }: { onChange: (unread: number) => void }) {
  const { unread } = useNotifications({ retryOnMount: false });
  useEffect(() => onChange(unread), [unread, onChange]);
  return null;
}
