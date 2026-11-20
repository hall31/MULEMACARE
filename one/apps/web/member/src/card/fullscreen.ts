/**
 * Plein écran demandé dans le geste de l'adhérent (obligatoire pour l'API Fullscreen). À part de
 * `PresentCard.tsx` : le bouton l'appelle tout de suite, l'écran de présentation est chargé à part.
 */
export function requestPresentFullscreen(): void {
  const root = document.documentElement;
  if (document.fullscreenElement || typeof root.requestFullscreen !== "function") return;
  root.requestFullscreen({ navigationUI: "hide" }).catch(() => undefined);
}
