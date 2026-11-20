import fr from "./fr.json" with { type: "json" };

/**
 * Traductions de la console. Tous les textes affichés viennent de `fr.json` :
 * aucun texte en dur dans les composants (AGENTS.md, Conventions).
 */
export const messages = fr;

type Messages = typeof fr;

/** Chemins pointés vers une feuille texte : "claims.title", "decision.confirm.accorder"… */
type Leaves<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>;
}[keyof T & string];

export type MessageKey = Leaves<Messages>;
export type MessageVars = Record<string, string | number>;

function lookup(key: string): string | undefined {
  let node: unknown = fr;
  for (const part of key.split(".")) {
    if (typeof node !== "object" || node === null || !(part in node)) return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : undefined;
}

/** Texte traduit ; les variables `{nom}` sont remplacées. Une clé absente est une erreur de code. */
export function t(key: MessageKey, vars?: MessageVars): string {
  const template = lookup(key);
  if (template === undefined) {
    throw new Error(`Clé de traduction absente : ${key}`);
  }
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

/** Pour les clés construites à partir d'une valeur d'énumération de l'API. */
export function tDynamic(prefix: string, value: string, vars?: MessageVars): string {
  return t(`${prefix}.${value}` as MessageKey, vars);
}
