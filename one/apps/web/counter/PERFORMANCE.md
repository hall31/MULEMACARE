# Budget de performance — comptoir PWA

Seuils du contrat de design (`docs/POLISH_CONTRACT.md` §11) et du PRD (objectif 1 : décision au
comptoir en moins de 10 s après le scan). Mesurés à chaque `make e2e` par `e2e/perf.spec.ts`, sur
le build de production (`next build && next start`), API simulée (`e2e/mock-api.ts`).

| Mesure | Budget | Mesuré le 01/10/2026 | Où |
|---|---|---|---|
| Interaction (clic → titre de l'écran suivant) | < 1 s par écran | scan 526 ms (dont lecture du QR toutes les 300 ms), identité 94 ms, code 92 ms, actes 178 ms | `perf.spec.ts` « parcours chronométré » |
| Parcours carte scannée → accord affiché | < 10 s | 1,1 à 1,3 s | idem |
| LCP, 3G rapide, processeur ×4 | < 2,5 s | 1,0 à 1,2 s (élément : titre `h1` de l'écran Carte) | `perf.spec.ts` « premier affichage » |
| CLS | < 0,1 | 0 | idem |
| JavaScript initial (corps compressés reçus) | ≤ 170 Ko | 155 Ko (158 440 octets) | idem |
| Polices | ≤ 110 Ko | 105 Ko (3 fichiers : 27 + 32 + 48 Ko), Plus Jakarta Sans seule préchargée | idem |
| Ressources hors origine | 0 | 0 (aucun CDN, aucune police Google) | idem |

## Profil réseau

Profil Lighthouse « slow 4G », appelé « 3G rapide » dans le contrat : 1,6 Mb/s descendant,
750 kb/s montant, RTT 150 ms (`Network.emulateNetworkConditions`), processeur ralenti ×4
(`Emulation.setCPUThrottlingRate`), cache désactivé, viewport 360 × 780 (Android d'entrée de gamme).

## Limites de la mesure (à connaître avant de citer un chiffre)

- **Bridage appliqué par Chromium, pas simulé.** CDP ralentit chaque requête dans le navigateur ;
  Lighthouse, lui, simule le réseau (« lantern ») et reconstruit les délais TCP/TLS. Les deux ne
  donnent pas les mêmes chiffres. Pas de TLS ici (serveur local en HTTP).
- **Un seul passage, pas un 75ᵉ percentile.** Le contrat demande le p75 du terrain ; seul un suivi
  RUM (Web Vitals en production) le donnera. Le test est un garde-fou de régression.
- **API simulée dans le navigateur** : les réponses de l'API ne subissent pas le bridage. Le temps
  serveur réel du moteur de règles s'ajoute au parcours (budget API : voir le PRD).
- **Machine de mesure chargée** (charge moyenne > 150 au moment des mesures) : les chiffres sont
  des majorants plausibles, pas des moyennes.
- **INP** (< 200 ms) n'est pas mesuré : il demande des interactions réelles sur appareil ;
  l'interaction la plus lente du parcours (scan inclus) reste sous 1 s de bout en bout.
- **JavaScript** : la somme ne compte que ce que charge un navigateur moderne ; le polyfill
  `nomodule` de Next (environ 40 Ko compressés) est référencé dans le HTML mais jamais téléchargé.
- **Scan** : caméra et `BarcodeDetector` sont simulés (flux d'un canevas, QR fictif) ; le temps
  d'autofocus d'une vraie caméra n'est pas compté.
