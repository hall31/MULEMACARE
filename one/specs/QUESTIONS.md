# Questions ouvertes — lot L0

Questions métier ou d'architecture soulevées en écrivant les contrats. Chacune a un **défaut** appliqué dans les contrats ; rien n'a été deviné au-delà. Compléments de la section 10 du PRD (non modifiée par L0).

## Seuils et règles

**Q-L0-01 — Valeurs du prototype stockées en données.** R-12 (< 50 000 FCFA, score < 0,20), R-20 (2 h), R-01 (suspension à J+45), ID-03 (3 codes faux, 15 min), HL-01 (validité 2 h), carence 60 j (v2), plafond 3 000 000 FCFA, taux 80 %, cotisation 27 500 FCFA/mois. *Défaut :* valeurs du prototype dans `specs/seeds/demo.sql`, marquées (proto). À valider (PRD §10 Q3, Q4).

**Q-L0-02 — Bornes des seuils.** Le PRD dit « total < 50 000 » et « score < 0,20 ». *Défaut :* bornes **exclues** (`total_max_exclu_xof`, `score_fraude_max_exclu`) ; 50 000 FCFA exactement part en revue (R-20).

**Q-L0-03 — Seuil incohérent dans le prototype.** Le fil d'activité du prototype dit « routée vers le médecin-conseil (montant > 150 000) », alors que R-12/R-20 fixent 50 000. *Défaut :* 50 000 (PRD §5).

**Q-L0-04 — Seuil R-12 porté par la règle ou par le produit ?** L'écran Produits du prototype montre un « seuil d'accord automatique » par version de produit (40 000 / 50 000 / 60 000). *Défaut :* le seuil appartient à la version de la règle R-12 (PRD §5) ; pas de colonne de seuil dans `plan_versions`. Si le seuil doit varier par formule, une CR ajoutera un paramètre par produit dans R-12.

**Q-L0-05 — Règle d'alerte fraude (score > 0,6, « F-03 » dans le prototype).** Absente du PRD §5, citée en §10 Q3. *Défaut :* pas de règle F-03 en données ; `claims.fraud_flagged` et `fraud_score` existent. Qui calcule le score (modèle, règles, fournisseur) et quel seuil ?

**Q-L0-06 — Durée de validité du code SMS et longueur.** Le prototype utilise 6 chiffres ; aucune durée n'est donnée. *Défaut :* 6 chiffres dans l'API ; durée **non fixée** (à ajouter comme paramètre de ID-03 après décision).

**Q-L0-07 — Périmètre du plafond R-09.** Année civile ou année d'adhésion ? Famille entière ? *Défaut :* `{"perimetre": "famille"}` ; la période reste à trancher avant L2.

## Adhésions et cotisations

**Q-L0-08 — Statut « résilié ».** Le PRD liste actif, carence, suspendu. *Défaut :* trois statuts seulement ; pas de résiliation en v1.

**Q-L0-09 — Changement de formule en cours d'année.** `members.plan_id` n'a pas d'historique ; un changement de formule rendrait une décision passée non rejouable. *Défaut :* changement de formule non géré en v1 ; si besoin, CR pour une table de périodes de formule.

**Q-L0-10 — Prélèvement employeur groupé.** Le prototype montre un virement employeur couvrant 212 adhérents. `payments.contribution_id` rattache un paiement à une seule cotisation. *Défaut :* un paiement = une cotisation ; le groupé demandera une table d'affectation (CR).

**Q-L0-11 — Compte comptable MTN MoMo.** Le plan de comptes initial (L3) a 5121 Wave et 5122 Orange Money, pas MTN. *Défaut :* pas de compte MTN tant que le plan n'est pas complété.

**Q-L0-12 — Qui peut décider une revue ?** Le prototype laisse le gestionnaire accorder/refuser ; le PRD §3 réserve la décision au médecin-conseil. *Défaut :* `decideClaim` réservé au médecin-conseil.

**Q-L0-13 — Codes de motif des décisions humaines.** `DecideClaimRequest.reason_code` est un code (pas de texte libre, pour qu'aucune donnée médicale n'entre en base). *Défaut :* format `^[A-Z]{1,4}-[0-9]{2}$`, liste des codes à définir (ex. « pièces manquantes », « acte non couvert »).

## Architecture et sécurité

**Q-L0-14 — Rôle applicatif (traité après revue du vérificateur).** `schema.sql` crée `mulema_app` (NOLOGIN, sans BYPASSRLS, propriétaire de rien) avec des privilèges minimaux : aucun UPDATE/DELETE/TRUNCATE sur les tables en ajout seul, DELETE seulement sur `idempotency_keys`, et RLS **forcée** sur toutes les tables. Les tests R7 et R10 tournent sous ce rôle. *Restent à trancher par l'exploitation :* (a) le rôle de connexion de l'API (LOGIN, membre de `mulema_app`, secret hors dépôt) ; (b) le rôle de migration doit avoir CREATEROLE (création de `mulema_app`) ; (c) avec la RLS forcée, le propriétaire y est soumis : les fonctions SECURITY DEFINER `resolve_organization_by_slug` et `resolve_payment_link` ne renvoient rien si le propriétaire n'a pas BYPASSRLS. *Défaut :* propriétaire dédié `mulema_owner` avec BYPASSRLS, jamais utilisé par l'API. Non testé en L0 (le serveur de test n'a qu'un superutilisateur) : à prouver en L4.

**Q-L0-15 — Webhook : organisation dans l'URL.** Un webhook n'a pas de jeton utilisateur. *Défaut :* `/v1/webhooks/{organization_slug}/payments/{channel}`, authentifié par signature ; seule exception à « l'organisation vient du jeton ».

**Q-L0-16 — Polices du prototype chargées depuis Google Fonts.** Contraire à la liste blanche réseau (R9). *Défaut :* les jetons ne citent que des noms de polices ; L6/L7 les auto-hébergent (licences OFL à vérifier) ou retombent sur les polices système.

**Q-L0-17 — Événements : un bus ou seulement l'outbox ?** *Défaut :* table `outbox_events` + consommateurs internes au monolithe ; pas de courtier de messages en v1.

**Q-L0-18 — Données de démonstration et règle « aucune donnée réelle ».** Le prototype nomme des personnes fictives et des établissements réalistes. *Défaut :* le jeu `demo.sql` ne contient aucune personne ni établissement, seulement du paramétrage.

**Q-L0-19 — Types de pièces d'un dossier.** `claim_documents.kind` ∈ facture, piece_clinique, justificatif_identite, autre ; seules des références HealthOS sont stockées. *Défaut :* liste provisoire, à valider avec le médecin-conseil.

**Q-L0-20 — Retour en revue.** Après `pieces_demandees`, seul le dépôt des pièces par la clinique (`submitClaimDocuments`) remet le dossier `en_revue` ; il est tracé comme décision humaine de la clinique. *Défaut :* pas d'opération distincte « remettre en revue » pour le médecin-conseil.

## Suivi de la revue du vérificateur (commit 6aa9ed3be)

Bloquants 1 à 3 et points non bloquants traités (rôle applicatif + RLS forcée, isolation générique par table, opérations OpenAPI par lot, événements conditionnels, migration 0001 figée avec empreinte, scan médical élargi, contre-passation miroir MCL04, état `soumise` des règles). Non fait : aucun point de la liste ; seules restent les décisions d'exploitation de Q-L0-14.

# Questions ouvertes — lot L2 (moteur de règles)

Défauts appliqués dans `apps/api/rules` ; chacun est testé et se change en données ou en une ligne.

**Q-L2-01 — « Cotisation à jour » (R-01).** *Défaut :* droits fermés dès que l'impayé atteint `suspension_apres_jours_impayes` (45 j), même si le statut n'a pas encore basculé en `suspendu` (L4). L'appelant fournit les jours d'impayé à la date du soin.

**Q-L2-02 — Adhérent au statut `carence`.** Avec `statuts_ouvrant_droits = ["actif"]`, il est refusé en **R-01**, pas en R-07. R-07 est calculé depuis `enrolled_on` + `waiting_period_days` de la version de produit en vigueur à la date du soin (pas `members.waiting_period_ends_on`) ; le soin du jour `enrolled_on + N` est couvert. *À confirmer :* quel code afficher à un adhérent en carence, et quelle version de produit fixe la carence (date du soin ou date d'adhésion).

**Q-L2-03 — Arrondi de la part couverte.** *Défaut :* entier inférieur, ligne par ligne (`claim_items.covered_xof`).

**Q-L2-04 — Garanties.** Acte dont la catégorie n'a pas de garantie dans la version : taux de la version. `coverages.annual_limit_xof` (plafond par garantie) n'est pas appliqué : absent du PRD §5.

**Q-L2-05 — Score de fraude absent.** *Défaut :* R-12 non remplie, revue (R-20).

**Q-L2-07 — Publication et version précédente (routes L2).** *Défaut :* `publishPlanVersion` / `publishRuleVersion` passent brouillon → soumise → en_vigueur (approbateur et instant renseignés) dans une transaction ; la version publiée **ouverte** qui commence avant la nouvelle date d'effet est close la veille (`valid_to`, seul changement que `freeze_published_version` permet), son état reste `en_vigueur`. Tout autre chevauchement : 409 RUL-02, rien n'est modifié. Republier une version publiée : 409 RUL-01. *À confirmer :* faut-il passer la version close à `cloturee`, et une publication rétroactive (date d'effet passée) doit-elle être refusée ?

**Q-L2-08 — Chevauchements hors versions et doublons.** *Défaut :* deux conventions d'un prestataire ou deux montants de barème d'un acte qui se chevauchent : 409 RUL-02 (le moteur refuserait un prix ambigu). Code de produit ou d'acte déjà pris : 409 VAL-01 (même choix que L1, voir CR-L1-01). Paramètres d'une version de règle de décision (R-01…R-20) : schéma fermé du moteur vérifié dès la création (422 VAL-01) ; ID-03 et HL-01 restent vérifiés à l'usage par L5.

**Q-L2-09 — Faits de `evaluateRules`.** *Défaut :* mêmes faits que L5 (statut à la fin du jour du soin, jours d'impayé, consommation de l'année civile du soin), lus via le dépôt L4 (`MemberRepository`) ; le bénéficiaire doit être le titulaire ou un ayant droit actif (sinon NOT-01). Rien n'est écrit. Les deux chemins (L2 simulation, L5 décision) rassemblent les faits séparément : un test de non-divergence ou un module de faits commun serait à décider.

**Q-L2-06 — Plafond R-09.** Compare la part couverte au reste du plafond familial. La consommation de la période est fournie par l'appelant (L5) : la période (année civile ou d'adhésion, Q-L0-07) reste à trancher.

## Lot L1 — noyau

**Q-L1-01 — Rôles : jeton ou base ?** Le contrat dit que le jeton « porte l'organisation et les rôles ». *Défaut :* le noyau prend du jeton le sujet et l'organisation seulement ; les rôles sont lus dans `user_roles`, seule source modifiable par l'admin (`replaceUserRoles`). Un rôle présent dans le jeton mais absent en base ne donne aucun droit.

**Q-L1-02 — Bornes `from`/`to` du journal d'audit.** *Défaut :* jours civils du fuseau de l'organisation, bornes incluses. Abidjan et Dakar sont à UTC+0 sans heure d'été : aucun écart aujourd'hui.

**Q-L1-03 — Tentatives refusées de lecture du motif.** Le PRD n'exige l'audit que des lectures. *Défaut :* un refus SEC-01 n'est pas écrit dans `audit_events` (il est dans le log JSON d'accès avec l'utilisateur pseudonyme et le statut 403). À trancher si la conformité veut tracer les tentatives.

**Q-L1-04 — Ordre audit / HealthOS.** *Défaut :* l'entrée `claim.medical_reason.read` est écrite avant l'appel à HealthOS, dans la transaction de la requête ; si HealthOS échoue, tout est annulé (rien n'a été lu). La transaction est validée avant l'envoi de la réponse : un motif n'est jamais renvoyé sans son audit validé.

## Lot L4 — adhésions et cotisations

Défauts appliqués dans `apps/api/members` et `apps/api/payments` ; chacun est testé et se change en une ligne ou en données.

**Q-L4-01 — Émission et échéance des cotisations.** Aucune opération du contrat ne crée de cotisation. *Défaut :* traitement `payments.jobs.issue_month` (rejouable), une échéance par adhérent inscrit au plus tard le dernier jour du mois, montant = `monthly_contribution_xof` de la version en vigueur au 1er, échéance (`due_on`) = 1er du mois. L'impayé (R-01, J+45) court depuis `due_on`. Qui ordonnance (cron) et quelle échéance réelle (1er, 5, 10 du mois) ?

**Q-L4-02 — Effet d'un paiement sur le statut.** *Défaut :* un adhérent `suspendu` repasse `actif` (ou `carence` si le délai n'est pas écoulé) dès que l'impayé restant est sous le seuil de R-01, dans la transaction du webhook. Un adhérent en `carence` qui paie reste en carence. Payer un mois sur trois en retard ne rouvre rien si une échéance dépasse encore 45 jours.

**Q-L4-03 — Plafond consommé (`getMemberEntitlements`).** *Défaut :* année civile de la date demandée, somme des `covered_xof` des dossiers accordés ou payés de l'adhérent (Q-L0-07 reste ouverte).

**Q-L4-04 — 404 ou 410 pour un lien expiré.** `resolve_payment_link` ne renvoie rien pour un jeton inconnu, expiré ou déjà utilisé : l'API ne peut pas les distinguer. *Défaut :* 404 dans ces trois cas ; 410 PAY-03 seulement si la cotisation est déjà réglée ou annulée. Voir CR-L4-01.

**Q-L4-05 — Chiffrement du secret de carte.** Sans dépendance ajoutée, le secret de QR est scellé avec la bibliothèque standard (flot dérivé de HMAC-SHA256 + étiquette HMAC, contexte organisation+carte, clé `MULEMA_CARD_KEY` hors base). *Proposition :* AES-GCM via `cryptography` (Apache-2.0/BSD) si un humain valide la dépendance. QR : fenêtre de 30 s, une fenêtre de tolérance. Aucune opération du contrat ne livre le QR au téléphone de l'adhérent (`cards.current_qr_payload` existe côté serveur) : canal de diffusion à décider.

**Q-L4-06 — Durées de conservation.** *Défaut :* clés d'idempotence des commandes 24 h, des webhooks 30 jours (au-delà, le statut du paiement reste une seconde barrière) ; lien de paiement 7 jours, calculé par l'horloge de la base (même horloge que `resolve_payment_link`).

**Q-L4-07 — Deux paiements confirmés pour une même échéance.** *Défaut :* le second est enregistré `confirme`, sans `contribution.received` (donc sans écriture comptable) et journalisé `payments.contribution_already_settled`. Remboursement ou affectation à l'échéance suivante : à décider.

**Q-L4-08 — MTN MoMo et canal `simulation` au grand livre.** Le plan de comptes (Q-L0-11) n'a pas de compte MTN : un `contribution.received` MTN est refusé par le consommateur L3 (resté en attente, signalé) tant que le compte n'existe pas.

**Q-L4-09 — Transitions manuelles (`changeMemberStatus`).** *Défaut :* vers `suspendu` depuis actif/carence ; vers `actif` seulement si la carence est écoulée ET l'impayé sous le seuil R-01 ; vers `carence` seulement depuis `suspendu` pendant le délai ; même statut = MBR-01.

**Q-L4-10 — Relances.** *Défaut :* relance manuelle seulement (`sendReminder`), message mis en file `en_file` avec un nouveau lien de paiement si une cotisation est jointe ; aucun envoi réel (pas de fournisseur SMS/WhatsApp dans la liste blanche) ni relance automatique planifiée.

**Q-L4-11 — Signature des webhooks simulés.** *Défaut :* `X-Signature` = HMAC-SHA256 hexadécimal du corps brut, secret par canal (`MULEMA_PAYMENT_SECRET_<CANAL>`). Chaque canal réel aura son propre schéma de signature dans son adaptateur.

**Q-L4-12 — Propriétaire BYPASSRLS (suite de Q-L0-14 c).** Prouvé : schéma appliqué par `mulema_owner` (NOSUPERUSER, BYPASSRLS, CREATEROLE), les deux fonctions résolvent sous `mulema_app` et le parcours complet passe ; contrôle négatif : propriétaire sans BYPASSRLS → aucune résolution. Le test crée `mulema_owner` sur le serveur de test et l'y laisse (rôle global, création idempotente).

**Q-L4-13 — Codes d'erreur absents du noyau.** `api.core.errors.ErrorCode` (L1) n'a ni MBR-01, ni IDEM-01/02, ni PAY-01/02/03 : L4 porte sa propre erreur rendue au même format problem+json. Le refus de lien pour une cotisation déjà réglée renvoie 409 `VAL-01` (aucun code de conflit dédié au contrat, même choix que L1).

## Phase 1, voie A — espace adhérent et diaspora (CR-P1-01)

Défauts appliqués dans `apps/api/member_space` ; chacun est testé (`apps/api/tests/e2e/test_member_space.py`, `apps/api/member_space/tests`).

**Q-P1-01 — Qui ouvre un compte adhérent, et pour qui ?** *Défaut :* un compte = le titulaire, rattaché à SON contrat (`user_roles.member_id`), créé par l'admin (`createUser` avec `{"role": "adherent", "member_id": …}`) ; il voit tout son contrat (ayants droit compris). Pas de compte propre pour un ayant droit adulte, pas d'auto-inscription. À trancher : un conjoint adulte doit-il avoir son propre espace, limité à ses dossiers (le titulaire voit aujourd'hui les dossiers de toute la famille, sans acte ni motif) ?

**Q-P1-02 — Ce que l'adhérent voit d'un dossier.** *Défaut :* numéro, bénéficiaire (prénom), établissement, dates, statut, montants (total, part mutuelle, part patient) et le code public de la règle (`R-12` v3) ou le code de motif d'une décision humaine (`MC-02`). Jamais : actes et libellés d'actes (un acte d'un ayant droit peut révéler une pathologie au titulaire), motif, référence HealthOS, score ou alerte de fraude, trace d'évaluation, échéance de revue, auteur de la décision.

**Q-P1-03 — Étapes « virement » et « reçu » de la frise.** Rien dans le contrat ne porte le virement : aucune opération ne fait passer un dossier à `payee`, aucune colonne ne date le paiement, et le parcours « frais avancés remboursés à l'adhérent » (prototype : `RB-26-00412`, virement Wave) n'existe pas (le tiers payant paie la clinique). *Défaut :* la frise est celle du dossier de prise en charge : accordé → « virement » `en_cours` (sans date) ; `payee` → les deux dernières étapes `fait`, `at` nul. Un vrai remboursement à l'adhérent demandera une CR (table de versements, canal, numéro masqué).

**Q-P1-04 — Durée de vie du QR affiché.** *Défaut :* QR de la fenêtre courante (30 s, une fenêtre de tolérance, Q-L4-05), `qr_refresh_at` = début de la fenêtre suivante, réponse `Cache-Control: no-store`. Le QR est servi même si la carte est bloquée (`card_status: bloquee`, `blocked_until`) : le comptoir le refusera (ID-04) ; à confirmer si l'espace doit plutôt le masquer.

**Q-P1-05 — Nom du payeur diaspora.** Le prototype affiche « payée depuis Paris par Kouadio K. » ; le contrat ne garde du payeur que son type et son pays (`payments.payer_kind`, `payer_country_code`). *Défaut :* `MyContribution` expose `payer_kind` et `payer_country_code` seulement ; afficher un nom demanderait de le collecter (donnée personnelle hors pays : à valider avec R9).

**Q-P1-06 — Le QR affiché n'est pas à usage unique (risque relevé par le vérificateur, non corrigé).** *État :* un QR `MC1.<carte>.<fenêtre>.<code>` est accepté pendant sa fenêtre de 30 s ET la suivante (une fenêtre de tolérance, Q-L4-05), soit jusqu'à environ 60 s, et autant de fois qu'on le présente : rien n'enregistre qu'il a déjà servi (`verify_qr_payload`, appelé par `CardQrVerifier.resolve`, vérifie la carte active, le HMAC et la fenêtre, sans état). Le parcours e2e s'en sert d'ailleurs : le même QR ouvre trois identifications de suite (`tests/e2e/test_member_space.py`, fixture `space`). *Risques :* (1) une capture d'écran ou une photo du QR, transmise dans la minute, ouvre une identification à un autre comptoir (y compris dans une autre clinique du réseau) ; la photo et le code SMS envoyé au téléphone du titulaire restent exigés (R1), donc le QR seul ne suffit pas à obtenir une prise en charge, mais le prêt de carte avec complicité du titulaire n'est freiné que par le contrôle photo ; (2) chaque rejeu déclenche un SMS au titulaire (coût, harcèlement) ; (3) trois codes faux saisis sur une identification ouverte par rejeu bloquent la carte du titulaire (`cards.blocked_until`, ID-04) : déni de service possible par un comptoir authentifié malveillant ou compromis. *Option proposée (non implémentée, change le contrat) :* QR consommé à la première identification. Ajouter `cards.last_qr_window bigint` (CR sur `specs/schema.sql` + migration 0003 additive) et, dans `startIdentification`, `UPDATE cards SET last_qr_window = :fenetre WHERE id = :carte AND (last_qr_window IS NULL OR last_qr_window < :fenetre)` dans la même transaction : 0 ligne = QR déjà utilisé, refus avec un code stable à ajouter au contrat (ID-02 à ID-07 sont pris : ex. `ID-08` « QR déjà utilisé : demandez à l'adhérent de rafraîchir sa carte »). La condition « strictement supérieure » interdit aussi de revenir à la fenêtre tolérée après usage de la courante. Effets à accepter : un deuxième scan légitime (erreur de saisie au comptoir) oblige l'adhérent à attendre la fenêtre suivante (≤ 30 s) ou à rafraîchir ; le parcours e2e doit redemander un QR par identification ; `getMyCard` pourrait renvoyer `qr_refresh_at` immédiat après consommation. Alternative plus courte sans changement de schéma : réduire la tolérance à 0 fenêtre (validité ≤ 30 s), qui réduit la fenêtre de rejeu sans la fermer. *À trancher par un humain :* usage unique (CR + code d'erreur) ou statu quo documenté.

## Phase 2, voie B — mesure produit (CR-P2-01)

Défauts appliqués dans `apps/api/metrics` ; chacun est testé (`apps/api/tests/e2e/test_product_metrics.py`, `apps/api/metrics/tests`).

**Q-P2-01 — Les métriques citées ne sont pas dans le PRD.** La consigne renvoie au « PRD §8 métriques : part de dossiers accordés automatiquement, délai médian au comptoir, taux de doublon de webhook, écart de balance » ; dans le PRD v0.2, §8 est le découpage en lots et aucune section ne porte ces métriques. *Défaut :* indicateurs livrés selon la consigne (`ProductMetricKey`) ; le PRD est à compléter par Dajan (section métriques, seuils cibles).

**Q-P2-02 — Durée de rétention des événements d'usage.** *Défaut :* 180 jours (`MULEMA_PRODUCT_EVENTS_RETENTION_DAYS`, bornes 1 à 730), posée à l'insertion (`expires_at`) ; une ligne expirée n'est plus comptée, `metrics.jobs.purge_expired_events` la supprime (ordonnancement à la charge de l'exploitation). À valider avec l'obligation de minimisation applicable (CI, SN).

**Q-P2-03 — « Taux de doublon de webhook » : ce qui est mesurable.** Un webhook rejoué est absorbé par la clé d'idempotence et seulement journalisé (`payments.webhook_replayed`) : aucune table ne compte les rejeux reçus. *Défaut :* l'indicateur mesure les doubles EFFETS (cotisation reçue plus d'une fois dans `outbox_events`, attendu 0), pas la fréquence des rejeux. Mesurer les rejeux demanderait de les enregistrer dans L4 (`payments.webhooks`, par exemple une ligne `audit_events` `payment.webhook.replayed`) : non fait, hors du périmètre de la voie B.

**Q-P2-04 — k-anonymat sur les indicateurs d'intégrité.** *Défaut :* seuil de 5 appliqué à TOUS les indicateurs, avec un effectif défini par indicateur (bénéficiaires distincts pour les dossiers, sessions pour les écrans, adhérents pour liens et cotisations, écritures pour le grand livre). Conséquence : une organisation de moins de 5 écritures voit l'écart du grand livre masqué. Alternative : exempter l'écart du grand livre et le taux de doubles effets (comptes système, pas de personnes).

**Q-P2-05 — Rotation de l'empreinte de session.** *Défaut :* rotation au changement de jour UTC (minuit à Abidjan et à Dakar) : un accueil commencé avant minuit et terminé après compte comme commencé sans être terminé. Le navigateur doit tirer un identifiant aléatoire (16 octets au moins) et le renouveler ; le serveur refuse ce qui ressemble à un identifiant de personne mais ne peut pas prouver le hasard.

**Q-P2-06 — Durées mesurées par l'écran.** `counter_decision_shown.duration_ms` (scan → écran de décision, objectif < 10 s) est mesurée par le comptoir : le serveur ne voit ni le scan ni l'affichage. *Défaut :* valeur bornée acceptée telle quelle ; le délai serveur demande → décision est mesuré à part depuis les tables (`claims_decision_median_ms`).

**Q-P2-07 — Volume et abus.** Un utilisateur authentifié peut gonfler ses propres comptages (un événement par requête, sans limite de débit). *Défaut :* aucune limite dans l'API (pas de dépendance nouvelle) ; à poser au mandataire inverse si besoin. Les indicateurs pilotent le produit, ils ne servent à aucune décision de prise en charge ni à aucun paiement.

## Phase 3, voie A — marque blanche, assureur, employeur, plateforme (CR-P3-01)

Défauts appliqués dans `apps/api/branding` et `apps/api/partners` ; chacun est testé (`apps/api/tests/e2e/test_branding.py`, `apps/api/tests/e2e/test_partners.py`, tests unitaires des deux modules).

**Q-P3-01 — Qui est « plateforme » et qui détient `admin_plateforme` ?** *Défaut :* l'organisation qui exploite l'instance reçoit la capacité `plateforme` et ses administrateurs le rôle `admin_plateforme` par l'exploitation (SQL relu), jamais par l'API (`createUser` et `replaceUserRoles` le refusent, la base le refuse hors organisation « plateforme »). Ce rôle n'a aucun accès métier (ni adhérent, ni dossier, ni grand livre).

**Q-P3-02 — Invitation du premier gestionnaire.** Le fournisseur d'identité n'est pas choisi (PRD §10 Q2). *Défaut :* la plateforme fournit le sujet d'identité ; le compte est créé actif avec les rôles `gestionnaire` et `admin` de la NOUVELLE organisation ; aucun message n'est envoyé (aucun fournisseur d'e-mail ou de SMS dans la liste blanche).

**Q-P3-03 — Statut d'une organisation accueillie.** *Défaut :* `integration` (le contrat L1 l'admet ; la connexion reste possible, seul `inactive` la bloque). Aucune opération ne la passe à `active` : à décider (exploitation, ou opération de plateforme à ajouter).

**Q-P3-04 — Contenu du gabarit.** *Défaut :* instantané de la configuration EN VIGUEUR de l'organisation « plateforme » à la date du jour : plan de comptes, règles (paramètres de la version en vigueur, valeurs exactes), produits actifs (version en vigueur et garanties), actes et barème du jour. Copie : règles et produits en version 1 `brouillon` datée du jour, à publier par l'organisation accueillie ; barème valable dès le jour (`tariff_items` n'a pas d'état) ; réseau de soins NON copié (propre à chaque organisation). Le gabarit porte le pays déclaré par la plateforme ; il n'est copié que vers une organisation du même pays.

**Q-P3-05 — Ratio sinistres/primes (S/P).** *Défaut :* sinistres = part mutuelle des dossiers accordés (`accordee_auto`, `accordee`, `payee`) demandés dans la période ; primes = cotisations payées dans la période (date de paiement) ; ratio en points de base, sans provisions ni sinistres tardifs. Effectif = le plus petit des deux groupes (sinistrés, cotisants). À valider par l'actuaire de l'assureur.

**Q-P3-06 — « Contrats arrivant à échéance » (employeur).** *Défaut :* contrats de groupe (`employers.contract_end`), horizon 90 jours (paramètre 1 à 365), statuts `en_cours`, `a_echeance`, `echu`, `sans_echeance`. Rien sur l'échéance individuelle d'un salarié (ce serait une donnée de personne).

**Q-P3-07 — Catégories de garantie publiées.** Une catégorie (« maternité ») renseigne sur la santé d'un petit groupe. *Défaut :* publiée seulement si au moins 5 personnes distinctes la portent ; sinon fondue dans `autres_regroupes`, lui-même grossi jusqu'à 5 personnes (protection contre la soustraction total - catégories). Un seuil plus haut pour les catégories sensibles (maternité, santé mentale) est à décider.

**Q-P3-08 — Lecture publique de la marque et propriétaire BYPASSRLS.** Comme `resolve_organization_by_slug` (Q-L4-12), `resolve_organization_branding` et `platform_create_organization` supposent un propriétaire de schéma BYPASSRLS ; sans lui, rien n'est résolu et aucune organisation n'est créée (échec fermé).

**Q-P3-09 — Jetons surchargeables.** *Défaut :* `accent`, `accent_hover`, `accent_fg`, `brand_deep`, en clair et en sombre ; le focus suit l'accent ; fonds, encres, statuts, plein soleil (noir sur blanc, 7:1) et polices ne se surchargent pas. Paires gardées : celles du contrat de design qui touchent ces jetons (4,5:1 texte, 3:1 focus). Un accent égal à une couleur de statut est refusé ; une couleur seulement « proche » d'un statut est acceptée (pas de distance de couleur fixée).

**Q-P3-10 — Logo.** *Défaut :* 32 Ko décodés ; `https` seulement vers un hôte:port de la liste blanche d'egress de l'instance (aucun CDN), ou chemin interne ; SVG accepté seulement s'il est déjà sûr (rien n'est réécrit). Quand un stockage d'objets du pays existera, préférer un objet stocké à un data-URI en base.

**Q-P3-11 — Effectifs publiés par palier.** Les espaces assureur et employeur reprennent `api.metrics.privacy.contributor_band` (paliers 5, 10, 20, 50, 100), en cours de durcissement par la voie P2 : une évolution de cette fonction change aussi les effectifs P3.

**Q-P3-12 — Gestion déléguée.** `organizations.managed_by_organization_id` existe, mais un assureur ne lit QUE son organisation : aucune vue d'un portefeuille géré pour le compte d'un autre. À trancher si un assureur doit voir le portefeuille qu'une mutuelle gère pour lui (demanderait une CR et une décision sur la résidence des données).

### Suivi de la revue du vérificateur sur CR-P3-01 (CR-P3-02)

**Q-P3-13 — Arrondi des montants publiés.** *Défaut :* millier de francs CFA le plus proche (demi vers le haut) pour primes, sinistres et parts mutuelle (`api.partners.privacy.AMOUNT_STEP_XOF`) ; taux en points de base et délai moyen non arrondis. Un pas relatif (par exemple trois chiffres significatifs) serait plus protecteur sur les grands portefeuilles ; à valider avec l'assureur (précision de pilotage contre risque de recoupement).

**Q-P3-14 — Comptes publiés au plancher du palier.** *Défaut :* `value` d'un compte (adhérents, dossiers) = plancher du palier (5, 10, 20, 50, 100 = « 100 ou plus »), comme `contributors`. Un portefeuille de 3 000 adhérents s'affiche donc « 100 » : il faudra des paliers plus hauts (200, 500, 1 000…) pour un pilotage utile ; à décider avec Q-P3-11 (paliers communs à P2).

**Q-P3-15 — Statuts d'adhérent : risque résiduel.** Les statuts sont un INSTANTANÉ pris à la fin de la période (dernier changement antérieur), pas un flux par semaine : la différence entre deux fins de période peut encore suggérer qu'un statut a changé, mais seulement au franchissement d'un palier (comptes par palier, masques complémentaires). Une publication par semaine des changements de statut serait plus stricte ; à décider.

**Q-P3-16 — Domaine squatté avant preuve.** L'unicité de `custom_domain` (contrat CR-P3-01) vaut aussi pour un domaine NON prouvé : une organisation peut en bloquer une autre en déclarant son domaine la première (sans jamais le voir servi). *Défaut :* inchangé (pas de contrainte retirée sans validation humaine) ; l'exploitation libère le domaine. Proposition : unicité restreinte aux domaines prouvés (index partiel) et expiration d'une déclaration non prouvée après 7 jours.

**Q-P3-17 — Résolveur DNS réel et revérification.** Aucun résolveur n'est branché (port `DnsTxtResolver`, défaut `NoDnsTxtResolver` : aucun domaine n'est jamais prouvé, donc jamais servi). Un résolveur réel est une destination réseau à ajouter à la liste blanche d'egress (revue humaine, résidence des données). Une revérification périodique (domaine expiré ou transféré) n'existe pas ; à décider avec le choix du résolveur.

**Q-P3-18 — Hôtes de logo.** *Défaut :* liste dédiée vide (`BrandingPorts.logo_hosts`) : seuls un chemin interne et un data-URI sont admis en production tant qu'un hôte de logo (stockage d'objets du pays) n'est pas déclaré. Remplace le défaut de Q-P3-10 (liste blanche d'egress, qui admettait HealthOS).

**Q-P3-19 — Qui règle la marque d'une organisation accueillie ?** L'API ne permet à `admin_plateforme` ni de lire ni de régler la marque d'une autre organisation (CR-P3-03, point 2). *Défaut (appliqué par la voie B) :* l'admin de l'organisation la règle lui-même dans la console (« Marque ») après l'accueil ; l'écran « Organisations » l'annonce comme prochaine étape.

**Q-P3-20 — Choix de l'organisation avant connexion (marque blanche web).** *Défaut :* `MULEMA_ORGANIZATION_SLUG` pour un déploiement dédié, sinon domaine personnalisé (en-tête Host, seulement s'il est prouvé côté API) ; en démonstration et en test seulement, cookie `mc-org` parmi trois organisations fictives. Lecture de `getOrganizationBranding` au rendu serveur, 800 ms au plus, cache 5 min : une marque changée met jusqu'à 5 min à apparaître. À valider : durée du cache ; titre et icônes du manifeste PWA (comptoir, espace adhérent) restent MulemaCare (statiques), seul le titre des pages console et partenaires suit la marque.

**Q-P3-21 — Repli de la marque côté client.** *Défaut :* si une paire dérivée échoue AA dans un thème (défense en profondeur, l'API l'a déjà refusée), TOUTES les couleurs de la marque sont écartées (clair et sombre), le nom et le logo restent ; signalé en console en développement seulement. Alternative : ne replier que le thème fautif.

**Q-P3-22 — Mesure dans les espaces partenaires.** Le catalogue fermé n'a aucun événement propre aux espaces assureur et employeur (consultation, export) ; aucun n'est envoyé (consigne : pas d'ajout). Faut-il un événement `partner_export_created` (surface console) ? Il demanderait une CR sur `ProductEventName`.
