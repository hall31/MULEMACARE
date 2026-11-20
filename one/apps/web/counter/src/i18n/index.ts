import fr from "./fr.json";

/** Textes du comptoir : une seule langue en v1 (français), jamais en dur dans les composants. */
export type MessageKey = keyof typeof fr;
export type MessageParams = Record<string, string | number>;

const messages: Record<MessageKey, string> = fr;

export function t(key: MessageKey, params?: MessageParams): string {
  const template = messages[key];
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const value = params[name];
    return value === undefined ? whole : String(value);
  });
}

export function hasMessage(key: string): key is MessageKey {
  return Object.prototype.hasOwnProperty.call(messages, key);
}

type PluralBase<K extends string> = K extends `${infer B}.one` ? (`${B}.other` extends MessageKey ? B : never) : never;
export type PluralKey = PluralBase<MessageKey>;

/** Pluriel français : 0 et 1 au singulier, au-delà au pluriel. */
export function tp(base: PluralKey, count: number, params: MessageParams = {}): string {
  const key = `${base}.${count <= 1 ? "one" : "other"}` as MessageKey;
  return t(key, { ...params, count });
}
