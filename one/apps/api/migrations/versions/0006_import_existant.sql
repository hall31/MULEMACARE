-- =============================================================================
-- Migration 0006 — import de l'existant en lecture seule (L11, R14 ; ADR-006 ; CR-L11-01,
-- appliqué sur instruction de Dajan — à valider).
--
-- STRICTEMENT ADDITIVE et REJOUABLE : deux tables nouvelles, aucune table existante touchée,
-- aucune ligne réécrite.
--   * `import_runs` : journal des imports appliqués (un import à blanc n'écrit RIEN, pas même
--     ce journal). Devise de la source égale à celle de l'organisation (déclencheur, MCI01) ;
--     un import terminé ou échoué est figé (MCI02).
--   * `external_ids` : clé d'origine (source, type, clé) → ligne de One. Ajout seul ; unicité
--     (organisation, source, type, clé) : rejouer un import ne crée aucun doublon. Une adresse
--     électronique n'est jamais une clé (CHECK). La ligne de One visée doit exister dans la même
--     organisation (déclencheur, MCI03).
-- Chaque instruction est gardée (IF NOT EXISTS, CREATE OR REPLACE, DROP … IF EXISTS puis
-- recréation à l'identique, GRANT idempotent) : rejouer ce fichier ne change rien.
-- 0001 à 0005 restent inchangées.
-- =============================================================================

CREATE TABLE IF NOT EXISTS import_runs (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id     uuid NOT NULL REFERENCES organizations (id),
  source              text NOT NULL CHECK (source ~ '^[a-z][a-z0-9_]{1,39}$'),
  spec_version        text NOT NULL CHECK (spec_version ~ '^[a-z0-9][a-z0-9._-]{0,39}$'),
  status_map_version  text NOT NULL CHECK (status_map_version ~ '^[a-z0-9][a-z0-9._-]{0,39}$'),
  source_currency     char(3) NOT NULL CHECK (source_currency ~ '^[A-Z]{3}$'),
  status              text NOT NULL DEFAULT 'en_cours'
                        CHECK (status IN ('en_cours', 'terminee', 'echouee')),
  batches_committed   integer NOT NULL DEFAULT 0 CHECK (batches_committed >= 0),
  rows_inserted       integer NOT NULL DEFAULT 0 CHECK (rows_inserted >= 0),
  rows_rejected       integer NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
  failure_code        text CHECK (failure_code ~ '^[A-Z]{3}-[0-9]{2}$'),
  started_at          timestamptz NOT NULL DEFAULT now(),
  finished_at         timestamptz,
  CONSTRAINT import_runs_finished_check CHECK ((status = 'en_cours') = (finished_at IS NULL)),
  CONSTRAINT import_runs_failure_check CHECK ((status = 'echouee') = (failure_code IS NOT NULL)),
  UNIQUE (organization_id, id)
);

CREATE TABLE IF NOT EXISTS external_ids (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id     uuid NOT NULL REFERENCES organizations (id),
  source              text NOT NULL CHECK (source ~ '^[a-z][a-z0-9_]{1,39}$'),
  kind                text NOT NULL CHECK (kind IN ('person', 'member', 'dependent', 'plan',
                                                    'plan_version', 'coverage', 'provider',
                                                    'claim', 'contribution')),
  key_name            text NOT NULL CHECK (key_name ~ '^[a-z][a-z0-9_]{1,39}$'),
  external_key        text NOT NULL,
  one_id              uuid NOT NULL,
  import_run_id       uuid NOT NULL,
  import_status       text CHECK (import_status ~ '^[A-Z][A-Z_]{1,39}$'),
  status_map_version  text CHECK (status_map_version ~ '^[a-z0-9][a-z0-9._-]{0,39}$'),
  created_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT external_ids_key_check CHECK (
    length(external_key) <= 240
    AND starts_with(external_key, key_name || ':')
    AND length(external_key) > length(key_name) + 1
    AND position('@' IN external_key) = 0),
  CONSTRAINT external_ids_status_check CHECK (
    (import_status IS NULL) = (status_map_version IS NULL)
    AND (kind = 'member' OR import_status IS NULL)),
  UNIQUE (organization_id, id),
  CONSTRAINT external_ids_unique_key UNIQUE (organization_id, source, kind, external_key),
  CONSTRAINT external_ids_run_fk FOREIGN KEY (organization_id, import_run_id)
    REFERENCES import_runs (organization_id, id)
);
CREATE INDEX IF NOT EXISTS external_ids_one_idx ON external_ids (organization_id, kind, one_id);
CREATE INDEX IF NOT EXISTS external_ids_run_idx ON external_ids (organization_id, import_run_id);

CREATE OR REPLACE FUNCTION import_runs_currency_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  -- La devise de la source est déclarée, jamais devinée, et jamais convertie (ADR-005).
  IF NEW.source_currency IS DISTINCT FROM (
    SELECT currency FROM organizations WHERE id = NEW.organization_id
  ) THEN
    RAISE EXCEPTION USING
      ERRCODE = 'MCI01',
      MESSAGE = 'Devise de la source différente de celle de l''organisation : import refusé.';
  END IF;
  RETURN NEW;
END
$$;

CREATE OR REPLACE FUNCTION import_runs_progress_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status <> 'en_cours'
     OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
     OR NEW.source IS DISTINCT FROM OLD.source
     OR NEW.spec_version IS DISTINCT FROM OLD.spec_version
     OR NEW.status_map_version IS DISTINCT FROM OLD.status_map_version
     OR NEW.source_currency IS DISTINCT FROM OLD.source_currency
     OR NEW.started_at IS DISTINCT FROM OLD.started_at
     OR NEW.batches_committed < OLD.batches_committed THEN
    RAISE EXCEPTION USING
      ERRCODE = 'MCI02',
      MESSAGE = 'Journal d''import figé : seul un import en cours avance.';
  END IF;
  RETURN NEW;
END
$$;

CREATE OR REPLACE FUNCTION external_ids_target_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  target text := CASE NEW.kind
    WHEN 'person' THEN 'persons'
    WHEN 'member' THEN 'members'
    WHEN 'dependent' THEN 'dependents'
    WHEN 'plan' THEN 'plans'
    WHEN 'plan_version' THEN 'plan_versions'
    WHEN 'coverage' THEN 'coverages'
    WHEN 'provider' THEN 'providers'
    WHEN 'claim' THEN 'claims'
    WHEN 'contribution' THEN 'contributions'
  END;
  found boolean;
BEGIN
  EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I WHERE organization_id = $1 AND id = $2)',
                 target)
    INTO found USING NEW.organization_id, NEW.one_id;
  IF NOT found THEN
    RAISE EXCEPTION USING
      ERRCODE = 'MCI03',
      MESSAGE = format('Clé d''origine orpheline : aucune ligne %s visée.', target);
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS import_runs_currency_guard ON import_runs;
CREATE TRIGGER import_runs_currency_guard
  BEFORE INSERT ON import_runs
  FOR EACH ROW EXECUTE FUNCTION import_runs_currency_guard();

DROP TRIGGER IF EXISTS import_runs_progress_guard ON import_runs;
CREATE TRIGGER import_runs_progress_guard
  BEFORE UPDATE ON import_runs
  FOR EACH ROW EXECUTE FUNCTION import_runs_progress_guard();

DROP TRIGGER IF EXISTS external_ids_target_guard ON external_ids;
CREATE TRIGGER external_ids_target_guard
  BEFORE INSERT ON external_ids
  FOR EACH ROW EXECUTE FUNCTION external_ids_target_guard();

DROP TRIGGER IF EXISTS external_ids_append_only ON external_ids;
CREATE TRIGGER external_ids_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON external_ids
  FOR EACH STATEMENT
  EXECUTE FUNCTION forbid_mutation('Une clé d''origine ne change pas.');

ALTER TABLE import_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON import_runs;
CREATE POLICY tenant_isolation ON import_runs
  USING (organization_id = app_current_organization_id())
  WITH CHECK (organization_id = app_current_organization_id());

ALTER TABLE external_ids ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_ids FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON external_ids;
CREATE POLICY tenant_isolation ON external_ids
  USING (organization_id = app_current_organization_id())
  WITH CHECK (organization_id = app_current_organization_id());

-- Journal : lecture, création, avancement (garde ci-dessus) ; clés : ajout seul.
GRANT SELECT, INSERT, UPDATE ON import_runs TO mulema_app;
GRANT SELECT, INSERT ON external_ids TO mulema_app;
REVOKE UPDATE, DELETE, TRUNCATE ON external_ids FROM mulema_app;
