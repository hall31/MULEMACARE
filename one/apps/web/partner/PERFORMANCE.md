# Budget de performance — espaces partenaires

Mesuré par `tests/e2e/perf.spec.ts` (`make perf`) sur le build de production, mode démonstration,
« 3G rapide » (1,6 Mb/s, RTT 150 ms, processeur ×4), même méthode que le comptoir.

| Mesure | Budget | Portefeuille assureur (02/10/2026, machine partagée chargée) |
|---|---|---|
| Premier affichage (titre, rendu serveur) | < 2,5 s | 1,5 s |
| LCP | relevé seulement | 6,3 s : en démonstration, les données attendent le démarrage du service worker MSW (absent en production) |
| CLS | < 0,1 | 0 |
| Polices | ≤ 110 Ko | 105 Ko (3 woff2 latins, texte seul préchargé) |
| Ressources hors origine | 0, sauf l'API de l'instance | 0 |

Le contrat (§11) ne fixe le LCP que pour le comptoir et le lien de paiement. À mesurer contre l'API réelle
quand elle sera déployée (le LCP sera alors le délai de `getInsurerPortfolio`).
