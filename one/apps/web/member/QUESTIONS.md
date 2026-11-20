# Espace adhérent (Phase 1, voie B) — questions ouvertes et points d'intégration

Chaque question a un **défaut appliqué** ; aucune règle métier n'a été devinée au-delà. Les
questions du contrat restent dans `specs/QUESTIONS.md` (Q-P1-01 à 05) ; les manques du contrat
sont dans `specs/CHANGE-REQUESTS.md` (CR-P1-02).

## Questions (défaut appliqué)

**Q-P1W-01 — Marge d'affichage du QR (Q-P1-04).** Le QR est redemandé à l'échéance annoncée
(`qr_refresh_at − qr_generated_at`, appliquée à l'heure de réception : une horloge de téléphone
fausse ne change rien). Pendant la requête, l'ancien QR reste affiché au plus **10 s**
(`QR_GRACE_MS`, `src/card/qr-schedule.ts`), puis il est remplacé par « QR expiré ». Cette marge
repose sur la fenêtre de tolérance du serveur (une fenêtre de 30 s, Q-L4-05). Si la tolérance
disparaît, passer `QR_GRACE_MS` à 0 et redemander le QR quelques secondes avant l'échéance.
Plafond : jamais un QR affiché plus de 60 s, quoi que le serveur annonce.

**Q-P1W-02 — Carte bloquée (Q-P1-04).** *Défaut :* le QR reste visible (comme l'API le sert),
mais « Présenter ma carte » est désactivé et un message ID-04 dit jusqu'à quelle heure.

**Q-P1W-03 — Hors ligne.** *Défaut :* la dernière carte lue est gardée dans le stockage local du
téléphone **sans son QR** ni ses dates (`src/card/last-card.ts`), une seule carte, pour la personne
demandée. Elle n'est montrée que sur une **erreur réseau** (hors ligne `E-NET-01`, serveur
injoignable `E-NET-02`, délai `E-NET-03`) : jamais sur une réponse de l'API, quelle qu'elle soit
(`src/card/source.ts`). L'espace affiche alors cette carte, la date de lecture, « QR expiré », le
code réseau et le numéro de carte à dicter au comptoir (le comptoir sait saisir un numéro).
Effacée sur refus d'accès (Q-P1W-12), à la déconnexion (Q-P1W-13) et au-delà de 24 h (Q-P1W-11).

**Q-P1W-04 — Équivalent en euros sur le lien de paiement.** Le contrat ne donne que le montant en
FCFA, ni devise ni pays du payeur. *Défaut :* montant en FCFA en héros (devise locale du
contrat) et « Environ 41,92 € · parité fixe 1 € = 655,957 FCFA » pour tous (parité légale du franc
CFA, calcul entier au centime, `src/lib/format.ts`). La planche montrait l'euro en héros ; il
faudrait la devise et le montant débité côté canal pour l'afficher ainsi (CR-P1-02).

**Q-P1W-05 — Moyens de paiement.** La tâche cite Wave, Orange Money et la carte bancaire ;
`PaymentChannel` ne contient pas de carte. *Défaut :* la page affiche exactement les `channels`
renvoyés par `getPublicPaymentLink` (le premier présélectionné). Carte bancaire : CR-P1-02.

**Q-P1W-06 — Payeur sans nouvelle après « en attente ».** Après `startCheckout` → `en_attente`
sans `redirect_url`, aucune opération publique ne permet au payeur de vérifier la confirmation.
*Défaut :* message « validez dans votre application, vous pouvez fermer cette page ».

**Q-P1W-07 — Fournisseur d'identité.** *Défaut :* interface `TokenProvider` + implémentation de
test (`NEXT_PUBLIC_MULEMA_AUTH_MODE=test`), comme le comptoir ; sans fournisseur, l'API répond
AUTH-01 et l'espace l'affiche avec son code. Pas d'écran de connexion.

**Q-P1W-08 — Navigation.** La planche a quatre onglets (Carte, Soins, Paiements, Aide) et une
cloche de notifications. *Défaut :* Carte, Soins, Cotisations, Famille ; la cloche existe depuis la
Phase 2 (notifications dérivées, Q-P2A-02) ; l'aide passe par la découverte (Q-P2A-01).

**Q-P1W-09 — Libellés à valider.** « Virement de la mutuelle » / « Paiement reçu » pour les
étapes `virement` et `recu` : dans le tiers payant, la mutuelle paie la clinique (Q-P1-03) ; le
libellé de la planche (« Virement Wave… sur votre compte ») décrit un remboursement à l'adhérent
qui n'existe pas encore. `plan_code` est affiché tel quel (« Formule FAMILLE-OR ») faute de nom
commercial dans `MyCard` (CR-P1-02).

**Q-P1W-10 — Luminosité.** Aucune API web ne règle la luminosité. *Défaut :* « Présenter ma
carte » ouvre un plein écran blanc (Fullscreen API), garde l'écran allumé (Wake Lock) et invite
l'adhérent à monter la luminosité.

**Q-P1W-11 — Âge maximal de la carte enregistrée.** *Défaut : 24 heures*
(`MAX_SAVED_CARD_AGE_MS`, `src/card/last-card.ts`). Au-delà, les droits ont pu changer (carence,
suspension, révocation) : la carte n'est plus affichée, elle est effacée, et l'écran dit « Carte
enregistrée trop ancienne : elle n'est plus affichée » avec la date de lecture et le code réseau.
Une date de lecture dans le futur (horloge du téléphone reculée de plus de 5 min) compte comme
trop ancienne. À valider par la mutuelle : une coupure de plus d'une journée en zone rurale
justifierait-elle 48 h ou 72 h ? Le comptoir, lui, exige le réseau pour identifier (Q-L7-01).

**Q-P1W-12 — Refus d'accès.** *Défaut :* toute réponse 401, 403 ou 404 d'une opération
`/v1/me/*`, et tout code `AUTH-01`, `AUTH-02` ou `NOT-01`, efface la carte enregistrée avant que
l'erreur ne remonte (`onAccessDenied`, `src/api/client.ts`) ; l'écran « Ma carte » cache alors
aussi la carte en direct gardée en mémoire et affiche l'erreur avec son code, et toutes les
données gardées en mémoire (dernier soin, cotisations…) sont oubliées puis redemandées
(`src/lib/query-client.ts`) : aucun écran ne garde une donnée d'avant le refus. Effet de bord
assumé : un 404 sur le suivi d'un dossier inconnu (adresse mal tapée) efface aussi la carte
enregistrée, qui revient à la lecture suivante en ligne. Une panne du serveur (`SYS-01`, 5xx)
n'efface rien et ne montre pas non plus la carte enregistrée : l'erreur et « Réessayer ».

**Q-P1W-13 — Déconnexion.** *Défaut :* « Se déconnecter » dans la barre du haut mène à
`/deconnexion`, hors de la coquille de l'espace, qui efface la mémoire des requêtes (requêtes en
cours annulées : une réponse tardive n'est pas enregistrée), la carte enregistrée et toute clé
`mulema.adherent.*`, puis tous les caches du service worker (`src/lib/device-data.ts`). Sans
fournisseur d'identité (Q-P1W-07), la session n'est pas fermée côté serveur : à brancher avec le
fournisseur (fin de session, révocation du jeton) ; « Revenir à mon espace » recharge l'espace avec
le jeton courant.

## Stockage sur le téléphone (inventaire)

Ce que l'espace adhérent garde sur le téléphone, et rien d'autre (vérifié par
`src/lib/device-data.test.ts`, `e2e/session.spec.ts`, `e2e/pwa.spec.ts`) :

| Où | Clé | Contenu | Durée | Effacé |
|---|---|---|---|---|
| `localStorage` | `mulema.adherent.derniere-carte` | Dernière carte lue **sans QR ni dates du QR** : identifiants de carte et de personne, prénom, nom, lien de parenté, numéro d'adhérent, formule, taux de couverture, nombre de bénéficiaires, statut et blocage de la carte, droits (statut, fin de carence, plafond familial, consommé, restant), date de lecture. Aucune donnée médicale (le contrat n'en renvoie pas). | 24 h | refus d'accès, déconnexion, au-delà de 24 h |
| `localStorage` | `mulema.adherent.decouverte` | État du parcours de découverte (`termine` ou `passe`) et sa date. Aucune donnée de l'adhérent. | jusqu'à la déconnexion | déconnexion, « Revoir la découverte » ne l'efface pas (il rejoue) |
| `localStorage` | `mulema.adherent.notifications` | Préférences des notifications (catégories, délai d'alerte) et **empreintes** seulement (version 2) : dossiers connus, état de chaque dossier (dossier + statut) à la dernière lecture, notifications lues ; 50 au plus. Aucun identifiant de dossier, de cotisation ou de personne, aucun statut, ni nom, ni montant, ni établissement en clair. Un état version 1 (en clair) est réécrit à l'ouverture. | jusqu'à la déconnexion | déconnexion |
| `localStorage` | `mulema.adherent.mesure` | Ancien interrupteur (`off`), relu comme un refus puis repris dans la clé ci-dessous. | jusqu'à la déconnexion | déconnexion |
| `localStorage` | `mulema.mesure.adherent` | Choix de mesure d'usage pseudonyme : `{ v: 1, choice: "granted" \| "refused" }`, rien d'autre. Sans cette clé, la mesure est désactivée. **Hors du préfixe** : un refus survit à la déconnexion. | jusqu'à un nouveau choix | jamais par la déconnexion (choix réversible dans Mes notifications › Préférences) |
| Cache Storage (service worker) | `adherent-v1` | Coquille : pages `/`, `/soins`, `/cotisations`, `/famille`, pages visitées (chemin seul, dont l'identifiant d'un dossier ou d'un bénéficiaire dans l'adresse ; le HTML ne contient aucune donnée de l'adhérent, chargée par l'API), scripts, polices, icônes, manifeste. **Jamais** une réponse d'API (`/api/*`) ni la page de paiement (`/payer/*`). | nouvelle version du service worker | déconnexion |
| Mémoire (TanStack Query) | — | Réponses de l'API de la session en cours. Non persistant. | onglet | déconnexion, fermeture |

Aucun cookie posé par l'espace, ni `sessionStorage`, ni IndexedDB. Le jeton d'accès n'est pas
stocké par l'espace (fourni par `TokenProvider`, Q-P1W-07) : le fournisseur d'identité retenu
devra respecter la même règle, ou ajouter sa clé à `PERSISTED_KEYS` (`src/lib/device-data.ts`).

## À intégrer hors du périmètre (fichiers partagés)

1. **Base du lien de paiement** : l'API construit `{MULEMA_PAYMENT_PUBLIC_BASE_URL}/{jeton}`
   (`apps/api/payments/service.py`) ; la page publique de cet espace est servie sous `/payer/{jeton}`.
   Régler `MULEMA_PAYMENT_PUBLIC_BASE_URL=https://<hôte de l'espace>/payer`.
2. **Lockfile racine** : comme le comptoir, l'espace a son `pnpm-lock.yaml` local (installation
   `--ignore-workspace`). `pnpm-workspace.yaml` couvre déjà `apps/web/*` ; le lockfile racine n'a
   pas été régénéré (il couvre console et comptoir) : à faire par l'intégrateur
   (`pnpm install` à la racine), sinon une installation racine `--frozen-lockfile` échouera.
3. **Makefile racine** : `make a11y` audite aussi l'espace ; `make test-web` le couvre via
   `pnpm -r`.
4. **Liste blanche réseau (L9)** : l'espace n'appelle que sa propre origine (`/api/*`, relayé vers
   `MULEMA_API_URL`) ; polices auto-hébergées. Le lien `https://wa.me/?text=…` est une navigation
   ouverte par l'adhérent, pas un appel de l'application.

## Phase 2, voie A — découverte, notifications, hors ligne, mesure

**Q-P2A-01 — Découverte sans formation.** *Défaut :* invitation non bloquante sous « Présenter ma
carte » à la première visite (l'adhérent peut être au comptoir), trois étapes sur `/decouverte`
sans barre d'onglets (couverture depuis `getMyCard`, présenter sa carte, suivre un remboursement),
« Passer » à tout moment, rejouable par « Revoir la découverte de l'espace ». L'exemple chiffré
(10 000 FCFA) applique le taux de la carte à l'entier inférieur (Q-L2-03) : c'est un exemple, pas
une décision. Objectif « comprendre sa couverture en moins de 2 minutes » : budget de lecture
testé (≤ 1,5 min à 100 mots/min) et question de vérification ; mesure réelle avec 5 adhérents :
`docs/USABILITY_PROTOCOL.md` (tâche T1). Le détail par type de soin manque au contrat (CR-P2A-01).

**Q-P2A-02 — Notifications dérivées.** *Défaut :* aucun endpoint, aucun envoi (SMS et WhatsApp
hors périmètre) : échéance à payer dans le délai choisi (3, 7 ou 14 jours, 7 par défaut, choix de
l'adhérent et non règle métier) ou dépassée, dossier passé à un autre statut depuis la dernière
lecture (référence posée en silence à la première ouverture), carte bloquée, couverture terminée ou
qui se termine. « Carte expirée » = fin de couverture du bénéficiaire faute de date d'expiration
de carte (CR-P2A-02). Le statut des dossiers à la dernière lecture est gardé sur le téléphone
(CR-P2A-03 le rendrait inutile).

**Q-P2A-03 — Hors ligne.** *Défaut :* bandeau persistant qui dit ce qui reste possible (carte
enregistrée, numéro à dicter, pages déjà ouvertes) et ce qui ne l'est pas (QR valable, paiement,
invitation, nouvelles étapes) ; « Inviter un proche à payer » désactivé avec son explication ;
notifications calculées sur les données déjà chargées.

**Q-P2A-04 — Mesure produit (CR-P2-01).** *Défaut :* `src/lib/telemetry.ts`, liste blanche du
contrat (testée contre `specs/openapi.yaml`) : `onboarding_started`, `onboarding_step` (étape),
`onboarding_completed` (durée), `card_presented` (`en_ligne`), `payment_link_created`,
`notification_opened` (`in_app`), `offline_banner_seen`, `claim_tracking_viewed`. Identifiant de
session aléatoire en mémoire seulement (jamais stocké), envoi `keepalive` sans attendre la réponse,
silencieux hors ligne (20 événements gardés en mémoire, envoyés au retour du réseau), coupé par
`NEXT_PUBLIC_MULEMA_TELEMETRY=off` ou par l'interrupteur des préférences. `card_presented`
`hors_ligne` n'est jamais émis : hors ligne, « Présenter ma carte » est désactivé (QR non valable).
