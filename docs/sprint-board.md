# Sprint Board — MulemaCare Full Agentic (autonome)

> Canon : [`prd.md`](./prd.md) · [`prd-mcare.md`](./prd-mcare.md) · Stripe [`STRIPE_DIASPORA.md`](./STRIPE_DIASPORA.md)  
> Mis à jour : 2026-08-30 · **Mode : exécution autonome terminée** · Gate : `make qa-mulemacare` **GREEN**

## Carte jalons → sprints

| Jalon PRD | Sprint | Statut |
|-----------|--------|--------|
| J0 Stripe cash + secrets | **S1** | 🟢 Done (+ ops IONOS humain) |
| J1 Mutuelle OS skeleton | **S2** | 🟢 Done (health/JWT/DB/members) |
| J2 ActionCenter HITL | **S2.7** | 🟢 Done |
| J3 Agents lecture seule | **S3** | 🟢 Done |
| J4 Câblage PHP ↔ OS | **S4** | 🟢 Done |
| J5 ClaimsTriage + PartnerDesk | **S5** | 🟢 Done |
| J6 Bridge HealthOS | **S6** | 🟢 Done (OFF by default) |
| J7 Console polish | **S7** | 🟢 Done (PHP ops minimale) |
| J8 / MC0–MC5 MCare | **S8** | 🟢 Done (fondations vendables) |

---

## S0 — Kickoff & gouvernance (Done)

| Ticket | DoD |
|--------|-----|
| S0-1 PRD mutuelle agentic | `docs/prd.md` |
| S0-2 PRD MCare chat diaspora | `docs/prd-mcare.md` |
| S0-3 Stack PHP + FastAPI + Next later | documentée dans PRD |

---

## S1 — Cash Stripe diaspora 🟢 Done

| Ticket | Statut | Preuve |
|--------|--------|--------|
| S1-1 Secrets env | Done | `site/.env.example`, `DB_PASS` hors clair |
| S1-2 Checkout Subscription EUR/USD | Done | `StripePaymentService` |
| S1-3 PENDING→ACTIVE | Done | `MembershipService` |
| S1-4 Webhook signé | Done | `/api/stripe/webhook` |
| S1-5 UI adhésion redirect | Done | `adhesion.php`, footer modal |
| S1-6 Tests | Done | `php site/tests/test_stripe_*.php` PASS |

**Rollback :** `STRIPE_ENABLED=false`

---

## S2 — Mutuelle OS foundations 🟢 Done

| Ticket | Statut | Preuve |
|--------|--------|--------|
| S2-1 `/health` `/ready` | Done | `api/app/main.py` |
| S2-2 `cybernecs/mulemacare-api` compose | Done | `docker-compose.yml` |
| S2-3 JWT MEMBER/OPS/ADMIN | Done | `/api/v1/auth/*` |
| S2-4 SQLAlchemy members (SQLite/PG) | Done | `domain/models.py` |
| S2-5 MCare stub flag | Done | `MCARE_ENABLED` |
| S2-6 pytest OS | Done | `test_os_billing_mcare.py` |

---

## S2.7 — ActionCenter HITL 🟢 Done

| Ticket | DoD | Preuve |
|--------|-----|--------|
| HITL-1 Model `AgentProposal` | pending/approved/rejected/executed | `api/app/domain/models.py` |
| HITL-2 API create/list/decide | JWT OPS/ADMIN | `api/app/api/action_center.py` |
| HITL-3 claim/status/préauth → proposal | tests | `test_hitl_proposal_decide` PASS |

**Rollback :** ne pas appeler decide / flag OS OFF

---

## S3 — Agents lecture seule 🟢 Done

| Agent | Tools | HITL | Preuve |
|-------|-------|------|--------|
| QuoteAdvisor | grille plans déterministe | Non | `POST /api/v1/agents/quote-advisor` |
| EligibilityAgent | member status/plafonds | Non | `api/app/api/agents.py` |
| DiasporaCareNavigator | pays/devise/WhatsApp | Non | `test_agents_quote_and_navigator` PASS |

---

## S4 — Bridge PHP ↔ OS 🟢 Done

| Ticket | DoD | Preuve |
|--------|-----|--------|
| OsClient PHP | bearer vers `MULEMACARE_OS_URL` | `MutuelleOsClient.php` |
| Flag `MULEMACARE_OS_ENABLED` | OFF = site solo | `config.php` |
| Sync activate Stripe → OS members | best-effort | `MembershipService` activate hook |

---

## S5 — ClaimsTriage 🟢 Done

| Ticket | DoD | Preuve |
|--------|-----|--------|
| POST claim → proposal HITL | jamais auto-APPROVED | `test_claims_triage_creates_pending_proposal` |
| PartnerDesk eligibility text | tools only | agents + claims |

---

## S6 — HealthOS bridge 🟢 Done

| Ticket | DoD | Preuve |
|--------|-----|--------|
| OS endpoint eligibility proxy | stub path | `api/app/api/healthos.py` |
| Flag OFF default | `MULEMACARE_HEALTHOS_BRIDGE_ENABLED=false` | `test_healthos_off_by_default` |
| Préauth → HITL proposal | never auto-approve | action_center execute |

---

## S7 — Console ops minimale 🟢 Done

| Ticket | DoD | Preuve |
|--------|-----|--------|
| Page PHP `/espace-admin` proposals | list + approve/reject via OS | onglet ActionCenter HITL |
| Routes PHP OS | proxy | `GET/POST /api/os/proposals*` |
| Pas de Next.js full rewrite | Later | — |

---

## S8 — MCare vendable (MC0–MC5) 🟢 Done (fondations)

| MC | Ticket | Preuve |
|----|--------|--------|
| MC0 | Art contract tokens | `docs/MCARE_ART.md` |
| MC1 | Conversations + messages persist | `McareConversation` / `McareMessage` |
| MC2 | Tools couverture/réseau/carte | `api/app/api/mcare.py` déterministe |
| MC3 | Triage ClinCard + quotas | tags IA + `mcare_quota_remaining` |
| MC4 | Transmit → proposal HITL | `test_mcare_tools_and_transmit` |
| MC5 | SKU + CTA diaspora | `config mcare` + CTA `pays.php` |

---

## FE0–FE5 Frontend hubs + MCare 🟢 Done

| Sprint | Statut | Preuve |
|--------|--------|--------|
| FE0 tokens + ui-kit | Done | `assets/css/mulema-tokens.css` · `assets/js/ui-kit.js` |
| FE1 hub adhérent | Done | shell 5 vues · `/api/me*` |
| FE2 hub admin | Done | sidebar · `/api/admin/hub` · claims HITL |
| FE3 MCare chat | Done | `/mcare` · `/api/mcare/chat` · about SKU |
| FE4 acquisition | Done | CTA home/diaspora · borne sans alert verify |
| FE5 QA | Done | `test_hub_api` + `make qa-mulemacare` |

Backend hub : `HubApiController` — me/claims/coverage/network/admin/mcare.

## Gate QA globale — GREEN (2026-08-30)

```bash
make qa-mulemacare
# + SA0–SA5 auth: docs/plan-espaces-auth.md · docs/AUDIT_ESPACES_AUTH.md
```

## SA0–SA5 Auth espaces 🟢 Done

| Sprint | Statut | Preuve |
|--------|--------|--------|
| SA0 Art/threat | Done | `docs/ART_ESPACES.md` |
| SA1 Auth adhérent | Done | OTP + `/login/adherent` · `test_auth_espaces` |
| SA2 Auth admin 2FA | Done | Argon2id+TOTP+CSRF · `seed_admin.php` |
| SA3 Packing adhérent | Done | session-scoped · no démo PII |
| SA4 Packing admin+audit | Done | HITL proxy · `audit.jsonl` |
| SA5 QA + audit | Done | `make qa-mulemacare` GREEN · `docs/AUDIT_ESPACES_AUTH.md` |

## Ops humain restant (hors code)

1. Stripe live keys + webhook Dashboard → `https://mulemacare.com/api/stripe/webhook`
2. `DB_PASS` + `MULEMACARE_OS_*` sur IONOS
3. Rotation secrets éventuellement exposés

## Ordre exécuté

```text
S2.7 HITL → S3 Agents → S4 Bridge → S5 Claims → S6 HealthOS (OFF) → S7 UI ops → S8 MCare → QA GREEN
```
