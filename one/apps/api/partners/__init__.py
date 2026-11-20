"""Espaces assureur et employeur, accueil d'organisation (Phase 3, voie A, x-lot P3, CR-P3-01).

- ``privacy`` : k-anonymat (seuil 5, comme ``api.metrics``) et protection contre la soustraction ;
- ``repository`` : seul endroit SQL ; chaque requête filtre ``organization_id`` elle-même ;
- ``service`` : portefeuille assureur, export CSV, consommation et contrats employeur ;
- ``onboarding`` : gabarits de configuration et ``createOrganization`` (copie, jamais partage) ;
- ``routes.install(app, runtime)`` : opérations des tags ``espace-assureur``,
  ``espace-employeur`` et ``plateforme``.
"""
