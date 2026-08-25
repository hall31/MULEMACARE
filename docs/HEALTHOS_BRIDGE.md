# Bridge MulemaCare → HealthOS

Le site MulemaCare et HealthOS restent deux applications séparées. Le bridge ne
remplace aucune API existante et il est désactivé par défaut.

## Contrat v1

- Base : `https://<healthos>/api/v1/partner`
- Authentification : `X-API-Key`, `X-Timestamp`, `X-Nonce`, `X-Signature`.
- Signature : HMAC-SHA256 de `timestamp + "\n" + nonce + "\n" + méthode + "\n" + chemin + "\n" + sha256(corps)` avec la clé partenaire.
- Les nonces sont à usage unique pendant cinq minutes ; HealthOS refuse les relectures.
- La préautorisation est une demande `PENDING_REVIEW`, jamais une approbation automatique.

## Activation contrôlée

Configurer sur l'hébergement MulemaCare, sans commiter les secrets :

```text
MULEMACARE_HEALTHOS_BRIDGE_ENABLED=true
HEALTHOS_BASE_URL=https://healthos.example.org
HEALTHOS_PARTNER_API_KEY=<clé partenaire HealthOS>
HEALTHOS_TIMEOUT_MS=2500
```

Avant activation, constituer une table de correspondance validée entre un
numéro CSSA et `patient_id` HealthOS. Il est interdit de deviner cet identifiant
depuis une carte ou une adresse email. Démarrer par un tenant pilote, en lecture
des droits seulement, puis activer les préautorisations après rapprochement des
contrats et des plafonds.

## Rollback

Remettre `MULEMACARE_HEALTHOS_BRIDGE_ENABLED=false`. Le site MulemaCare continue
alors d'utiliser ses parcours existants sans appel HealthOS.
