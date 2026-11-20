"""Espace adhérent et diaspora (Phase 1, x-lot P1, CR-P1-01).

- ``routes.install(app)`` : opérations ``espace-adherent`` de specs/openapi.yaml (rôle adherent) ;
- ``service`` : ma carte (QR dynamique, droits, plafond restant), mes bénéficiaires, mes soins
  et leur frise, mes cotisations, « inviter un proche à payer » ;
- ``repository`` : lecture filtrée par organisation ET par contrat de l'adhérent ;
- ``tracking`` : frise d'un remboursement (fonction pure).
"""
