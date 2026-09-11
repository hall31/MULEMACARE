# Adhésion WhatsApp — ops MulemaCare

## Principe (meilleur système)

**Register-first, pay-second :**

1. Le formulaire `/adhesion` (ou deep-link `?wa=1`) crée **toujours** le client dans le système (`PENDING_PAYMENT` + CSSA + NSS + `tariff_version`).
2. WhatsApp n’est **pas** un PSP : c’est le canal desk (preuve MoMo / Qonto, relance).
3. Activation `ACTIVE` uniquement via :
   - webhook Stripe signé, **ou**
   - confirmation ops HITL (`POST /api/admin/payments/confirm`).

## Parcours WhatsApp / MoMo

```text
Formulaire → POST /api/subscribe (payment_method=whatsapp|orange_money|mtn_momo)
  → members.json + (MySQL best-effort)
  → response.whatsapp_url (template CSSA + montant + USSD)
  → user paie MoMo + envoie capture
  → Admin hub → Paiements → Confirmer
  → ACTIVE
```

Deep-link marketing : `https://mulemacare.com/adhesion?wa=1&plan=silver&comp=family`

## Diaspora

| Rail | Méthode API | Activation |
|------|-------------|------------|
| Stripe | `payment_method=stripe` | Webhook |
| Qonto | `payment_method=qonto` | HITL + preuve |

## Admin

Vue **Paiements** dans `/espace-admin` : file `pending_payments`, bouton confirmer + réf MoMo/virement.

## Env

Voir `site/.env.example` : `QONTO_*`, `TARIFF_ACTIVE_VERSION`.
