import type { ReactNode } from "react";

/**
 * Corps de l'écran (colonne de 640 px au-delà de 600 px, deux colonnes au-delà de 1024 px si
 * `wide`), puis barre d'actions collée en bas : action principale sous le pouce.
 */
export function ScreenLayout({ children, footer, wide = false }: { children: ReactNode; footer: ReactNode; wide?: boolean }) {
  return (
    <>
      <main className="c-body" data-wide={wide || undefined}>
        {children}
      </main>
      <footer data-testid="counter-footer" className="c-foot">
        <div className="c-foot-in" data-wide={wide || undefined}>
          {footer}
        </div>
      </footer>
    </>
  );
}
