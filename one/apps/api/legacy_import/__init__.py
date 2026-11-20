"""Import de l'existant en lecture seule (L11, R14) et mode ombre (L12, R15).

- ``importer`` : import DÉCLARATIF (``spec`` + ``specs``) depuis une source lue en lecture seule
  (export CSV, dump SQL, ou connexion MySQL gardée par ``readonly``) vers une organisation cible
  explicite, sous ``mulema_app`` (RLS forcée). À blanc par défaut ; ``apply`` explicite.
- ``reconcile`` : rapprochement source ↔ One (comptes, sommes, écarts par clé d'origine).
- ``shadow`` : rejoue des dossiers historiques dans ``api.rules.engine.evaluate`` et compare à
  la décision de la source ; n'écrit rien d'autre que son rapport.

Aucune donnée personnelle dans les journaux ni dans les rapports : identifiants d'origine,
codes et comptes seulement. Plan de migration : ``docs/MIGRATION_PLAN.md``.
"""
