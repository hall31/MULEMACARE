# Questions ouvertes — lot L8 (JOE)

Défauts appliqués dans `apps/api/joe`, chacun testé ; à reporter dans `specs/QUESTIONS.md` par l'intégration (ce lot ne modifie rien hors de son dossier).

**Q-L8-01 — Câblage.** `api.core.app` ne monte pas encore JOE. À ajouter par l'intégration : `install(app, JoeRuntime(clock=..., model=build_language_model(JoeModelSettings.from_env(os.environ)), members=member_reader_factory(members_runtime.clock, members_runtime.card_keys)))` (`api.joe.routes`, `api.joe.model`, `api.joe.ports`).

**Q-L8-02 — Règle de recommandation du brouillon de décision.** *Défaut :* refuser si droits fermés à la date du soin (R-01) ou plafond restant < part couverte (R-09) ; demander des pièces si alerte de fraude levée ou aucune facture déposée ; accorder sinon. Recommandation calculée sans le modèle (le modèle ne rédige que la justification). À valider par le médecin-conseil.

**Q-L8-03 — Brouillon pour un dossier hors revue.** *Défaut :* 404 NOT-01 si le dossier n'est ni `en_revue` ni `pieces_demandees` (le contrat ne déclare que 404).

**Q-L8-04 — Modèle local.** *Défaut :* `MULEMA_JOE_MODEL=deterministe` (aucun appel réseau). Le mode `local` (format Ollama) n'accepte qu'une adresse de boucle locale ET doit figurer dans `infra/egress-allowlist.txt` du pays (ex. `CI 127.0.0.1:11434`), sinon la garde de l'application le refuse et JOE se replie sur le déterministe. Quel modèle local, sur quel hôte (même machine que l'API ?) : à décider par l'exploitation.

**Q-L8-05 — Pseudonymisation de la question libre.** Les valeurs identifiantes lues par les outils, numéros, téléphones, courriels, dates et mots à majuscule (sauf codes métier et mots courants en début de phrase) sont masqués avant le modèle ; un contrôle final bloque l'envoi en cas de fuite. Un nom tapé entièrement en minuscules et inconnu des enregistrements consultés n'est PAS détectable : risque résiduel à accepter ou à fermer (question non transmise au modèle).

**Q-L8-06 — Recherche ⌘K non journalisée.** *Défaut :* la recherche n'est pas une action de JOE (aucun modèle) : pas de ligne `ai_actions`. Le médecin-conseil ne cherche pas les adhérents (`getMember` lui est fermé).

**Q-L8-07 — Journal.** Une ligne `lecture` par outil appelé, plus une ligne `reponse`/`refus`/`preparation` ; `input`/`output` ne contiennent que des identifiants et le texte à jetons (question masquée).
