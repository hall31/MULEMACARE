"""Noyau (lot L1) : organisations, utilisateurs, rôles, permissions, audit.

Points d'entrée pour les autres lots :
- ``api.core.app.create_app(settings, identity_provider=..., routers=[...])`` ;
- ``api.core.context.require_operation("<operationId>")`` : dépendance FastAPI qui injecte
  l'organisation du jeton (``SET LOCAL``) et contrôle le rôle ; ``RequestContext.session`` ;
- ``api.core.permissions.authorize(principal, op, ResourceScope(...))`` : contrôle par attribut ;
- ``api.core.services.AuditService.for_session(session).record(ctx, AuditIntent(...))`` ;
- ``api.core.medical.MedicalReasonAccess`` : seul passage vers le motif médical (R6) ;
- ``api.core.errors`` : erreurs typées à code stable, rendues en problem+json.
"""
