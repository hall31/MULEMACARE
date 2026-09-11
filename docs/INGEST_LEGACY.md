# Ingestion legacy → nouveau MulemaCare

Contrat pour passer les CSV prod (Laravel 2018–2026) vers le site PHP 8 / Mutuelle OS **sans casser les droits ni inventer un actif payé**.

## Règle d’or

Les **420 « actifs » legacy ne deviennent pas `ACTIVE` tout seuls**.  
Statut cible = `PENDING_REVIEW` → ActionCenter HITL → `ACTIVE` seulement avec preuve de cotisation (Stripe, MoMo, virement, historique ops).

## Flux

```text
CSV prod → CRM HTML (décision humaine) → mulemacare-ingest.json
        → php site/tools/legacy_ingest.php --dry-run
        → revue ops
        → --commit  (members.json + mulema_subscribers, cartes CSSA neuves)
```

## Mapping déterministe (déjà dans le CRM)

| Origine | Cible 2026 | HITL |
|---|---|---|
| Formule A / 50 % / Étudiant / Collégien / Single | Bronze · solo | Non si email unique |
| Formule B / 70 % / Couple | Silver · couple | Oui si pack vide |
| Formule C / 80 % Famille ou Senior | Gold | Oui (écart tarif vs grille actuelle) |
| Pack catalogue vide (417) | Silver, composition via ayants droit | **Toujours** |
| `actif` | `PENDING_REVIEW` | **Toujours** |
| `en_attente` | `PENDING_PAYMENT` | Non |
| `expire` | `SUSPENDED` | Oui avant réactivation |
| Devis particulier | `quotes.json` seulement | Non |
| Devis entreprise | File commerciale PME | Oui (tarif groupe) |

Platinium **jamais** auto-assigné.

## Identité & couverture

- Clé de fusion : email normalisé. Doublons = bloqués dans le CRM.
- Persister `legacy_user_id` + `legacy_unique_id`. Nouveau `CSSA-XXXX-yy` à l’émission.
- `valid_from` / `valid_until` = dates legacy. **Ne pas** recaler la carence à J+90 si la couverture a déjà couru ≥ 90 jours.
- 216 ayants droit collés via `id_user`. Titulaire = premier bénéficiaire.

## Rollback

`--commit` écrit un fichier horodaté `data/members.ingest-YYYYMMDD.json`.  
Le `members.json` courant n’est remplacé qu’après copie de sauvegarde. Flag off = garder le JSON précédent.
