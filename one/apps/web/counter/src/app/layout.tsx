import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { describeFallback } from "@shared/brand";
import { BrandDevNotice, BrandProvider } from "@/brand/brand-context";
import { getBrand } from "@/brand/brand.server";
import { BrandStyle } from "@/brand/brand-style";
import { t } from "@/i18n";
import { lightToken } from "@/lib/tokens.server";
import { fontVariables } from "./fonts";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: t("app.name"),
  description: t("app.description"),
  applicationName: t("app.name"),
  appleWebApp: { capable: true, title: t("app.shortName"), statusBarStyle: "default" },
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: lightToken("surface"),
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // Marque de l'organisation lue AVANT le premier rendu : ses jetons sont dans le <head> servi.
  const brand = await getBrand();
  const devNotice = process.env.NODE_ENV === "production" ? null : describeFallback(brand);
  return (
    <html
      lang="fr"
      data-surface="counter"
      className={fontVariables}
      suppressHydrationWarning
      data-brand={brand.css ? "organisation" : "mulemacare"}
      data-organization={brand.identity?.slug}
    >
      <head>
        <BrandStyle brand={brand} />
      </head>
      <body>
        <BrandProvider identity={brand.identity}>
          {devNotice ? <BrandDevNotice message={devNotice} /> : null}
          <Providers>{children}</Providers>
        </BrandProvider>
      </body>
    </html>
  );
}
