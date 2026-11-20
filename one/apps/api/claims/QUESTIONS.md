# Lot L5 — questions ouvertes (défaut appliqué)

Aucun contrat modifié, aucune demande de changement déposée, aucune dépendance ajoutée.
À reporter dans `specs/QUESTIONS.md` à l'intégration (fichier partagé non touché pendant le lot).

**Q-L5-01 — QR dynamique et fournisseur SMS.** Le format du QR est porté par l'émission de carte
(L4) et le fournisseur SMS n'est pas choisi. *Défaut :* ports `QrVerifier` et `SmsSender`
injectés par `install(app, runtime)`, sans implémentation de production ; `SimulatedSmsSender`
n'envoie rien sur le réseau.

**Q-L5-02 — Saisie manuelle du numéro.** R1 exige trois facteurs. *Défaut :* `member_number`
ouvre une identification sans facteur QR ; elle n'atteint jamais `verifiee`, `createClaim`
répond 422 ID-07. Seule la carte du titulaire est trouvée par numéro.

**Q-L5-03 — Prix ligne à ligne.** `Decision` (L2) ne donne que des totaux, or `claim_items`
exige `covered_xof` par ligne. *Défaut :* L5 appelle la fonction de prix du moteur
(`engine._price`) et vérifie que la somme égale le total du moteur. À exposer publiquement par L2.

**Q-L5-04 — Faits fournis au moteur.** Statut à la date du soin = dernier
`member_status_history` avant la fin du jour local, sinon statut courant ; jours d'impayé =
date du soin − plus ancienne échéance non payée à cette date ; consommation R-09 = dossiers
`accordee_auto`/`accordee`/`payee` de l'adhérent sur l'année civile du soin (Q-L0-07 ouverte).

**Q-L5-05 — Score de fraude.** Fournisseur non choisi (Q-L0-05). *Défaut :* `NoFraudScore`
(aucun score, donc revue R-20 pour tout dossier, Q-L2-05). Les tests injectent 0,06.
`fraud_flagged` reste faux : aucune règle F-03 en données.

**Q-L5-06 — Photo.** Aucun stockage d'objets dans le pays n'est branché. *Défaut :*
`photo_url = null`.

**Q-L5-07 — Durée de validité du code SMS** (Q-L0-06). *Défaut :* 10 minutes
(`ClaimsRuntime.sms_code_validity`). Code à 6 chiffres, empreinte PBKDF2 salée, à usage unique.
Une identification ne sert qu'à un dossier (409 CLM-01 sinon).

**Q-L5-08 — Hors ligne.** *Défauts :* format de signature de Q-L7-03 (ES256, r‖s, JSON canonique)
vérifié en Python pur ; OFF-01 si synchronisé après `expires_at` ou validité plus longue que
HL-01 ; OFF-03 si le total déclaré ou au barème ≥ seuil R-12. OFF-04, adhérent inconnu (NOT-01)
et acte inconnu (CLM-02) ne créent rien et n'émettent aucun événement.

*Règle remplacée (2026-10-01).* L'ancien défaut confirmait tout accord valide par HL-01
(`accordee_auto`) « même si R-01 à R-09 auraient refusé », sans lire la décision du moteur : un
adhérent suspendu ou en carence, ou une clinique hors réseau, obtenait un accord payable. Cela
contredit AGENTS.md (« la décision vient du moteur de règles ») : défaut bloquant relevé par le
vérificateur. *Nouveau défaut :* une fois la signature, l'identification, la validité et le
seuil contrôlés, le moteur L2 décide aux faits et versions de la date du soin :

- refus (R-01, R-04, R-07, R-09) : dossier `refusee` avec `rule_id`/`rule_version` de la règle,
  accord `rejetee_a_la_synchro` (couverture 0, même règle), `claim.decided` `refusee`, aucune
  écriture de grand livre ; réponse et `authorization.synced` : `rejetee` + ce code R-0x ;
- revue (R-20) : dossier `en_revue` (échéance R-20) dans la file du médecin-conseil, accord
  non confirmé (`rejetee_a_la_synchro`, couverture 0, règle R-20) ; réponse `rejetee` + `R-20`.
  Si le médecin-conseil accorde ensuite, aucun nouvel accord n'est émis (Q-L5-09) ;
- accord automatique (R-12) : dossier `accordee_auto` décidé par R-12, accord `synchronisee`
  porté par HL-01 ; réponse `confirmee`.

Le score de fraude est lu à la synchronisation par le même port qu'en ligne (avant : « fraude non
évaluée », ce qui, avec le moteur, aurait tout envoyé en revue). Avec `NoFraudScore` (Q-L5-05),
tout accord hors ligne part donc en revue tant qu'aucun fournisseur n'est choisi.
Codes renvoyés : R-01…R-20 existent déjà dans `ErrorCode` (contrat inchangé) ; les descriptions
d'`offline-sync` et d'`authorization.synced` ne citent que OFF-0x : CR-L5-01.
**À confirmer par un humain :** (1) un patient soigné sur la foi d'un accord provisoire puis
refusé par le moteur reste à la charge de qui (adhérent, clinique, mutuelle) ? (2) revue
plutôt qu'accord quand le seul obstacle est l'absence de score ; (3) `rejetee` pour un dossier
en revue (le contrat n'offre que `confirmee`/`rejetee`).
Concurrence : chaque (`device_id`, `offline_ref`) est verrouillé (verrou consultatif, ordre
trié) avant lecture ; l'identification est lue `FOR UPDATE` puis contrôlée non utilisée.

**Q-L5-09 — Décisions humaines.** *Défauts :* `accorder` n'émet pas d'accord (`authorizations`
exige une règle) ; le grand livre passe l'écriture sur `claim.decided`. Remise en revue par la
clinique tracée avec le motif `R-20`. `claims.decision_rule_*` est nul après une décision
humaine (copie de la dernière décision). Liste des motifs `reason_code` toujours à définir
(Q-L0-13).

**Q-L5-10 — Lecture du motif quand HealthOS échoue.** L1 (Q-L1-04) annule l'audit si HealthOS
échoue ; L9 dit « toute tentative tracée ». *Défaut :* règle L1 (502 INT-01, aucun audit).

## À intégrer hors périmètre L5

`api.core.app.create_app` monte L3 lui-même ; L5 se monte par
`api.claims.routes.install(app, ClaimsRuntime(...))`, avec la liste blanche HealthOS dans
`Settings.egress_allowlist`.
