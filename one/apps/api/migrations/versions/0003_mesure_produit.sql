-- =============================================================================
-- Migration 0003 — mesure produit (Phase 2, voie B, CR-P2-01, appliqué sur instruction de
-- Dajan pour enchaîner les phases — à valider).
--
-- STRICTEMENT ADDITIVE et REJOUABLE :
--   * une table nouvelle `product_events` (aucune table existante touchée, aucune ligne
--     réécrite) ; mêmes définitions que specs/schema.sql ;
--   * RLS activée ET forcée, avec la même et unique politique `tenant_isolation` que les
--     autres tables (la boucle de 0001 ne s'applique qu'aux tables qui existaient alors) ;
--   * droits de `mulema_app` : SELECT, INSERT, DELETE (purge par rétention), jamais UPDATE.
-- Chaque instruction est gardée (IF NOT EXISTS, politique créée si absente, GRANT idempotent) :
-- rejouer ce fichier ne change rien.
-- =============================================================================

CREATE TABLE IF NOT EXISTS product_events (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  name             text NOT NULL CHECK (name IN ('onboarding_started', 'onboarding_step',
                                                 'onboarding_completed', 'card_presented',
                                                 'counter_decision_shown',
                                                 'payment_link_created', 'palette_opened',
                                                 'joe_question_asked', 'notification_opened',
                                                 'offline_banner_seen',
                                                 'claim_tracking_viewed')),
  surface          text NOT NULL CHECK (surface IN ('console', 'comptoir', 'espace_adherent')),
  role             text NOT NULL CHECK (role IN ('gestionnaire', 'medecin_conseil', 'clinique',
                                                 'employeur', 'admin', 'adherent')),
  session_ref      text NOT NULL CHECK (session_ref ~ '^[0-9a-f]{64}$'),
  duration_ms      integer CHECK (duration_ms BETWEEN 0 AND 86400000),
  step             smallint CHECK (step BETWEEN 1 AND 20),
  variant          text CHECK (variant IN ('en_ligne', 'hors_ligne', 'accordee', 'revue',
                                           'refusee', 'clavier', 'bouton', 'exemple', 'saisie',
                                           'sms', 'whatsapp', 'in_app')),
  occurred_at      timestamptz NOT NULL,
  expires_at       timestamptz NOT NULL,
  CHECK (expires_at > occurred_at),
  UNIQUE (organization_id, id)
);
CREATE INDEX IF NOT EXISTS product_events_name_idx ON product_events (organization_id, name, occurred_at);
CREATE INDEX IF NOT EXISTS product_events_expiry_idx ON product_events (organization_id, expires_at);

ALTER TABLE product_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_events FORCE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = current_schema() AND tablename = 'product_events'
      AND policyname = 'tenant_isolation'
  ) THEN
    CREATE POLICY tenant_isolation ON product_events
      USING (organization_id = app_current_organization_id())
      WITH CHECK (organization_id = app_current_organization_id());
  END IF;
END
$$;

GRANT SELECT, INSERT, DELETE ON product_events TO mulema_app;
