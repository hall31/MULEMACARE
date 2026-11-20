# CLAUDE.md

@AGENTS.md

## Spécifique à Claude Code

- Commence chaque session en lisant `AGENTS.md`, `specs/PRD.md` et ton lot dans `specs/LOTS.md`.
- Utilise le mode plan pour tout lot qui touche plus de cinq fichiers : propose le plan, attends la validation, puis exécute.
- Lance les tests après chaque modification significative, pas seulement à la fin.
- Pour une tâche indépendante (recherche dans le code, revue, génération de jeux de données fictifs), délègue à un sous-agent plutôt que de remplir ton contexte.
- Les agents vérificateurs n'ont pas le droit de modifier le code qu'ils relisent : ils écrivent leurs constats dans la PR.
- Quand tu crées un commit, garde le message court, en français, et indique le lot : `L3: contre-passation des écritures (R7)`.
