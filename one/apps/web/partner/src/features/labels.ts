import { hasMessage, t, type MessageKey } from "@/i18n";

/**
 * Libellé d'une catégorie de garantie (clé `^[a-z_]{2,40}$` du contrat). Catégorie connue : texte
 * de fr.json ; inconnue (créée par l'organisation) : la clé rendue lisible, jamais un acte ni un motif.
 */
export function categoryLabel(key: string): string {
  const id = `categories.${key}`;
  if (hasMessage(id)) return t(id as MessageKey);
  const text = key.replace(/_/g, " ").trim();
  return text.charAt(0).toLocaleUpperCase("fr") + text.slice(1);
}
