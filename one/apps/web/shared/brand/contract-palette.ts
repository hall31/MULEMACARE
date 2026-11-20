/**
 * Miroir des couleurs de `specs/design/mulemacare-tokens.css` (thèmes clair et sombre), pour le
 * calcul de contraste côté navigateur (aperçu en direct, garde de la marque) où le fichier CSS
 * n'est pas lisible. Ce n'est pas du code de composant : l'interface lit les variables CSS, jamais
 * ces valeurs. Tenu identique au contrat par `contract-palette.test.ts` (comme
 * `apps/api/branding/palette.py` côté serveur) : un jeton modifié sans régénération casse le test.
 * Fichier généré : `node scripts/gen-contract-palette.mjs`.
 */
import type { ContractPalette } from "./tokens";

export const CONTRACT_PALETTE: ContractPalette = {
  light: {
    "--bg": "#f6f9fb",
    "--surface": "#ffffff",
    "--sunk": "#eef3f6",
    "--line": "#e2e8f0",
    "--line-2": "#7a8a9e",
    "--fg": "#0f172a",
    "--fg-2": "#334155",
    "--fg-3": "#5b6b7f",
    "--accent": "#097268",
    "--accent-hover": "#075e56",
    "--accent-2": "#e3f3ef",
    "--accent-fg": "#ffffff",
    "--focus": "#097268",
    "--ok": "#166534",
    "--ok-bg": "#e6f4ea",
    "--warn": "#92400e",
    "--warn-bg": "#fef3c7",
    "--crit": "#b91c1c",
    "--crit-bg": "#fdecec",
    "--info": "#1e40af",
    "--info-bg": "#eaf0fd",
    "--brand-deep": "#064a43",
    "--brand-on-deep": "#ffffff",
    "--brand-on-deep-2": "#b9e4dc",
    "--brand-gold": "#d97706",
    "--brand-gold-soft": "#fef3c7",
    "--brand-gold-on-deep": "#e3a23b",
    "--brand-royal": "#1e40af",
  },
  dark: {
    "--bg": "#0d1417",
    "--surface": "#131c20",
    "--sunk": "#0a1013",
    "--line": "#22303a",
    "--line-2": "#5f7282",
    "--fg": "#e7eef1",
    "--fg-2": "#b3c1c8",
    "--fg-3": "#8d9da6",
    "--accent": "#4fc2b0",
    "--accent-hover": "#6fd3c3",
    "--accent-2": "#123430",
    "--accent-fg": "#04211d",
    "--focus": "#4fc2b0",
    "--ok": "#6fcf8e",
    "--ok-bg": "#12291b",
    "--warn": "#f0b45e",
    "--warn-bg": "#33250f",
    "--crit": "#f38e86",
    "--crit-bg": "#3a1816",
    "--info": "#9bb4f6",
    "--info-bg": "#172343",
    "--brand-deep": "#0b3f3a",
    "--brand-on-deep": "#ffffff",
    "--brand-on-deep-2": "#b9e4dc",
    "--brand-gold": "#d97706",
    "--brand-gold-soft": "#33250f",
    "--brand-gold-on-deep": "#e3a23b",
    "--brand-royal": "#1e40af",
  },
};
