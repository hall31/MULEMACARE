# Zero-friction — devis & adhésions (particuliers + entreprises)

## Principe

1. **Simulateur → Express** : 1 clic vers `/adhesion?express=1&…` (corrige `famille`→`family`).
2. **Express adhésion** : nom + WhatsApp + rail paiement → `POST /api/express` → client `PENDING` + CSSA/NSS.
3. **PME** : profil PME du simulateur → `/entreprises?employees=…`.
4. **Entreprises** : formulaire RH → `mode=corporate` → devis + contrat `ENT-…` + WhatsApp.

## API

```http
POST /api/express
{ "mode": "quote"|"adhere"|"corporate", … }
```

## Jamais

- Toast fake sans enregistrement (form B2B).
- ACTIVE sans Stripe webhook / HITL.
