# Bridge MulemaCare → HealthOS

Le site MulemaCare et HealthOS restent deux applications séparées. Le bridge ne
remplace aucune API existante et il est désactivé par défaut.

## Contrat v1

- Base : `https://<healthos>/api/v1/partner`
- Authentification : `X-API-Key`, `X-Timestamp`, `X-Nonce`, `X-Signature`.
- Signature : HMAC-SHA256 de `timestamp + "\n" + nonce + "\n" + méthode + "\n" + chemin + "\n" + sha256(corps)` avec la clé partenaire.
- Les nonces sont à usage unique pendant cinq minutes ; HealthOS refuse les relectures.
- La préautorisation est une demande `PENDING_REVIEW`, jamais une approbation automatique.
- Chaque clé partenaire porte des **portées** explicites. Une clé sans la portée
  demandée reçoit `403`, quelle que soit la configuration du site.

## Les trois étapes, dans cet ordre

Le bridge s'ouvre en trois temps. On ne passe au suivant qu'avec le rapport du
précédent en main.

| Étape | `MULEMACARE_HEALTHOS_BRIDGE_MODE` | Portées de la clé | Ce qui se passe |
|---|---|---|---|
| 1. Observation | `observe` | `eligibility:read` | Un script compare hors ligne les décisions des deux systèmes. Aucune page n'appelle HealthOS, aucun adhérent n'est affecté. |
| 2. Lecture des droits | `read` | `eligibility:read` | Les droits HealthOS sont affichés à côté de ceux du site. Toujours aucune écriture. |
| 3. Préautorisations | `preauth` | `eligibility:read`, `claims:preauthorize` | Le site peut déposer une demande, qui reste `PENDING_REVIEW`. |

Aujourd'hui, seule l'étape 1 est implémentée. Les étapes 2 et 3 demandent
chacune leur propre lot : le mode ne fait rien tout seul.

## Étape 1 — rapprochement en mode observation

### La table de correspondance

Elle rapproche un numéro CSSA d'un `patient_id` HealthOS. Elle est produite par
la migration de données et **relue par un humain** : chaque ligne porte
`validated_at` et `validated_by`, et une ligne sans validation est ignorée.
Deviner l'identifiant HealthOS depuis une carte, un email ou un téléphone est
interdit, et `site/app/Services/HealthOSIdentityMap.php` n'offre aucun moyen de
le faire.

Modèle : `site/data/healthos_identity_map.example.json`. Le fichier réel
(`site/data/healthos_identity_map.json`) n'est pas versionné.

Deux lignes qui rapprochent le même numéro de deux patients — ou le même patient
de deux numéros — **annulent la table entière**. Une table refusée arrête le
rapprochement ; une table ambiguë le ferait mentir, et l'erreur se paierait en
droits de santé montrés à la mauvaise personne.

### La clé partenaire, restreinte côté HealthOS

Côté HealthOS, la clé du pilote est émise avec la seule portée nécessaire :

```bash
PYTHONPATH=. DATABASE_URL=postgresql+psycopg2://... \
  python -m tools.provision_partner_credential \
    --partner-id <partenaire-mulemacare> \
    --scopes eligibility:read
```

La clé n'est affichée qu'une fois. Avec cette portée, `POST /claims/analyze`,
`POST /claims/preauthorize`, le score de confiance des prestataires et les
alertes de fraude répondent `403`. C'est HealthOS qui refuse, pas le site qui
s'abstient : c'est la différence entre une promesse et un contrôle.

### Lancer le rapprochement

```bash
MULEMACARE_HEALTHOS_BRIDGE_ENABLED=true \
MULEMACARE_HEALTHOS_BRIDGE_MODE=observe \
HEALTHOS_BASE_URL=https://healthos.example.org \
HEALTHOS_PARTNER_API_KEY=<clé partenaire, portée eligibility:read> \
HEALTHOS_PILOT_TENANT=<tenant pilote> \
HEALTHOS_TIMEOUT_MS=2500 \
php site/scripts/healthos_observation_run.php --out site/data/healthos_observation_$(date +%F).json
```

Le script sort en `0` même quand il trouve des écarts — trouver un écart est le
but. Il sort en `1` quand il n'a pas pu tourner : bridge éteint, mauvais mode,
table de correspondance inexploitable. Chaque cause est nommée.

### Lire le rapport

| Verdict | Sens |
|---|---|
| `match` | Les deux systèmes disent la même chose. |
| `divergent` | Ils diffèrent sur la couverture, la carence ou le plafond restant. Chaque écart est expliqué. |
| `unreachable` | HealthOS n'a pas répondu. Ce n'est ni une concordance ni un écart. |
| `unmapped` | Le numéro n'est pas dans la table. Aucun appel n'est parti. |
| `not_a_record` | Le site a répondu avec sa fiche de démonstration. Écarté : comparer une fiction ne dit rien. |
| `unknown_to_site` | Rapproché côté table, inconnu côté site. À reprendre dans la migration. |

Deux réglages évitent les faux écarts, et un faux écart en masse rend le rapport
illisible :

- `HEALTHOS_MINOR_UNITS_PER_UNIT` (défaut `1`) — HealthOS compte en unités
  mineures ; le franc CFA n'a pas de subdivision en usage. Une valeur fausse
  ferait diverger tous les plafonds d'un facteur constant.
- `HEALTHOS_CAP_TOLERANCE` (défaut `0`) — écart de plafond toléré avant d'être
  signalé, dans l'unité du site.

### Ce que l'étape 1 ne fait pas

Aucune page, aucun contrôleur n'appelle le rapprochement : un test le vérifie sur
l'arborescence du site (`site/tests/HealthOSObservationTest.php`). Un adhérent ne
voit jamais la décision de HealthOS pendant cette phase, donc une divergence ne
peut pas lui coûter une prise en charge.

## Tests

Le site n'a ni Composer ni `vendor/`. Le lanceur est en bibliothèque standard :

```bash
php site/tests/run.php
```

La CI l'exécute dans le job `MulemaCare bridge`, à côté des `php -l`.

## Rollback

Remettre `MULEMACARE_HEALTHOS_BRIDGE_ENABLED=false`. Le site MulemaCare continue
alors d'utiliser ses parcours existants sans appel HealthOS. Aucune donnée n'est
à défaire : l'étape d'observation n'écrit rien.
