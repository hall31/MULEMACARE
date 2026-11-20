# Budget de performance — espace adhérent et lien de paiement

Seuils du contrat de design (`docs/POLISH_CONTRACT.md` §11), mesurés par `e2e/perf.spec.ts` (même
méthode que `apps/web/counter/e2e/perf.spec.ts`) sur le build de production, API simulée.

| Mesure | Budget | Ma carte (`/`) | Lien de paiement (`/payer/…`) |
|---|---|---|---|
| LCP, 3G rapide, processeur ×4 | < 2,5 s | 0,8 s (`p.m-hint`) | 0,8 s (titre `h1`) |
| CLS | < 0,1 | 0,016 ; 0 avec une API lente de 1,5 s | 0,022 |
| JavaScript initial (référencé par le HTML, compressé) | ≤ 170 Ko (174 080 octets) | 168 Ko (172 111 octets) | 159 Ko (163 256 octets) |
| JavaScript des premières secondes (morceaux chargés à part, préchargement des onglets, encodeur du QR) | ≤ 200 Ko | 176 Ko (179 899 octets) | 159 Ko |
| Polices | ≤ 110 Ko | 105 Ko (3 fichiers, Plus Jakarta Sans seule préchargée) | idem |
| Ressources hors origine | 0 | 0 | 0 |

Mesuré le 02/10/2026, machine très chargée (charge moyenne 40 à 160) : majorants plausibles.

### Phase 2 : budget dépassé (176 539 octets), ramené sous le seuil sans le relever

La phase 2 avait porté le JavaScript initial de la carte à 176 539 octets (budget : 174 080). Le
budget n'est **pas** relevé : ce qui ne sert pas au premier affichage est sorti du JavaScript
initial et chargé juste après (`src/ui/deferred.ts`), soit 4 428 octets compressés en moins :

| Chargé à part | Pourquoi ce n'est pas du premier affichage |
|---|---|
| Calcul des notifications de la cloche (`notifications/UnreadProbe.tsx` → `useNotifications`, `derive.ts`) | La cloche est rendue tout de suite à sa taille ; seul le compteur (pastille absolue) arrive ensuite, sans saut. L'observateur ne relance pas une lecture en erreur (`retryOnMount: false`) : l'écran garde son erreur et « Réessayer ». |
| Bandeau de consentement à la mesure (`member/MeasureConsent.tsx`, texte détaillé compris) | Rien au rendu serveur (le choix est sur le téléphone) : il apparaissait déjà après l'hydratation. |
| Invitation à la découverte (`onboarding/TourInvite.tsx`) | Idem : attend la lecture du téléphone. |
| Écran « Présenter ma carte » (`card/PresentCard.tsx`) | Ouvert par un geste ; préchargé dès que la carte est arrivée, donc en cache du service worker avant une coupure au comptoir. Le plein écran est demandé dans le geste (`card/fullscreen.ts`, resté dans la page). |
| Client de mesure produit (`lib/telemetry.ts`, appelé via `lib/track.ts`) | Préchargé après le premier affichage ; s'il manque (coupure), les événements attendent en mémoire (20 au plus) et partent au retour du réseau. |

Pourquoi pas `React.lazy` ni `next/dynamic` : `next/dynamic` ajoute son propre code au JavaScript
initial (le gain disparaît), et un `React.lazy` dont le morceau n'est pas encore arrivé au moment
d'une coupure rejette et fait tomber l'écran (constaté dans `e2e/a11y.spec.ts`, hors ligne). Le
chargeur maison ne lève jamais : rien n'est affiché et un nouvel essai part au retour du réseau.

- **Marge encore faible sur la carte** (172 111 octets pour 174 080) : tout nouvel import dans
  l'écran d'accueil doit être chargé à part (`deferred`, comme l'encodeur du QR,
  `src/card/QrCode.tsx`). Prochain levier identifié si la marge est consommée : le fichier de
  traduction est entier dans le JavaScript initial (6,6 Ko compressés) alors que les textes de la
  découverte, des notifications, du paiement public et de la mesure (environ 40 %) ne servent pas
  à la carte ; les découper par écran rendrait environ 2,5 Ko.
- **Place réservée** : le squelette de la carte a la même structure et la même hauteur que la
  carte (vérifié dans `e2e/states.spec.ts`), et le plafond a sa place pendant le chargement.
- Mêmes limites que le comptoir : bridage CDP (pas la simulation Lighthouse), un seul passage et
  pas un p75 terrain, réponses d'API non bridées, INP non mesuré.
