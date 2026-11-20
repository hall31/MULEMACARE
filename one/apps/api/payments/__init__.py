"""Cotisations et paiements (lot L4, R2, R8) — canaux SIMULÉS uniquement (PRD §10 Q1).

- ``routes.install(app, PaymentsRuntime(...))`` : opérations ``cotisations`` de specs/openapi.yaml ;
- ``channels`` : interface ``PaymentChannel`` et canaux simulés Wave, Orange Money, MTN MoMo ;
- ``webhooks`` : signature, idempotence, ``contribution.received`` et réouverture des droits ;
- ``jobs.issue_month`` : émission mensuelle des cotisations.
"""
