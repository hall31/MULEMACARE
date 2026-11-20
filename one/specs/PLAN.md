# PLAN — MulemaCare One

Base : `AGENTS.md`, `specs/PRD.md` (brouillon), `specs/LOTS.md`. Branche de travail : `feat/mulemacare-one-core` (worktree `mulemacare-one-core`).

## Condition d'entrée

La décision `DOCS/DECISION_Q3_2026_SUPPORTOS_FIRST.md` gèle le portfolio hors SupportOS. Ce chantier est lancé sur instruction explicite de Dajan (2026-09-30), isolé dans `APPS/PUBLIC/HEALTH/MULEMACARE/one/`, sans toucher aux autres produits. Aucun push, aucun déploiement.

## Vagues

| Vague | Lots | Condition de sortie |
|---|---|---|
| 0 | L0 Contrats | schema.sql s'applique, openapi passe le linter, test anti-diagnostic vert, relecture vérificateur |
| 1 | L1 Noyau, L2 Règles, L3 Grand livre, L6 Console, L7 Comptoir, L9 Intégration | `make check` par lot, vérificateur par lot |
| 2 | L4 Adhésions/cotisations, L5 Tiers payant API | dépendent de L1, L2, L3 |
| 3 | L8 JOE | dépend de L5 |
| 4 | Intégration bout en bout | parcours comptoir → règle → grand livre, isolation, egress |

Un commit par lot vert, dans le même worktree (un worktree par projet).

## Risques

- Contrats L0 écrits sans relecture humaine : le vérificateur remplace la relecture, Dajan valide ensuite (point ouvert).
- Seuils métier issus du prototype : configurables en données, à valider (PRD §10).
- Conflits de fichiers partagés (Makefile, pyproject) entre lots parallèles : L0 pose le squelette, chaque lot n'ajoute que dans son périmètre.
