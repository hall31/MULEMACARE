import type { ResolvedBrand } from "@shared/brand";

/**
 * Jetons de la marque, rendus dans le <head> par le serveur. Le CSS ne contient que des variables
 * de la liste fermée et des couleurs #rrggbb revérifiées (`brandStyleSheet`) : aucun texte de
 * l'organisation n'y entre. Rien à surcharger : rien n'est rendu (thème MulemaCare).
 */
export function BrandStyle({ brand }: { brand: ResolvedBrand }) {
  if (!brand.css) return null;
  return <style id="mc-brand" dangerouslySetInnerHTML={{ __html: brand.css }} />;
}
