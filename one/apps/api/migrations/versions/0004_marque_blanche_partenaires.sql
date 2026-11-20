-- =============================================================================
-- Migration 0004 — marque blanche, espaces assureur et employeur, accueil d'organisation
-- (Phase 3, voie A, CR-P3-01, appliqué sur instruction de Dajan pour enchaîner les phases —
-- à valider).
--
-- STRICTEMENT ADDITIVE et REJOUABLE :
--   * trois listes fermées ÉLARGIES (tout ce qui était accepté l'est encore, aucune ligne
--     réécrite) : capacité `plateforme` (organisations), rôles `assureur` et `admin_plateforme`
--     (user_roles, product_events) ;
--   * garde de base : `admin_plateforme` n'existe que dans une organisation `plateforme` ;
--   * deux tables nouvelles, chacune avec `organization_id`, RLS activée ET forcée, politique
--     unique `tenant_isolation` : `organization_branding` (une ligne par organisation, liste
--     fermée de jetons vérifiée par la base) et `configuration_templates` (gabarits versionnés,
--     en ajout seul) ;
--   * deux fonctions SECURITY DEFINER limitées au strict nécessaire, réservées à `mulema_app` :
--     lecture publique de la marque (champs non sensibles) et création d'organisation par un
--     administrateur de plateforme (vérifié par la base).
-- Chaque instruction est gardée (IF NOT EXISTS, CREATE OR REPLACE, suppression puis recréation
-- de la même contrainte ou du même déclencheur, politique créée si absente, GRANT idempotent) :
-- rejouer ce fichier ne change rien. 0001, 0002 et 0003 restent inchangées.
-- =============================================================================

-- --- Listes fermées élargies ------------------------------------------------------------------

ALTER TABLE organizations DROP CONSTRAINT IF EXISTS organizations_capabilities_check;
ALTER TABLE organizations ADD CONSTRAINT organizations_capabilities_check CHECK (
  cardinality(capabilities) > 0
  AND capabilities <@ ARRAY['porteur_de_risque', 'gestionnaire', 'distributeur',
                            'plateforme']::text[]);

ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_role_check;
ALTER TABLE user_roles ADD CONSTRAINT user_roles_role_check
  CHECK (role IN ('gestionnaire', 'medecin_conseil', 'clinique', 'employeur', 'admin',
                  'adherent', 'assureur', 'admin_plateforme'));

ALTER TABLE product_events DROP CONSTRAINT IF EXISTS product_events_role_check;
ALTER TABLE product_events ADD CONSTRAINT product_events_role_check
  CHECK (role IN ('gestionnaire', 'medecin_conseil', 'clinique', 'employeur', 'admin',
                  'adherent', 'assureur', 'admin_plateforme'));

-- --- Administrateur de plateforme : seulement dans une organisation « plateforme » -----------

CREATE OR REPLACE FUNCTION user_roles_platform_admin_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.role = 'admin_plateforme' AND NOT EXISTS (
    SELECT 1 FROM organizations
    WHERE id = NEW.organization_id AND 'plateforme' = ANY (capabilities)
  ) THEN
    RAISE EXCEPTION USING
      ERRCODE = 'MCP01',
      MESSAGE = 'Le rôle admin_plateforme est réservé à une organisation « plateforme ».';
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS user_roles_platform_admin_guard ON user_roles;
CREATE TRIGGER user_roles_platform_admin_guard
  BEFORE INSERT OR UPDATE ON user_roles
  FOR EACH ROW EXECUTE FUNCTION user_roles_platform_admin_guard();

-- --- Marque blanche ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION branding_theme_is_closed(p_theme jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
  t record;
  k record;
BEGIN
  IF jsonb_typeof(p_theme) IS DISTINCT FROM 'object' THEN
    RETURN false;
  END IF;
  FOR t IN SELECT key, value FROM jsonb_each(p_theme) LOOP
    IF t.key NOT IN ('light', 'dark') OR jsonb_typeof(t.value) <> 'object' THEN
      RETURN false;
    END IF;
    FOR k IN SELECT key, value FROM jsonb_each(t.value) LOOP
      IF k.key NOT IN ('accent', 'accent_hover', 'accent_fg', 'brand_deep')
         OR jsonb_typeof(k.value) <> 'string'
         OR (k.value #>> '{}') !~ '^#[0-9a-f]{6}$' THEN
        RETURN false;
      END IF;
    END LOOP;
  END LOOP;
  RETURN true;
END
$$;

CREATE TABLE IF NOT EXISTS organization_branding (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  display_name     text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 80
                                        AND display_name !~ '[<>[:cntrl:]]'),
  logo_kind        text CHECK (logo_kind IN ('url', 'data_uri')),
  logo_src         text CHECK (length(logo_src) <= 43800),
  theme            jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (branding_theme_is_closed(theme)),
  custom_domain    text UNIQUE CHECK (length(custom_domain) <= 253 AND custom_domain
                                      ~ '^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$'),
  legal_notice     text CHECK (length(legal_notice) <= 4000 AND legal_notice !~ '[<>]'),
  privacy_notice   text CHECK (length(privacy_notice) <= 4000 AND privacy_notice !~ '[<>]'),
  updated_by       uuid,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CHECK ((logo_kind IS NULL) = (logo_src IS NULL)),
  CHECK (logo_kind IS DISTINCT FROM 'url' OR logo_src ~ '^(/[^/]|https://)'),
  CHECK (logo_kind IS DISTINCT FROM 'data_uri'
         OR logo_src ~ '^data:image/(png|webp|jpeg|svg\+xml);base64,[A-Za-z0-9+/]+={0,2}$'),
  UNIQUE (organization_id),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, updated_by) REFERENCES users (organization_id, id)
);
CREATE INDEX IF NOT EXISTS organization_branding_updated_by_idx
  ON organization_branding (organization_id, updated_by);

-- --- Gabarits de configuration (produits, règles, barème, plan de comptes) --------------------

CREATE TABLE IF NOT EXISTS configuration_templates (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  code             text NOT NULL CHECK (code ~ '^[a-z0-9][a-z0-9-]{1,39}$'),
  version          integer NOT NULL CHECK (version > 0),
  country_code     char(2) NOT NULL CHECK (country_code IN ('CI', 'SN')),
  label            text NOT NULL CHECK (length(label) BETWEEN 1 AND 120),
  payload          jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
  created_by       uuid NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, code, version),
  FOREIGN KEY (organization_id, created_by) REFERENCES users (organization_id, id)
);
CREATE INDEX IF NOT EXISTS configuration_templates_created_by_idx
  ON configuration_templates (organization_id, created_by);

DROP TRIGGER IF EXISTS configuration_templates_append_only ON configuration_templates;
CREATE TRIGGER configuration_templates_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON configuration_templates
  FOR EACH STATEMENT
  EXECUTE FUNCTION forbid_mutation('Publiez une nouvelle version du gabarit.');

-- --- Isolation : RLS forcée, politique unique ---------------------------------------------------

ALTER TABLE organization_branding ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_branding FORCE ROW LEVEL SECURITY;
ALTER TABLE configuration_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE configuration_templates FORCE ROW LEVEL SECURITY;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['organization_branding', 'configuration_templates'] LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname = current_schema() AND tablename = t AND policyname = 'tenant_isolation'
    ) THEN
      EXECUTE format(
        'CREATE POLICY tenant_isolation ON %I '
        'USING (organization_id = app_current_organization_id()) '
        'WITH CHECK (organization_id = app_current_organization_id())', t);
    END IF;
  END LOOP;
END
$$;

-- --- Résolutions sans contexte ------------------------------------------------------------------

-- Marque publique d'une organisation, par identifiant public ou par domaine : champs non
-- sensibles seulement (aucun identifiant interne, aucun utilisateur, aucune donnée métier).
CREATE OR REPLACE FUNCTION resolve_organization_branding(p_slug text, p_domain text)
RETURNS TABLE (slug text, name text, country_code text, currency text, display_name text,
               logo_kind text, logo_src text, theme jsonb, custom_domain text,
               legal_notice text, privacy_notice text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT o.slug, o.name, o.country_code::text, o.currency::text, b.display_name, b.logo_kind,
         b.logo_src, coalesce(b.theme, '{}'::jsonb), b.custom_domain, b.legal_notice,
         b.privacy_notice
  FROM organizations o
  LEFT JOIN organization_branding b ON b.organization_id = o.id
  WHERE o.status <> 'inactive'
    AND ((p_slug IS NOT NULL AND o.slug = p_slug)
      OR (p_domain IS NOT NULL AND b.custom_domain = p_domain))
$$;

-- Création d'une organisation accueillie, par un administrateur ACTIF d'une organisation
-- « plateforme » ACTIVE (vérifié ici, en plus de la matrice de l'API). Nouvelle organisation en
-- statut `integration`, jamais « plateforme ». MCP01 : refusé ; MCP02 : identifiant déjà pris.
CREATE OR REPLACE FUNCTION platform_create_organization(
  p_actor uuid, p_slug text, p_name text, p_country_code text, p_timezone text,
  p_capabilities text[], p_regulator text)
RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  caller uuid := app_current_organization_id();
  created uuid;
BEGIN
  IF caller IS NULL OR NOT EXISTS (
    SELECT 1
    FROM user_roles ur
    JOIN users u ON u.organization_id = ur.organization_id AND u.id = ur.user_id
    JOIN organizations o ON o.id = ur.organization_id
    WHERE ur.organization_id = caller AND ur.user_id = p_actor
      AND ur.role = 'admin_plateforme' AND u.status = 'active' AND o.status = 'active'
      AND 'plateforme' = ANY (o.capabilities)
  ) THEN
    RAISE EXCEPTION USING
      ERRCODE = 'MCP01',
      MESSAGE = 'Création d''organisation réservée à un administrateur de plateforme.';
  END IF;
  IF 'plateforme' = ANY (p_capabilities) THEN
    RAISE EXCEPTION USING
      ERRCODE = 'MCP01',
      MESSAGE = 'Une organisation accueillie ne reçoit pas la capacité plateforme.';
  END IF;
  BEGIN
    INSERT INTO organizations (slug, name, country_code, timezone, capabilities, regulator,
                               status)
    VALUES (p_slug, p_name, p_country_code, p_timezone, p_capabilities, p_regulator,
            'integration')
    RETURNING id INTO created;
  EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION USING
      ERRCODE = 'MCP02',
      MESSAGE = 'Identifiant public d''organisation déjà utilisé.';
  END;
  RETURN created;
END
$$;

-- --- Droits de mulema_app -----------------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE ON organization_branding TO mulema_app;
GRANT SELECT, INSERT ON configuration_templates TO mulema_app;
REVOKE UPDATE, DELETE, TRUNCATE ON configuration_templates FROM mulema_app;

REVOKE ALL ON FUNCTION resolve_organization_branding(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_create_organization(uuid, text, text, text, text, text[], text)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_organization_branding(text, text) TO mulema_app;
GRANT EXECUTE ON FUNCTION platform_create_organization(uuid, text, text, text, text, text[], text)
  TO mulema_app;
