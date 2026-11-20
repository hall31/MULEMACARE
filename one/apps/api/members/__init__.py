"""Adhésions (lot L4, R2) : adhérents, ayants droit, statuts, cartes à QR dynamique.

- ``routes.install(app, MembersRuntime(...))`` : opérations ``adherents`` de specs/openapi.yaml ;
- ``status`` : R-01 en données, transitions et événement ``member.status_changed`` ;
- ``jobs.run_daily`` : fin de carence et suspension automatique à J+45 d'impayé (R8) ;
- ``cards.verify_qr_payload`` : vérification du QR dynamique pour le comptoir (L5) ;
- ``idempotency`` et ``outbox`` : clés stockées et boîte d'envoi, partagées avec ``payments``.
"""
