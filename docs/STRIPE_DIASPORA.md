# Stripe Diaspora — Ops MulemaCare

## Parcours

1. Sponsor diaspora remplit `/adhesion` (EUR) ou modal (EUR/USD).
2. `POST /api/subscribe` crée un membre `PENDING_PAYMENT` + session **Checkout Subscription**.
3. Redirect Stripe → paiement carte.
4. Webhook `POST /api/stripe/webhook` (signature `Stripe-Signature`) → `ACTIVE`.
5. Retour `/adhesion?paid=1&cssa=CSSA-…` + poll lookup jusqu’à ACTIVE.

## Variables d’environnement (IONOS / `.env`)

```bash
STRIPE_ENABLED=true
STRIPE_SECRET_KEY=sk_live_…
STRIPE_PUBLISHABLE_KEY=pk_live_…
STRIPE_WEBHOOK_SECRET=whsec_…
DB_PASS=…   # plus jamais en clair dans config.php
```

## Dashboard Stripe

- Endpoint : `https://mulemacare.com/api/stripe/webhook`
- Events : `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`, `customer.subscription.paused`
- Mode : **Subscription** (interval `year` ou `month` selon `cycle`)

## Devises / canaux (canon produit)

| Segment | Devise | Canal | Activation |
|---------|--------|--------|------------|
| Diaspora | EUR / USD | **Stripe Checkout** (paiement en ligne) | Webhook signé |
| Diaspora | EUR / USD | **Virement Qonto** | HITL ops (preuve + CSSA) |
| Afrique | XAF | **Orange Money / MTN MoMo via Stripe** | Webhook signé |
| Support | — | WhatsApp (aide / preuve Qonto) | Ne active jamais seul |

Détail sprints : [`plan-tarifs-whatsapp.md`](./plan-tarifs-whatsapp.md).

## Tests manuels

```bash
# Preuve PENDING → ACTIVE (signature webhook)
php site/tests/test_stripe_webhook_activation.php

# Syntaxe
php -l site/app/Services/StripePaymentService.php
php -l site/app/Controllers/ApiController.php

# Stripe CLI (clés réelles)
stripe listen --forward-to localhost:8080/api/stripe/webhook
stripe trigger checkout.session.completed
```

## Sécurité

- Carte CSSA / tiers-payant / claim refusés si statut ≠ `ACTIVE` (HTTP 402).
- Webhook sans signature valide → 400, aucune activation.
