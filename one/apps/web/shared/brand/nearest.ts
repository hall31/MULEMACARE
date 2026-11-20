/**
 * Couleur conforme la plus proche d'une couleur refusée (écran de réglage de la marque, BRD-01).
 *
 * On garde la teinte et la saturation perçues (OKLCH) et on déplace seulement la clarté, pas à pas,
 * dans les deux sens, jusqu'à la première couleur qui ne fait plus échouer aucune paire touchant le
 * jeton (mêmes règles que l'API). Une couleur hors du gamut sRGB perd de la saturation, jamais sa
 * teinte. Rien de trouvé (cas d'une couleur de statut à l'identique, par exemple) : null.
 */
import { hexToRgb, normalizeHex, rgbToHex, type Rgb } from "./contrast";
import { CONTRACT_PALETTE } from "./contract-palette";
import { themeProblems, type OverridableToken, type TokenOverrides } from "./policy";
import type { ContractPalette, ThemeName } from "./tokens";

interface Oklch {
  l: number;
  c: number;
  h: number;
}

const toLinear = (c: number) => {
  const v = c / 255;
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
};
const fromLinear = (v: number) => 255 * (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055);

function rgbToOklch({ r, g, b }: Rgb): Oklch {
  const [lr, lg, lb] = [toLinear(r), toLinear(g), toLinear(b)];
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  const L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
  const A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const B = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  return { l: L, c: Math.hypot(A, B), h: Math.atan2(B, A) };
}

/** Canaux linéaires (peuvent sortir de [0, 1] : hors gamut). */
function oklchToLinear({ l: L, c, h }: Oklch): [number, number, number] {
  const A = c * Math.cos(h);
  const B = c * Math.sin(h);
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3;
  const m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3;
  const s = (L - 0.0894841775 * A - 1.291485548 * B) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
}

const inGamut = (channels: number[]) => channels.every((v) => v >= -1e-4 && v <= 1 + 1e-4);

/** Couleur sRGB de clarté `l`, même teinte ; saturation réduite si nécessaire pour rester dans le gamut. */
function atLightness(base: Oklch, l: number): string {
  let low = 0;
  let high = base.c;
  if (!inGamut(oklchToLinear({ ...base, l }))) {
    for (let i = 0; i < 24; i += 1) {
      const mid = (low + high) / 2;
      if (inGamut(oklchToLinear({ ...base, l, c: mid }))) low = mid;
      else high = mid;
    }
  } else low = base.c;
  const [r, g, b] = oklchToLinear({ ...base, l, c: low });
  return rgbToHex({ r: fromLinear(Math.min(1, Math.max(0, r))), g: fromLinear(Math.min(1, Math.max(0, g))), b: fromLinear(Math.min(1, Math.max(0, b))) });
}

function passes(theme: ThemeName, token: OverridableToken, value: string, overrides: TokenOverrides, palette: ContractPalette): boolean {
  return !themeProblems(theme, { ...overrides, [token]: value }, palette).some((p) => p.token === token);
}

/**
 * Couleur la plus proche de `value` (même teinte) qui rend `token` conforme dans `theme`, compte tenu
 * des autres surcharges du thème ; la couleur elle-même si elle passe déjà ; null si rien ne passe.
 */
export function nearestCompliant(
  theme: ThemeName,
  token: OverridableToken,
  value: string,
  overrides: TokenOverrides = {},
  palette: ContractPalette = CONTRACT_PALETTE,
): string | null {
  const start = normalizeHex(value);
  if (!start) return null;
  if (passes(theme, token, start, overrides, palette)) return start;
  const base = rgbToOklch(hexToRgb(start));
  const step = 0.0025;
  for (let delta = step; delta <= 1; delta += step) {
    for (const l of [base.l - delta, base.l + delta]) {
      if (l < 0 || l > 1) continue;
      const candidate = atLightness(base, l);
      if (candidate !== start && passes(theme, token, candidate, overrides, palette)) return candidate;
    }
  }
  return null;
}
