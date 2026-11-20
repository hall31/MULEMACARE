import { headers } from "next/headers";
import type { ResolvedBrand } from "@shared/brand";

/**
 * Jetons de la marque, rendus dans le <head> par le serveur. Le CSS ne contient que des variables
 * de la liste fermée et des couleurs #rrggbb revérifiées (`brandStyleSheet`) : aucun texte de
 * l'organisation n'y entre. Rien à surcharger : rien n'est rendu (thème MulemaCare).
 */
export async function BrandStyle({ brand }: { brand: ResolvedBrand }) {
  // Nonce de la CSP de la requête (src/proxy.ts), lu AVANT tout retour : la mise en page reste
  // rendue à la requête, condition pour que Next.js pose le nonce sur ses scripts.
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  if (!brand.css) return null;
  return <style id="mc-brand" nonce={nonce} dangerouslySetInnerHTML={{ __html: brand.css }} />;
}
