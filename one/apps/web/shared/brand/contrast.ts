/**
 * Contraste WCAG 2.2 : luminance relative et rapport. Même formule que l'API
 * (`apps/api/branding/contrast.py`), qui refuse une marque sous le seuil (422 BRD-01) : le client
 * recalcule ici en défense en profondeur, et pour l'aperçu en direct de l'écran de réglage.
 */

/** Couleur `#rrggbb` (minuscules) : seule forme admise par le contrat (`HexColor`). */
export const HEX_COLOR = /^#[0-9a-f]{6}$/;

/** `#RRGGBB` ou `#rrggbb` → minuscules ; toute autre forme (nom, rgb(), CSS) → null. */
export function normalizeHex(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const lower = value.toLowerCase();
  return HEX_COLOR.test(lower) ? lower : null;
}

export interface Rgb {
  r: number;
  g: number;
  b: number;
}

/** Canaux 0 à 255 d'une couleur `#rrggbb`. */
export function hexToRgb(hex: string): Rgb {
  const value = normalizeHex(hex);
  if (!value) throw new Error(`couleur attendue au format #rrggbb : ${String(hex)}`);
  return {
    r: Number.parseInt(value.slice(1, 3), 16),
    g: Number.parseInt(value.slice(3, 5), 16),
    b: Number.parseInt(value.slice(5, 7), 16),
  };
}

/** Couleur `#rrggbb` à partir de canaux 0 à 255 (arrondis et bornés). */
export function rgbToHex({ r, g, b }: Rgb): string {
  const part = (c: number) => Math.min(255, Math.max(0, Math.round(c))).toString(16).padStart(2, "0");
  return `#${part(r)}${part(g)}${part(b)}`;
}

function linear(channel: number): number {
  const c = channel / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

/** Luminance relative (WCAG 2.x) d'une couleur `#rrggbb`. */
export function relativeLuminance(hex: string): number {
  const { r, g, b } = hexToRgb(hex);
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}

/** Rapport de contraste (1 à 21), indépendant de l'ordre. */
export function contrastRatio(a: string, b: string): number {
  const [high, low] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x) as [number, number];
  return (high + 0.05) / (low + 0.05);
}
