"""Mesure produit (Phase 2, voie B, x-lot P2, CR-P2-01, CR-P2-02).

- ``catalog`` : liste blanche FERMÉE des événements d'usage, règles par événement (durée
  comprise), empreinte HMAC de la PERSONNE avec une clé du serveur (aucun identifiant en clair,
  aucun texte libre, rien du client) ;
- ``windows`` : semaines civiles entières et terminées, seules publiées (anti-recoupement) ;
- ``privacy`` : seuil de k-anonymat (5) par période ET par semaine, effectifs par palier,
  arithmétique entière des agrégats ;
- ``repository`` : seul endroit SQL du module ; chaque requête filtre ``organization_id``
  elle-même, en plus de la RLS forcée ;
- ``service`` : ``recordProductEvent`` et ``getProductMetrics`` ;
- ``routes.install(app, runtime)`` : opérations du tag ``mesure`` ;
- ``jobs`` : purge des événements expirés (``python -m api.metrics purge``), rétention et clé
  dans ``runtime.MetricsRuntime``.

Aucun traceur tiers : les événements restent dans la base de l'instance (R9).
"""
