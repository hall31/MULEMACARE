-- =============================================================================
-- Migration 0005 — preuve de propriété du domaine de marque blanche, lecture publique
-- restreinte aux organisations actives (CR-P3-02, correctif de vérificateur appliqué sur
-- instruction de Dajan — à valider).
--
-- STRICTEMENT ADDITIVE et REJOUABLE :
--   * deux colonnes nouvelles et nullables sur `organization_branding` (jeton de preuve propre au
--     domaine déclaré, instant de la preuve) ; aucune ligne réécrite : un domaine déjà déclaré
--     devient « en attente de vérification » (jeton absent : l'admin le réenregistre) ;
--   * deux contraintes nouvelles, vraies pour toute ligne existante (colonnes nulles) ;
--   * un déclencheur : une preuve ne s'hérite jamais (nouvelle ligne ou autre domaine) ;
--   * `resolve_organization_branding` remplacée (même signature, mêmes droits) : organisation
--     ACTIVE seulement (inconnue et non active : même absence de ligne), domaine servi et
--     résolu seulement s'il est prouvé.
-- Chaque instruction est gardée (IF NOT EXISTS, suppression puis recréation de la même
-- contrainte ou du même déclencheur, CREATE OR REPLACE, GRANT idempotent) : rejouer ce fichier
-- ne change rien. 0001 à 0004 restent inchangées.
-- =============================================================================

ALTER TABLE organization_branding ADD COLUMN IF NOT EXISTS custom_domain_token text;
ALTER TABLE organization_branding ADD COLUMN IF NOT EXISTS custom_domain_verified_at timestamptz;

ALTER TABLE organization_branding
  DROP CONSTRAINT IF EXISTS organization_branding_domain_token_check;
ALTER TABLE organization_branding ADD CONSTRAINT organization_branding_domain_token_check
  CHECK (custom_domain_token ~ '^[0-9a-f]{32}$');

ALTER TABLE organization_branding
  DROP CONSTRAINT IF EXISTS organization_branding_domain_proof_check;
ALTER TABLE organization_branding ADD CONSTRAINT organization_branding_domain_proof_check CHECK (
    (custom_domain IS NOT NULL
     OR (custom_domain_token IS NULL AND custom_domain_verified_at IS NULL))
    AND (custom_domain_verified_at IS NULL OR custom_domain_token IS NOT NULL));

CREATE OR REPLACE FUNCTION organization_branding_domain_reverify() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  -- Une preuve ne s'hérite pas : nouvelle ligne ou autre domaine = domaine à prouver.
  IF TG_OP = 'INSERT' THEN
    NEW.custom_domain_verified_at := NULL;
  ELSIF NEW.custom_domain IS DISTINCT FROM OLD.custom_domain THEN
    NEW.custom_domain_verified_at := NULL;
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS organization_branding_domain_reverify ON organization_branding;
CREATE TRIGGER organization_branding_domain_reverify
  BEFORE INSERT OR UPDATE ON organization_branding
  FOR EACH ROW EXECUTE FUNCTION organization_branding_domain_reverify();

CREATE OR REPLACE FUNCTION resolve_organization_branding(p_slug text, p_domain text)
RETURNS TABLE (slug text, name text, country_code text, currency text, display_name text,
               logo_kind text, logo_src text, theme jsonb, custom_domain text,
               legal_notice text, privacy_notice text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT o.slug, o.name, o.country_code::text, o.currency::text, b.display_name, b.logo_kind,
         b.logo_src, coalesce(b.theme, '{}'::jsonb),
         CASE WHEN b.custom_domain_verified_at IS NOT NULL THEN b.custom_domain END,
         b.legal_notice, b.privacy_notice
  FROM organizations o
  LEFT JOIN organization_branding b ON b.organization_id = o.id
  WHERE o.status = 'active'
    AND ((p_slug IS NOT NULL AND o.slug = p_slug)
      OR (p_domain IS NOT NULL AND b.custom_domain = p_domain
          AND b.custom_domain_verified_at IS NOT NULL))
$$;

REVOKE ALL ON FUNCTION resolve_organization_branding(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_organization_branding(text, text) TO mulema_app;
