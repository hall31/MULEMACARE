import localFont from "next/font/local";

/**
 * Polices du contrat (docs/POLISH_CONTRACT.md §4), auto-hébergées : copies des woff2 variables
 * latins de specs/design/direction/fonts (OFL-1.1, licences à côté des fichiers). next/font/local
 * les sert depuis /_next/static/media (empreinte dans le nom, mises en cache par le service
 * worker) et génère une police de repli aux métriques ajustées. Aucun CDN, aucun appel à Google.
 * Seule la police de texte est préchargée.
 */
export const fontBody = localFont({
  src: "./fonts/plus-jakarta-sans-latin-wght-normal.woff2",
  weight: "200 800",
  style: "normal",
  display: "swap",
  preload: true,
  variable: "--mc-font-body",
});

export const fontDisplay = localFont({
  src: "./fonts/outfit-latin-wght-normal.woff2",
  weight: "100 900",
  style: "normal",
  display: "swap",
  preload: false,
  variable: "--mc-font-display",
});

export const fontNum = localFont({
  src: "./fonts/inter-latin-wght-normal.woff2",
  weight: "100 900",
  style: "normal",
  display: "swap",
  preload: false,
  variable: "--mc-font-num",
});

export const fontVariables = `${fontBody.variable} ${fontDisplay.variable} ${fontNum.variable}`;
