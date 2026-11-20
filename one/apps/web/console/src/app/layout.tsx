import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { describeFallback } from "@shared/brand";
import { BrandDevNotice, BrandProvider } from "@/brand/brand-context";
import { getBrand } from "@/brand/brand.server";
import { BrandStyle } from "@/brand/brand-style";
import { AppShell } from "@/components/app-shell";
import { Providers } from "@/components/providers";
import { t } from "@/i18n";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const brand = await getBrand();
  return {
    title: brand.identity ? t("app.brandedTitle", { name: brand.identity.displayName }) : t("app.title"),
    description: t("app.description"),
    robots: { index: false, follow: false },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // Marque de l'organisation lue AVANT le premier rendu : ses jetons sont dans le <head> servi.
  const brand = await getBrand();
  const devNotice = process.env.NODE_ENV === "production" ? null : describeFallback(brand);
  return (
    <html lang="fr" suppressHydrationWarning data-brand={brand.css ? "organisation" : "mulemacare"} data-organization={brand.identity?.slug}>
      <head>
        <BrandStyle brand={brand} />
      </head>
      <body>
        <BrandProvider identity={brand.identity}>
          {devNotice ? <BrandDevNotice message={devNotice} /> : null}
          <Providers>
            <AppShell>{children}</AppShell>
          </Providers>
        </BrandProvider>
      </body>
    </html>
  );
}
