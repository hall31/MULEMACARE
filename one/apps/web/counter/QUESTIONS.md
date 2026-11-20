# Lot L7 — questions ouvertes et points d'intégration

Chaque question a un **défaut appliqué** ; aucune règle métier n'a été devinée au-delà.
Aucun contrat modifié, aucune demande de changement déposée.

## Questions (défaut appliqué)

**Q-L7-01 — Identification sans réseau.** Les trois facteurs (QR, photo, code SMS) se vérifient
côté serveur ; le contrat n'expose ni liste d'adhérents à mettre en cache, ni clé pour vérifier un
QR hors ligne, ni photo hors ligne. *Défaut :* l'identification exige le réseau ; l'accord
provisoire (R13) couvre la coupure **après** identification vérifiée (cas testé). Bandeau dédié si
le réseau manque dès la carte. Une identification hors ligne demanderait une CR (QR signé +
cache des droits) et une décision sur le facteur SMS.

**Q-L7-02 — Au-dessus du seuil, réseau coupé.** Le prototype dit « le dossier partira dès le retour
du réseau ». *Défaut :* aucune mise en file automatique (l'identification côté serveur peut avoir
expiré) ; l'écran explique et le bouton « Réessayer la demande » rejoue la même clé
d'idempotence au retour du réseau (testé).

**Q-L7-03 — Format de signature à confirmer par L5.** *Défaut :* ES256 (ECDSA P-256, SHA-256,
WebCrypto), clé privée non exportable, clé publique en JWK canonique via `registerCounterDevice`.
`signed_payload` = base64url du JSON canonique (clés triées, sans espace, UTF-8) contenant
`v, offline_ref, device_id, identification_id, member_number, beneficiary_id, service_date, items,
total_xof, covered_xof, currency, issued_at, expires_at, rules` ; `signature` = base64url des 64
octets r‖s calculés sur ces octets UTF-8. L5 doit vérifier la signature **et** que les champs en
clair égalent ceux du contenu signé.

**Q-L7-04 — `beneficiary_id` de l'accord hors ligne.** `Beneficiary` n'expose que `person_id`.
*Défaut :* `beneficiary_id = beneficiary.person_id`.

**Q-L7-05 — Arrondi de la part mutuelle hors ligne.** *Défaut :* arrondi au franc le plus proche,
demi vers le haut, en entiers (`(total × taux_bp + 5000) div 10000`), comme le prototype. En ligne,
le comptoir affiche toujours les montants du moteur de règles.

**Q-L7-06 — Accord provisoire synchronisé après 2 h.** *Défaut :* le comptoir envoie tout ce qui
est en attente, même expiré ; le serveur tranche (OFF-01). Durée d'un accord provisoire :
`validity_minutes` de la politique, plafonnée à 120 min côté comptoir (`MAX_VALIDITY_MINUTES`) même
si la politique reçue annonce davantage. Âge maximal de la politique hors ligne en cache : **72 h**
(`MAX_POLICY_AGE_HOURS`, `src/offline/policy.ts`), mesuré depuis `fetchedAt` (réception sur
l'appareil). Au-delà, ou si la date de réception manque, est illisible ou se trouve dans le futur
(horloge reculée), aucun accord provisoire (`stale_policy`) et le bandeau hors ligne l'annonce. 72 h
couvrent une coupure de week-end prolongé ; la politique est rafraîchie à chaque passage en ligne.

**Q-L7-07 — Fraude hors ligne.** R-12 exige un score < 0,20, inconnu sur l'appareil. *Défaut :*
non évalué localement, revérifié à la synchronisation par le serveur.

**Q-L7-08 — Détection de la coupure.** *Défaut :* provisoire seulement si aucune réponse n'a pu
partir (`navigator.onLine` faux ou échec de connexion). Un délai dépassé (12 s) n'ouvre **pas** le
provisoire (la demande a pu être traitée) : message « réessayez », même clé d'idempotence.

**Q-L7-09 — Fournisseur d'identité.** *Défaut :* interface `TokenProvider` + implémentation de test
(`NEXT_PUBLIC_MULEMA_AUTH_MODE=test`, jeton factice) ; sans fournisseur, l'API répond AUTH-01 et le
comptoir l'affiche. Pas d'écran de connexion (hors des cinq écrans).

**Q-L7-10 — Accords rejetés à la synchronisation.** Ils restent sur l'appareil et un bandeau
d'alerte les compte (code OFF-xx) ; les confirmés sont effacés au « Patient suivant ». Qui
les traite côté mutuelle, et quand l'appareil peut-il les oublier ?

## À intégrer hors du périmètre L7 (fichiers partagés non touchés)

1. **Makefile racine** : remplacer la cible `a11y` par
   `$(MAKE) -C apps/web/counter a11y` (et, si voulu, une cible `e2e-counter` →
   `$(MAKE) -C apps/web/counter e2e`). `make test-web` exécute déjà `vitest run` du comptoir.
2. **Lockfile racine** : le comptoir a son `pnpm-lock.yaml` local (installation
   `--ignore-workspace`, pour ne pas croiser L6). À la fusion, le supprimer et faire un
   `pnpm install` à la racine. Attention : une commande `pnpm run` lancée dans le comptoir a déclenché
   pendant le lot une installation de l'espace de travail qui a créé `pnpm-lock.yaml` et
   `node_modules/` à la racine `one/` ; le `pnpm-workspace.yaml` racine, modifié de la même façon,
   a été restauré à l'identique. Le lockfile racine (qui couvre console et comptoir) est laissé
   en place : à valider ou à régénérer par l'intégrateur.
3. **Liste blanche réseau (L9)** : le comptoir n'appelle que son propre origine (`/api/*`, relayé
   vers `MULEMA_API_URL`) et l'hôte des photos signées (`photo_url`) ; polices auto-hébergées.
4. **Contrat (pour L0, sans CR bloquante)** : `RuleCodeValue` n'a pas d'exemple ; les réponses
   statiques de Prism (`make mock-api`) violent donc son propre motif (`"string"`). Ajouter
   `examples: [R-12]` rendrait le mock conforme.

## Phase 2, voie A — aide de première utilisation, hors ligne, mesure

**Q-P2A-C1 — Aide de première utilisation.** *Défaut :* une bulle sobre par écran (ton info, sans
animation, sans voile, sans capture du focus), au-dessus de l'écran ; « Compris » la retire pour
cet écran, « Ne plus afficher l'aide » pour tous ; le bouton « Aide » de la barre du haut les
rétablit toutes. Mémorisée sur l'appareil (`mulema.comptoir.aide` : écrans vus et interrupteur,
aucune donnée de patient). Un comptoir partagé entre plusieurs agents garde un seul réglage : à
valider avec les cliniques.

**Q-P2A-C2 — Bandeau hors ligne.** *Défaut :* la phrase existante, puis « Possible : » et
« Impossible sans réseau : » ligne par ligne, selon l'étape et la politique hors ligne
(`src/counter/offline-capabilities.ts`, mêmes règles que `src/offline/policy.ts`).

**Q-P2A-C3 — Mesure produit (CR-P2-01).** *Défaut :* `counter_decision_shown` (variante
`accordee`, `revue` ou `refusee`, durée = scan ou saisie du numéro → écran de décision, objectif
< 10 s ; un accord provisoire compte comme `accordee`, un refus de provisoire n'est pas une
décision), `offline_banner_seen` (envoyé au retour du réseau), `onboarding_started`,
`onboarding_step` (« Compris » sur l'écran n), `onboarding_completed` (cinq écrans compris).
Coupée par `NEXT_PUBLIC_MULEMA_TELEMETRY=off` ou `mulema.comptoir.mesure = off` (pas d'interrupteur
à l'écran : réglage de l'appareil par la mutuelle).
