-- =============================================================================
-- MulemaCare One — contrat de schéma de la base logique `insurance` (PostgreSQL 16)
-- Lot L0 · 2026-09-30 · brouillon à relire par un humain avant le démarrage des lots.
--
-- Ce fichier est un CONTRAT. Toute modification passe par specs/CHANGE-REQUESTS.md.
-- Appliqué tel quel par la migration Alembic 0001 (apps/api/migrations), puis complété par les
-- migrations additives 0002+ (0002 : rôle adherent, CR-P1-01 ; 0003 : mesure produit,
-- CR-P2-01 ; 0004 : marque blanche, assureur, employeur, accueil, CR-P3-01 ; 0005 : preuve de
-- domaine, CR-P3-02 ; 0006 : import de l'existant, CR-L11-01). État final = toutes les
-- migrations.
--
-- Invariants portés par la base (AGENTS.md, PRD §4) :
--   * Secret médical (R6) : aucune colonne de diagnostic, de motif médical ou de prescription.
--     Le motif se lit à la demande chez HealthOS via `claims.healthos_encounter_ref`
--     (référence pseudonyme) ; chaque lecture crée une ligne `audit_events`.
--   * Isolation (R10) : `organization_id uuid NOT NULL` sur toute table métier, clés étrangères
--     composites (organization_id, x_id) pour interdire toute référence inter-organisations,
--     Row Level Security filtrée par `app.organization_id` (voir fin de fichier).
--   * Argent : montants en entiers FCFA (`bigint`, colonnes suffixées `_xof`), devise explicite
--     `currency = 'XOF'` (CI et SN partagent le franc CFA UEMOA). Aucun flottant.
--   * Grand livre (R7) : `ledger_entries` / `ledger_lines` en ajout seul (UPDATE, DELETE,
--     TRUNCATE refusés), débits = crédits vérifié au COMMIT, lignes ajoutées uniquement dans
--     la transaction qui crée l'écriture. Correction = contre-passation.
--   * Règles et produits versionnés (R3) : une version publiée est figée ; les versions
--     publiées d'un même produit / d'une même règle ne se chevauchent pas.
--   * Dates en UTC (`timestamptz`), dates de soin et d'effet en `date` (jour civil local).
--
-- Codes SQLSTATE propres au contrat (classe « MC ») :
--   MCL01  modification ou suppression d'une table en ajout seul
--   MCL02  écriture comptable déséquilibrée ou de moins de deux lignes
--   MCL03  ligne ajoutée à une écriture déjà validée
--   MCL04  contre-passation qui n'est pas le miroir exact de l'écriture d'origine
--   MCR01  modification d'une version de produit ou de règle déjà publiée
--   MCR02  chevauchement de périodes entre versions publiées
--
-- Le rôle applicatif ne doit PAS être propriétaire des tables (la RLS ne s'applique pas au
-- propriétaire et seul le propriétaire peut désactiver les déclencheurs). Voir QUESTIONS.md.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Fonctions communes
-- -----------------------------------------------------------------------------

-- Organisation de la requête en cours, positionnée par l'API (SET LOCAL app.organization_id).
-- Non positionnée => NULL => aucune ligne visible (échec fermé).
CREATE FUNCTION app_current_organization_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.organization_id', true), '')::uuid
$$;

-- Refus générique pour les tables en ajout seul (déclencheur de niveau instruction :
-- il se déclenche même si aucune ligne n'est touchée).
CREATE FUNCTION forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION USING
    ERRCODE = 'MCL01',
    MESSAGE = format('Table %s en ajout seul : %s interdit.', TG_TABLE_NAME, TG_OP),
    HINT = coalesce(TG_ARGV[0], 'Ajoutez une nouvelle ligne au lieu de modifier l''existante.');
END
$$;

-- Une version publiée (état différent de « brouillon ») est figée, sauf son état, sa date de
-- fin (une seule fois, si elle était ouverte) et les champs d'approbation.
CREATE FUNCTION freeze_published_version() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  mutable_keys text[] := ARRAY['state', 'valid_to', 'approved_by', 'approved_at'];
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.state <> 'brouillon' THEN
      RAISE EXCEPTION USING ERRCODE = 'MCR01',
        MESSAGE = format('%s : une version publiée ne se supprime pas.', TG_TABLE_NAME);
    END IF;
    RETURN OLD;
  END IF;

  IF OLD.state <> 'brouillon' THEN
    IF (to_jsonb(NEW) - mutable_keys) IS DISTINCT FROM (to_jsonb(OLD) - mutable_keys)
       OR NEW.state = 'brouillon'
       OR (OLD.valid_to IS NOT NULL AND NEW.valid_to IS DISTINCT FROM OLD.valid_to) THEN
      RAISE EXCEPTION USING ERRCODE = 'MCR01',
        MESSAGE = format('%s : une version publiée est figée. Créez une nouvelle version.',
                         TG_TABLE_NAME);
    END IF;
  END IF;
  RETURN NEW;
END
$$;

-- Les versions publiées d'un même parent (produit ou règle) ne se chevauchent pas, pour
-- qu'une date de soin désigne une et une seule version (R3).
-- TG_ARGV[0] = colonne parent (plan_id | rule_id), TG_ARGV[1] = table parent (verrouillée).
CREATE FUNCTION forbid_overlapping_versions() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  parent_id uuid;
  clash boolean;
BEGIN
  IF NEW.state = 'brouillon' THEN
    RETURN NEW;
  END IF;
  EXECUTE format('SELECT ($1).%I', TG_ARGV[0]) INTO parent_id USING NEW;
  EXECUTE format('SELECT 1 FROM %I WHERE id = $1 FOR UPDATE', TG_ARGV[1]) USING parent_id;
  EXECUTE format(
    'SELECT EXISTS (SELECT 1 FROM %I WHERE organization_id = $1 AND %I = $2 AND id <> $3 '
    'AND state <> ''brouillon'' '
    'AND daterange(valid_from, valid_to, ''[]'') && daterange($4, $5, ''[]''))',
    TG_TABLE_NAME, TG_ARGV[0])
  INTO clash
  USING NEW.organization_id, parent_id, NEW.id, NEW.valid_from, NEW.valid_to;
  IF clash THEN
    RAISE EXCEPTION USING ERRCODE = 'MCR02',
      MESSAGE = format('%s : la période chevauche une version déjà publiée.', TG_TABLE_NAME);
  END IF;
  RETURN NEW;
END
$$;

-- Montant en francs CFA : entier positif ou nul.
CREATE DOMAIN amount_xof AS bigint CHECK (VALUE >= 0);

-- -----------------------------------------------------------------------------
-- Organisations, utilisateurs, rôles (L1)
-- -----------------------------------------------------------------------------

CREATE TABLE organizations (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                        text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
  name                        text NOT NULL,
  country_code                char(2) NOT NULL CHECK (country_code IN ('CI', 'SN')),
  timezone                    text NOT NULL CHECK (timezone IN ('Africa/Abidjan', 'Africa/Dakar')),
  currency                    char(3) NOT NULL DEFAULT 'XOF' CHECK (currency = 'XOF'),
  -- Rôles joués par l'organisation (prototype « Porteurs de risque ») ; `plateforme` :
  -- exploite l'instance et accueille d'autres organisations (Phase 3, migration 0004).
  capabilities                text[] NOT NULL CHECK (
                                cardinality(capabilities) > 0
                                AND capabilities <@ ARRAY['porteur_de_risque', 'gestionnaire',
                                                          'distributeur',
                                                          'plateforme']::text[]),
  -- Assureur en gestion déléguée : organisation gestionnaire (modèle seul, PRD §2).
  managed_by_organization_id  uuid REFERENCES organizations (id),
  regulator                   text,
  status                      text NOT NULL DEFAULT 'active'
                                CHECK (status IN ('active', 'integration', 'inactive')),
  created_at                  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX organizations_managed_by_idx ON organizations (managed_by_organization_id);

CREATE TABLE users (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  -- Identifiant chez le fournisseur d'identité (non choisi, PRD §10 Q2).
  idp_subject      text NOT NULL,
  display_name     text NOT NULL,
  email            text,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, idp_subject)
);

CREATE TABLE employers (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  name             text NOT NULL,
  contract_start   date NOT NULL,
  contract_end     date CHECK (contract_end IS NULL OR contract_end >= contract_start),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id)
);

-- -----------------------------------------------------------------------------
-- Réseau de soins (L2 : règle R-04)
-- -----------------------------------------------------------------------------

CREATE TABLE providers (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id       uuid NOT NULL REFERENCES organizations (id),
  name                  text NOT NULL,
  kind                  text NOT NULL CHECK (kind IN ('clinique', 'hopital', 'pharmacie',
                                                      'laboratoire', 'imagerie', 'cabinet')),
  city                  text NOT NULL,
  country_code          char(2) NOT NULL CHECK (country_code IN ('CI', 'SN')),
  status                text NOT NULL DEFAULT 'actif' CHECK (status IN ('actif', 'suspendu')),
  -- Référence de l'établissement chez HealthOS (L9).
  healthos_facility_ref text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id)
);

-- Convention (conventionnement) d'un prestataire sur une période.
CREATE TABLE provider_conventions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  provider_id      uuid NOT NULL,
  valid_from       date NOT NULL,
  valid_to         date CHECK (valid_to IS NULL OR valid_to >= valid_from),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, provider_id, valid_from),
  FOREIGN KEY (organization_id, provider_id) REFERENCES providers (organization_id, id)
);

-- Appareil de comptoir enregistré (clé publique pour les accords provisoires hors ligne, R13).
CREATE TABLE counter_devices (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  provider_id      uuid NOT NULL,
  label            text NOT NULL,
  public_key       text NOT NULL,
  status           text NOT NULL DEFAULT 'actif' CHECK (status IN ('actif', 'revoque')),
  registered_at    timestamptz NOT NULL DEFAULT now(),
  revoked_at       timestamptz,
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, provider_id) REFERENCES providers (organization_id, id)
);
CREATE INDEX counter_devices_provider_idx ON counter_devices (organization_id, provider_id);

CREATE TABLE user_roles (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  user_id          uuid NOT NULL,
  -- 'adherent' : Phase 1, migration 0002 (CR-P1-01, à valider) ; 'assureur' et
  -- 'admin_plateforme' : Phase 3, migration 0004 (CR-P3-01, à valider).
  role             text NOT NULL CHECK (role IN ('gestionnaire', 'medecin_conseil', 'clinique',
                                                 'employeur', 'admin', 'adherent', 'assureur',
                                                 'admin_plateforme')),
  -- Attributs de portée (contrôle par attribut) : une clinique ne voit que ses dossiers,
  -- un employeur que son groupe, un adhérent que son contrat.
  provider_id      uuid,
  employer_id      uuid,
  granted_by       uuid,
  granted_at       timestamptz NOT NULL DEFAULT now(),
  -- Contrat de l'adhérent (Phase 1, migration 0002) ; clé étrangère posée après `members`.
  member_id        uuid,
  CHECK ((role = 'clinique') = (provider_id IS NOT NULL)),
  CHECK ((role = 'employeur') = (employer_id IS NOT NULL)),
  CONSTRAINT user_roles_adherent_scope_check CHECK ((role = 'adherent') = (member_id IS NOT NULL)),
  UNIQUE NULLS NOT DISTINCT (organization_id, user_id, role, provider_id, employer_id),
  FOREIGN KEY (organization_id, user_id) REFERENCES users (organization_id, id),
  FOREIGN KEY (organization_id, provider_id) REFERENCES providers (organization_id, id),
  FOREIGN KEY (organization_id, employer_id) REFERENCES employers (organization_id, id),
  FOREIGN KEY (organization_id, granted_by) REFERENCES users (organization_id, id)
);
CREATE INDEX user_roles_provider_idx ON user_roles (organization_id, provider_id);
CREATE INDEX user_roles_employer_idx ON user_roles (organization_id, employer_id);
CREATE INDEX user_roles_granted_by_idx ON user_roles (organization_id, granted_by);

-- -----------------------------------------------------------------------------
-- Personnes, produits, adhésions (L4, L2)
-- -----------------------------------------------------------------------------

-- Identité civile. Données personnelles : ne quittent jamais le pays de l'instance (R9).
CREATE TABLE persons (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id     uuid NOT NULL REFERENCES organizations (id),
  given_name          text NOT NULL,
  family_name         text NOT NULL,
  birth_date          date NOT NULL,
  phone_e164          text CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'),
  -- Clé de l'objet photo dans le stockage du pays (pas l'image elle-même).
  photo_object_key    text,
  -- Seul identifiant transmis à HealthOS (R9).
  healthos_pseudonym  uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id)
);

CREATE TABLE plans (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  code             text NOT NULL CHECK (code ~ '^[A-Z0-9-]{2,32}$'),
  name             text NOT NULL,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, code)
);

-- Version de produit avec date d'effet (R3). Un soin est évalué avec la version en vigueur
-- à `claims.service_date`.
CREATE TABLE plan_versions (
  id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id            uuid NOT NULL REFERENCES organizations (id),
  plan_id                    uuid NOT NULL,
  version                    integer NOT NULL CHECK (version > 0),
  valid_from                 date NOT NULL,
  valid_to                   date CHECK (valid_to IS NULL OR valid_to >= valid_from),
  state                      text NOT NULL DEFAULT 'brouillon'
                               CHECK (state IN ('brouillon', 'soumise', 'en_vigueur', 'cloturee')),
  -- Taux de couverture en points de base (8000 = 80 %).
  coverage_rate_bp           integer NOT NULL CHECK (coverage_rate_bp BETWEEN 0 AND 10000),
  family_annual_ceiling_xof  amount_xof NOT NULL,
  waiting_period_days        integer NOT NULL CHECK (waiting_period_days >= 0),
  monthly_contribution_xof   amount_xof NOT NULL,
  currency                   char(3) NOT NULL DEFAULT 'XOF' CHECK (currency = 'XOF'),
  approved_by                uuid,
  approved_at                timestamptz,
  created_at                 timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, plan_id, version),
  FOREIGN KEY (organization_id, plan_id) REFERENCES plans (organization_id, id),
  FOREIGN KEY (organization_id, approved_by) REFERENCES users (organization_id, id)
);
CREATE INDEX plan_versions_effective_idx ON plan_versions (organization_id, plan_id, valid_from);
CREATE INDEX plan_versions_approved_by_idx ON plan_versions (organization_id, approved_by);

-- Garanties d'une version de produit (prototype, onglet « Garanties »).
CREATE TABLE coverages (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id    uuid NOT NULL REFERENCES organizations (id),
  plan_version_id    uuid NOT NULL,
  category           text NOT NULL CHECK (category ~ '^[a-z_]{2,40}$'),
  label              text NOT NULL,
  -- Taux propre à la garantie ; NULL = taux de la version.
  coverage_rate_bp   integer CHECK (coverage_rate_bp BETWEEN 0 AND 10000),
  annual_limit_xof   amount_xof,
  limit_scope        text NOT NULL DEFAULT 'famille' CHECK (limit_scope IN ('famille',
                                                                             'beneficiaire')),
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, plan_version_id, category),
  FOREIGN KEY (organization_id, plan_version_id) REFERENCES plan_versions (organization_id, id)
);

-- Nomenclature des actes (libellés de facturation, pas de motif médical).
CREATE TABLE acts (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id          uuid NOT NULL REFERENCES organizations (id),
  code                     text NOT NULL CHECK (code ~ '^[A-Z0-9-]{2,32}$'),
  label                    text NOT NULL,
  -- Rattachement à une catégorie de garantie (`coverages.category`).
  coverage_category        text NOT NULL CHECK (coverage_category ~ '^[a-z_]{2,40}$'),
  requires_prior_approval  boolean NOT NULL DEFAULT false,
  created_at               timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, code)
);

-- Barème conventionné daté (R-04 : barème de l'année du soin).
CREATE TABLE tariff_items (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  act_id           uuid NOT NULL,
  amount_xof       amount_xof NOT NULL,
  currency         char(3) NOT NULL DEFAULT 'XOF' CHECK (currency = 'XOF'),
  valid_from       date NOT NULL,
  valid_to         date CHECK (valid_to IS NULL OR valid_to >= valid_from),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, act_id, valid_from),
  FOREIGN KEY (organization_id, act_id) REFERENCES acts (organization_id, id)
);

CREATE TABLE members (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id         uuid NOT NULL REFERENCES organizations (id),
  person_id               uuid NOT NULL,
  member_number           text NOT NULL CHECK (member_number ~ '^MC-[0-9]{8}$'),
  plan_id                 uuid NOT NULL,
  employer_id             uuid,
  status                  text NOT NULL CHECK (status IN ('actif', 'carence', 'suspendu')),
  status_changed_at       timestamptz NOT NULL DEFAULT now(),
  enrolled_on             date NOT NULL,
  waiting_period_ends_on  date NOT NULL CHECK (waiting_period_ends_on >= enrolled_on),
  created_at              timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, member_number),
  UNIQUE (organization_id, person_id),
  FOREIGN KEY (organization_id, person_id) REFERENCES persons (organization_id, id),
  FOREIGN KEY (organization_id, plan_id) REFERENCES plans (organization_id, id),
  FOREIGN KEY (organization_id, employer_id) REFERENCES employers (organization_id, id)
);
CREATE INDEX members_plan_idx ON members (organization_id, plan_id);
CREATE INDEX members_employer_idx ON members (organization_id, employer_id);
CREATE INDEX members_status_idx ON members (organization_id, status);

-- Compte adhérent rattaché à son contrat (Phase 1, migration 0002, CR-P1-01).
ALTER TABLE user_roles ADD CONSTRAINT user_roles_member_fk
  FOREIGN KEY (organization_id, member_id) REFERENCES members (organization_id, id);
CREATE INDEX user_roles_member_idx ON user_roles (organization_id, member_id);

-- Historique des statuts (ajout seul). Sert à R-01 à la date du soin et à
-- l'événement member.status_changed.
CREATE TABLE member_status_history (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  member_id        uuid NOT NULL,
  from_status      text CHECK (from_status IN ('actif', 'carence', 'suspendu')),
  to_status        text NOT NULL CHECK (to_status IN ('actif', 'carence', 'suspendu')),
  reason_code      text NOT NULL CHECK (reason_code IN ('adhesion', 'fin_de_carence',
                                                        'paiement_confirme', 'impaye',
                                                        'decision_gestionnaire')),
  actor_user_id    uuid,
  occurred_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, member_id) REFERENCES members (organization_id, id),
  FOREIGN KEY (organization_id, actor_user_id) REFERENCES users (organization_id, id)
);
CREATE INDEX member_status_history_member_idx
  ON member_status_history (organization_id, member_id, occurred_at);
CREATE INDEX member_status_history_actor_idx ON member_status_history (organization_id, actor_user_id);

CREATE TABLE dependents (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  member_id        uuid NOT NULL,
  person_id        uuid NOT NULL,
  relationship     text NOT NULL CHECK (relationship IN ('conjoint', 'enfant', 'autre')),
  valid_from       date NOT NULL,
  valid_to         date CHECK (valid_to IS NULL OR valid_to >= valid_from),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, member_id, person_id),
  FOREIGN KEY (organization_id, member_id) REFERENCES members (organization_id, id),
  FOREIGN KEY (organization_id, person_id) REFERENCES persons (organization_id, id)
);
CREATE INDEX dependents_person_idx ON dependents (organization_id, person_id);

-- Carte à QR dynamique, une carte active par bénéficiaire.
CREATE TABLE cards (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id       uuid NOT NULL REFERENCES organizations (id),
  member_id             uuid NOT NULL,
  person_id             uuid NOT NULL,
  -- Secret du QR dynamique, chiffré par l'application (clé hors base).
  qr_secret_ciphertext  bytea NOT NULL,
  status                text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoquee')),
  -- R1 : compteur de codes faux et blocage temporaire (seuils en données, règle ID-03).
  failed_code_count     integer NOT NULL DEFAULT 0 CHECK (failed_code_count >= 0),
  blocked_until         timestamptz,
  issued_at             timestamptz NOT NULL DEFAULT now(),
  revoked_at            timestamptz,
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, member_id) REFERENCES members (organization_id, id),
  FOREIGN KEY (organization_id, person_id) REFERENCES persons (organization_id, id)
);
CREATE UNIQUE INDEX cards_one_active_per_person_idx
  ON cards (organization_id, person_id) WHERE status = 'active';
CREATE INDEX cards_member_idx ON cards (organization_id, member_id);
CREATE INDEX cards_person_idx ON cards (organization_id, person_id);

-- Identification en trois facteurs au comptoir (R1) : QR, photo, code SMS.
CREATE TABLE identity_checks (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id       uuid NOT NULL REFERENCES organizations (id),
  card_id               uuid NOT NULL,
  provider_id           uuid NOT NULL,
  operator_user_id      uuid NOT NULL,
  qr_verified           boolean NOT NULL DEFAULT false,
  photo_confirmed       boolean,
  code_hash             text,
  code_sent_at          timestamptz,
  code_expires_at       timestamptz,
  code_failed_attempts  integer NOT NULL DEFAULT 0 CHECK (code_failed_attempts >= 0),
  verified_at           timestamptz,
  status                text NOT NULL DEFAULT 'ouverte'
                          CHECK (status IN ('ouverte', 'verifiee', 'identite_refusee',
                                            'bloquee', 'expiree')),
  started_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, card_id) REFERENCES cards (organization_id, id),
  FOREIGN KEY (organization_id, provider_id) REFERENCES providers (organization_id, id),
  FOREIGN KEY (organization_id, operator_user_id) REFERENCES users (organization_id, id)
);
CREATE INDEX identity_checks_card_idx ON identity_checks (organization_id, card_id, started_at);
CREATE INDEX identity_checks_provider_idx ON identity_checks (organization_id, provider_id);
CREATE INDEX identity_checks_operator_idx ON identity_checks (organization_id, operator_user_id);

-- -----------------------------------------------------------------------------
-- Règles de décision en données (L2)
-- -----------------------------------------------------------------------------

CREATE TABLE rules (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  -- Code stable affiché et renvoyé par l'API : R-01, R-04, R-07, R-09, R-12, R-20, ID-03…
  code             text NOT NULL CHECK (code ~ '^[A-Z]{1,3}-[0-9]{2}$'),
  label            text NOT NULL,
  kind             text NOT NULL CHECK (kind IN ('droits', 'reseau', 'carence', 'plafond',
                                                 'accord_automatique', 'revue',
                                                 'identification', 'hors_ligne')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, code)
);

CREATE TABLE rule_versions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  rule_id          uuid NOT NULL,
  version          integer NOT NULL CHECK (version > 0),
  valid_from       date NOT NULL,
  valid_to         date CHECK (valid_to IS NULL OR valid_to >= valid_from),
  -- Seuils, taux et conditions (objet JSON ; les montants y sont des entiers FCFA).
  params           jsonb NOT NULL CHECK (jsonb_typeof(params) = 'object'),
  state            text NOT NULL DEFAULT 'brouillon'
                     CHECK (state IN ('brouillon', 'soumise', 'en_vigueur', 'cloturee')),
  approved_by      uuid,
  approved_at      timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, rule_id, version),
  FOREIGN KEY (organization_id, rule_id) REFERENCES rules (organization_id, id),
  FOREIGN KEY (organization_id, approved_by) REFERENCES users (organization_id, id)
);
CREATE INDEX rule_versions_effective_idx ON rule_versions (organization_id, rule_id, valid_from);
CREATE INDEX rule_versions_approved_by_idx ON rule_versions (organization_id, approved_by);

-- -----------------------------------------------------------------------------
-- Prises en charge (L5)
-- -----------------------------------------------------------------------------

CREATE TABLE claims (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id         uuid NOT NULL REFERENCES organizations (id),
  claim_number            text NOT NULL CHECK (claim_number ~ '^PEC-[0-9]{2}-[0-9]{5,}$'),
  member_id               uuid NOT NULL,
  beneficiary_person_id   uuid NOT NULL,
  provider_id             uuid NOT NULL,
  identity_check_id       uuid,
  channel                 text NOT NULL CHECK (channel IN ('comptoir', 'comptoir_hors_ligne',
                                                           'console')),
  -- Date du soin : détermine la version de produit et de règle applicable (R3).
  service_date            date NOT NULL,
  plan_version_id         uuid NOT NULL,
  status                  text NOT NULL CHECK (status IN ('demandee', 'accordee_auto',
                                                          'en_revue', 'pieces_demandees',
                                                          'accordee', 'refusee', 'payee',
                                                          'annulee')),
  total_xof               amount_xof NOT NULL,
  covered_xof             amount_xof NOT NULL,
  patient_share_xof       amount_xof NOT NULL,
  currency                char(3) NOT NULL DEFAULT 'XOF' CHECK (currency = 'XOF'),
  fraud_score             numeric(4, 3) CHECK (fraud_score BETWEEN 0 AND 1),
  fraud_flagged           boolean NOT NULL DEFAULT false,
  -- Dernière décision : règle et version appliquées (copie de claim_decisions).
  decision_rule_id        uuid,
  decision_rule_version   integer,
  -- Référence pseudonyme de la consultation chez HealthOS ; le motif n'est JAMAIS copié ici.
  healthos_encounter_ref  text,
  review_due_at           timestamptz,
  requested_at            timestamptz NOT NULL DEFAULT now(),
  decided_at              timestamptz,
  created_by              uuid,
  CHECK (covered_xof + patient_share_xof = total_xof),
  CHECK ((decision_rule_id IS NULL) = (decision_rule_version IS NULL)),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, claim_number),
  FOREIGN KEY (organization_id, member_id) REFERENCES members (organization_id, id),
  FOREIGN KEY (organization_id, beneficiary_person_id) REFERENCES persons (organization_id, id),
  FOREIGN KEY (organization_id, provider_id) REFERENCES providers (organization_id, id),
  FOREIGN KEY (organization_id, identity_check_id)
    REFERENCES identity_checks (organization_id, id),
  FOREIGN KEY (organization_id, plan_version_id) REFERENCES plan_versions (organization_id, id),
  FOREIGN KEY (organization_id, decision_rule_id, decision_rule_version)
    REFERENCES rule_versions (organization_id, rule_id, version),
  FOREIGN KEY (organization_id, created_by) REFERENCES users (organization_id, id)
);
CREATE INDEX claims_member_idx ON claims (organization_id, member_id, service_date);
CREATE INDEX claims_beneficiary_idx ON claims (organization_id, beneficiary_person_id);
CREATE INDEX claims_provider_idx ON claims (organization_id, provider_id, requested_at);
CREATE INDEX claims_identity_check_idx ON claims (organization_id, identity_check_id);
CREATE INDEX claims_plan_version_idx ON claims (organization_id, plan_version_id);
CREATE INDEX claims_decision_rule_idx
  ON claims (organization_id, decision_rule_id, decision_rule_version);
CREATE INDEX claims_created_by_idx ON claims (organization_id, created_by);
CREATE INDEX claims_status_idx ON claims (organization_id, status, requested_at);

CREATE TABLE claim_items (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id    uuid NOT NULL REFERENCES organizations (id),
  claim_id           uuid NOT NULL,
  line_no            integer NOT NULL CHECK (line_no > 0),
  act_id             uuid NOT NULL,
  tariff_item_id     uuid,
  quantity           integer NOT NULL DEFAULT 1 CHECK (quantity > 0),
  unit_amount_xof    amount_xof NOT NULL,
  amount_xof         amount_xof NOT NULL,
  covered_xof        amount_xof NOT NULL,
  CHECK (amount_xof = unit_amount_xof * quantity),
  CHECK (covered_xof <= amount_xof),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, claim_id, line_no),
  FOREIGN KEY (organization_id, claim_id) REFERENCES claims (organization_id, id),
  FOREIGN KEY (organization_id, act_id) REFERENCES acts (organization_id, id),
  FOREIGN KEY (organization_id, tariff_item_id) REFERENCES tariff_items (organization_id, id)
);
CREATE INDEX claim_items_act_idx ON claim_items (organization_id, act_id);
CREATE INDEX claim_items_tariff_item_idx ON claim_items (organization_id, tariff_item_id);

-- Journal des décisions (ajout seul) : chaque décision est rejouable (objectif v1 n°2).
CREATE TABLE claim_decisions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id   uuid NOT NULL REFERENCES organizations (id),
  claim_id          uuid NOT NULL,
  sequence          integer NOT NULL CHECK (sequence > 0),
  outcome           text NOT NULL CHECK (outcome IN ('accordee_auto', 'en_revue', 'accordee',
                                                     'refusee', 'pieces_demandees',
                                                     'annulee')),
  source            text NOT NULL CHECK (source IN ('regle', 'humain')),
  rule_id           uuid,
  rule_version      integer,
  -- Code stable (R-01, R-04… pour une règle ; code de motif administratif pour un humain).
  reason_code       text NOT NULL CHECK (reason_code ~ '^[A-Z]{1,4}-[0-9]{2}$'),
  decided_by        uuid,
  -- Trace d'évaluation : résultat de chaque règle, sans donnée médicale.
  evaluation_trace  jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(evaluation_trace)
                                                               = 'array'),
  decided_at        timestamptz NOT NULL DEFAULT now(),
  CHECK ((source = 'regle' AND rule_id IS NOT NULL AND rule_version IS NOT NULL
          AND decided_by IS NULL)
      OR (source = 'humain' AND decided_by IS NOT NULL)),
  CHECK ((rule_id IS NULL) = (rule_version IS NULL)),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, claim_id, sequence),
  FOREIGN KEY (organization_id, claim_id) REFERENCES claims (organization_id, id),
  FOREIGN KEY (organization_id, rule_id, rule_version)
    REFERENCES rule_versions (organization_id, rule_id, version),
  FOREIGN KEY (organization_id, decided_by) REFERENCES users (organization_id, id)
);
CREATE INDEX claim_decisions_rule_idx ON claim_decisions (organization_id, rule_id, rule_version);
CREATE INDEX claim_decisions_decided_by_idx ON claim_decisions (organization_id, decided_by);

-- Pièces fournies après une demande (statut pieces_demandees) : références HealthOS seulement.
-- Le contenu des pièces reste dans la base clinique ; ici, le type et la référence.
CREATE TABLE claim_documents (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id        uuid NOT NULL REFERENCES organizations (id),
  claim_id               uuid NOT NULL,
  kind                   text NOT NULL CHECK (kind IN ('facture', 'piece_clinique',
                                                       'justificatif_identite', 'autre')),
  healthos_document_ref  text NOT NULL,
  submitted_by           uuid NOT NULL,
  submitted_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, claim_id, healthos_document_ref),
  FOREIGN KEY (organization_id, claim_id) REFERENCES claims (organization_id, id),
  FOREIGN KEY (organization_id, submitted_by) REFERENCES users (organization_id, id)
);
CREATE INDEX claim_documents_submitted_by_idx ON claim_documents (organization_id, submitted_by);

-- Accord de prise en charge remis au prestataire : en ligne, ou provisoire signé sur
-- l'appareil hors ligne (R13) puis rapproché à la synchronisation.
CREATE TABLE authorizations (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id       uuid NOT NULL REFERENCES organizations (id),
  authorization_number  text NOT NULL,
  claim_id              uuid NOT NULL,
  kind                  text NOT NULL CHECK (kind IN ('en_ligne', 'provisoire_hors_ligne')),
  status                text NOT NULL CHECK (status IN ('emise', 'synchronisee',
                                                          'rejetee_a_la_synchro', 'expiree',
                                                          'annulee')),
  covered_xof           amount_xof NOT NULL,
  currency              char(3) NOT NULL DEFAULT 'XOF' CHECK (currency = 'XOF'),
  rule_id               uuid NOT NULL,
  rule_version          integer NOT NULL,
  issued_at             timestamptz NOT NULL,
  expires_at            timestamptz,
  -- Hors ligne : appareil, identifiant local (idempotence de la synchro) et signature.
  device_id             uuid,
  offline_ref           uuid,
  device_signature      text,
  signed_payload        jsonb,
  synced_at             timestamptz,
  CHECK (kind = 'en_ligne'
      OR (device_id IS NOT NULL AND offline_ref IS NOT NULL AND device_signature IS NOT NULL
          AND signed_payload IS NOT NULL AND expires_at IS NOT NULL)),
  CHECK (expires_at IS NULL OR expires_at > issued_at),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, authorization_number),
  UNIQUE (organization_id, device_id, offline_ref),
  FOREIGN KEY (organization_id, claim_id) REFERENCES claims (organization_id, id),
  FOREIGN KEY (organization_id, rule_id, rule_version)
    REFERENCES rule_versions (organization_id, rule_id, version),
  FOREIGN KEY (organization_id, device_id) REFERENCES counter_devices (organization_id, id)
);
CREATE INDEX authorizations_claim_idx ON authorizations (organization_id, claim_id);
CREATE INDEX authorizations_rule_idx ON authorizations (organization_id, rule_id, rule_version);

-- -----------------------------------------------------------------------------
-- Cotisations et paiements (L4)
-- -----------------------------------------------------------------------------

CREATE TABLE contributions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  member_id        uuid NOT NULL,
  -- Premier jour du mois couvert.
  period_start     date NOT NULL CHECK (extract(day FROM period_start) = 1),
  due_on           date NOT NULL,
  amount_xof       amount_xof NOT NULL,
  currency         char(3) NOT NULL DEFAULT 'XOF' CHECK (currency = 'XOF'),
  status           text NOT NULL DEFAULT 'a_payer'
                     CHECK (status IN ('a_payer', 'payee', 'en_retard', 'annulee')),
  paid_at          timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  CHECK ((status = 'payee') = (paid_at IS NOT NULL)),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, member_id, period_start),
  FOREIGN KEY (organization_id, member_id) REFERENCES members (organization_id, id)
);
CREATE INDEX contributions_due_idx ON contributions (organization_id, status, due_on);

-- Paiement reçu d'un canal (simulé tant que PRD §10 Q1 n'est pas tranchée).
-- Idempotence : (canal, référence du fournisseur) est unique.
CREATE TABLE payments (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id     uuid NOT NULL REFERENCES organizations (id),
  contribution_id     uuid,
  channel             text NOT NULL CHECK (channel IN ('wave', 'orange_money', 'mtn_momo',
                                                       'virement', 'prelevement_employeur',
                                                       'simulation')),
  provider_reference  text NOT NULL,
  amount_xof          amount_xof NOT NULL,
  currency            char(3) NOT NULL DEFAULT 'XOF' CHECK (currency = 'XOF'),
  status              text NOT NULL CHECK (status IN ('en_attente', 'confirme', 'echoue')),
  payer_kind          text NOT NULL CHECK (payer_kind IN ('adherent', 'employeur', 'proche')),
  -- Pays du payeur (diaspora), sans autre donnée sur le payeur.
  payer_country_code  char(2) CHECK (payer_country_code ~ '^[A-Z]{2}$'),
  received_at         timestamptz NOT NULL DEFAULT now(),
  confirmed_at        timestamptz,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, channel, provider_reference),
  FOREIGN KEY (organization_id, contribution_id) REFERENCES contributions (organization_id, id)
);
CREATE INDEX payments_contribution_idx ON payments (organization_id, contribution_id);

-- Lien de paiement (payeur diaspora). Seul le hachage du jeton est stocké.
CREATE TABLE payment_links (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  contribution_id  uuid NOT NULL,
  token_hash       text NOT NULL UNIQUE,
  expires_at       timestamptz NOT NULL,
  used_at          timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, contribution_id) REFERENCES contributions (organization_id, id)
);
CREATE INDEX payment_links_contribution_idx ON payment_links (organization_id, contribution_id);

-- SMS / WhatsApp sortants (code, relance, confirmation). Pas de corps libre stocké.
CREATE TABLE outbound_messages (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  person_id        uuid NOT NULL,
  channel          text NOT NULL CHECK (channel IN ('sms', 'whatsapp')),
  template_code    text NOT NULL CHECK (template_code ~ '^[a-z_]{2,64}$'),
  related_type     text CHECK (related_type IN ('claim', 'contribution', 'identity_check',
                                                'member')),
  related_id       uuid,
  status           text NOT NULL DEFAULT 'en_file' CHECK (status IN ('en_file', 'envoye',
                                                                     'echoue')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  sent_at          timestamptz,
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, person_id) REFERENCES persons (organization_id, id)
);
CREATE INDEX outbound_messages_person_idx ON outbound_messages (organization_id, person_id);
CREATE INDEX outbound_messages_pending_idx ON outbound_messages (organization_id, status)
  WHERE status = 'en_file';

-- -----------------------------------------------------------------------------
-- Grand livre en partie double, ajout seul (L3, R7)
-- -----------------------------------------------------------------------------

-- Plan de comptes (initial : 4011, 5110, 5121, 5122, 6011, 7061).
CREATE TABLE ledger_accounts (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  code             text NOT NULL CHECK (code ~ '^[0-9]{4,8}$'),
  label            text NOT NULL,
  account_class    text NOT NULL CHECK (account_class IN ('actif', 'passif', 'charge',
                                                          'produit')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, code)
);

CREATE TABLE ledger_entries (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id    uuid NOT NULL REFERENCES organizations (id),
  entry_number       text NOT NULL,
  accounting_date    date NOT NULL,
  label              text NOT NULL,
  currency           char(3) NOT NULL DEFAULT 'XOF' CHECK (currency = 'XOF'),
  source_type        text NOT NULL CHECK (source_type IN ('prise_en_charge', 'cotisation',
                                                          'reglement', 'contre_passation')),
  source_id          uuid,
  -- Identifiant de l'événement consommé (claim.decided, contribution.received) :
  -- rend le consommateur idempotent.
  source_event_id    uuid,
  reverses_entry_id  uuid,
  created_by         uuid,
  posted_at          timestamptz NOT NULL DEFAULT now(),
  -- Transaction de création, positionnée par déclencheur (non modifiable par le client).
  posted_txid        xid8 NOT NULL DEFAULT pg_current_xact_id(),
  CHECK ((source_type = 'contre_passation') = (reverses_entry_id IS NOT NULL)),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, entry_number),
  UNIQUE (organization_id, source_event_id),
  -- Une écriture ne se contre-passe qu'une fois.
  UNIQUE (organization_id, reverses_entry_id),
  FOREIGN KEY (organization_id, reverses_entry_id) REFERENCES ledger_entries (organization_id, id),
  FOREIGN KEY (organization_id, created_by) REFERENCES users (organization_id, id)
);
CREATE INDEX ledger_entries_date_idx ON ledger_entries (organization_id, accounting_date);
CREATE INDEX ledger_entries_source_idx ON ledger_entries (organization_id, source_type, source_id);
CREATE INDEX ledger_entries_created_by_idx ON ledger_entries (organization_id, created_by);

CREATE TABLE ledger_lines (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  entry_id         uuid NOT NULL,
  line_no          integer NOT NULL CHECK (line_no > 0),
  account_id       uuid NOT NULL,
  debit_xof        amount_xof NOT NULL DEFAULT 0,
  credit_xof       amount_xof NOT NULL DEFAULT 0,
  -- Tiers (sous-compte) : prestataire à payer ou adhérent.
  provider_id      uuid,
  member_id        uuid,
  -- Exactement un des deux montants est strictement positif.
  CHECK ((debit_xof > 0) <> (credit_xof > 0)),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, entry_id, line_no),
  FOREIGN KEY (organization_id, entry_id) REFERENCES ledger_entries (organization_id, id),
  FOREIGN KEY (organization_id, account_id) REFERENCES ledger_accounts (organization_id, id),
  FOREIGN KEY (organization_id, provider_id) REFERENCES providers (organization_id, id),
  FOREIGN KEY (organization_id, member_id) REFERENCES members (organization_id, id)
);
CREATE INDEX ledger_lines_account_idx ON ledger_lines (organization_id, account_id);
CREATE INDEX ledger_lines_provider_idx ON ledger_lines (organization_id, provider_id);
CREATE INDEX ledger_lines_member_idx ON ledger_lines (organization_id, member_id);

CREATE FUNCTION ledger_entry_stamp() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.posted_txid := pg_current_xact_id();
  NEW.posted_at := now();
  RETURN NEW;
END
$$;

CREATE FUNCTION ledger_line_same_transaction() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  entry_txid xid8;
BEGIN
  SELECT posted_txid INTO entry_txid
  FROM ledger_entries
  WHERE id = NEW.entry_id AND organization_id = NEW.organization_id;
  IF entry_txid IS NOT NULL AND entry_txid <> pg_current_xact_id() THEN
    RAISE EXCEPTION USING ERRCODE = 'MCL03',
      MESSAGE = 'Écriture déjà validée : aucune ligne ne peut y être ajoutée.',
      HINT = 'Passez une nouvelle écriture ou une contre-passation.';
  END IF;
  RETURN NEW;
END
$$;

CREATE FUNCTION ledger_check_entry_balanced() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  target uuid;
  original uuid;
  line_count integer;
  total_debit numeric;
  total_credit numeric;
BEGIN
  IF TG_TABLE_NAME = 'ledger_entries' THEN
    target := NEW.id;
  ELSE
    target := NEW.entry_id;
  END IF;
  SELECT count(*), coalesce(sum(debit_xof), 0), coalesce(sum(credit_xof), 0)
    INTO line_count, total_debit, total_credit
  FROM ledger_lines
  WHERE entry_id = target;
  IF line_count < 2 OR total_debit <> total_credit THEN
    RAISE EXCEPTION USING ERRCODE = 'MCL02',
      MESSAGE = format('Écriture %s déséquilibrée : %s ligne(s), débits %s, crédits %s.',
                       target, line_count, total_debit, total_credit);
  END IF;

  -- Contre-passation : miroir exact de l'écriture d'origine (mêmes comptes et tiers,
  -- débits et crédits inversés, mêmes montants).
  SELECT reverses_entry_id INTO original FROM ledger_entries WHERE id = target;
  IF original IS NOT NULL AND EXISTS (
    (SELECT account_id, provider_id, member_id, sum(debit_xof), sum(credit_xof)
       FROM ledger_lines WHERE entry_id = target GROUP BY 1, 2, 3
     EXCEPT
     SELECT account_id, provider_id, member_id, sum(credit_xof), sum(debit_xof)
       FROM ledger_lines WHERE entry_id = original GROUP BY 1, 2, 3)
    UNION ALL
    (SELECT account_id, provider_id, member_id, sum(credit_xof), sum(debit_xof)
       FROM ledger_lines WHERE entry_id = original GROUP BY 1, 2, 3
     EXCEPT
     SELECT account_id, provider_id, member_id, sum(debit_xof), sum(credit_xof)
       FROM ledger_lines WHERE entry_id = target GROUP BY 1, 2, 3)
  ) THEN
    RAISE EXCEPTION USING ERRCODE = 'MCL04',
      MESSAGE = format('Contre-passation %s : ce n''est pas le miroir exact de %s.',
                       target, original),
      HINT = 'Reprenez chaque ligne d''origine en inversant débit et crédit.';
  END IF;
  RETURN NULL;
END
$$;

CREATE TRIGGER ledger_entries_stamp
  BEFORE INSERT ON ledger_entries
  FOR EACH ROW EXECUTE FUNCTION ledger_entry_stamp();

CREATE TRIGGER ledger_lines_same_transaction
  BEFORE INSERT ON ledger_lines
  FOR EACH ROW EXECUTE FUNCTION ledger_line_same_transaction();

-- Équilibre vérifié au COMMIT (différé) : lignes et écriture insérées dans la même transaction.
CREATE CONSTRAINT TRIGGER ledger_entries_balanced
  AFTER INSERT ON ledger_entries
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION ledger_check_entry_balanced();

CREATE CONSTRAINT TRIGGER ledger_lines_balanced
  AFTER INSERT ON ledger_lines
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION ledger_check_entry_balanced();

-- -----------------------------------------------------------------------------
-- Audit, JOE, idempotence, événements (L1, L8, L4, L3)
-- -----------------------------------------------------------------------------

-- Journal d'audit immuable. Toute lecture du motif médical y crée une ligne (R6) :
-- action = 'claim.medical_reason.read'.
CREATE TABLE audit_events (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  occurred_at      timestamptz NOT NULL DEFAULT now(),
  actor_user_id    uuid,
  actor_role       text,
  action           text NOT NULL CHECK (action ~ '^[a-z_]+(\.[a-z_]+)+$'),
  target_type      text NOT NULL,
  target_id        uuid,
  request_id       text,
  -- Contexte technique, identifiants pseudonymes seulement.
  metadata         jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, actor_user_id) REFERENCES users (organization_id, id)
);
CREATE INDEX audit_events_time_idx ON audit_events (organization_id, occurred_at);
CREATE INDEX audit_events_target_idx ON audit_events (organization_id, target_type, target_id);
CREATE INDEX audit_events_actor_idx ON audit_events (organization_id, actor_user_id);

-- Actions de JOE (R11) : lecture, préparation ou réponse, avec leurs sources.
-- JOE ne dispose d'aucun outil de décision ni de paiement.
CREATE TABLE ai_actions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  user_id          uuid NOT NULL,
  kind             text NOT NULL CHECK (kind IN ('lecture', 'preparation', 'reponse', 'refus')),
  tool             text NOT NULL CHECK (tool ~ '^[a-z_]{2,64}$'
                                        AND tool !~ '(approve|reject|pay|decide)'),
  model            text,
  input            jsonb NOT NULL DEFAULT '{}'::jsonb,
  output           jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- Enregistrements consultés : [{"type": "claim", "id": "…"}, …].
  sources          jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(sources) = 'array'),
  occurred_at      timestamptz NOT NULL DEFAULT now(),
  -- Une réponse ou une préparation cite au moins une source ; sinon c'est un refus.
  CHECK (kind IN ('lecture', 'refus') OR jsonb_array_length(sources) > 0),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, user_id) REFERENCES users (organization_id, id)
);
CREATE INDEX ai_actions_user_idx ON ai_actions (organization_id, user_id, occurred_at);

-- Clés d'idempotence (webhooks, commandes de paiement, création de prise en charge).
CREATE TABLE idempotency_keys (
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  -- Portée : 'webhook:wave', 'webhook:orange_money', 'command:claim.create'…
  scope            text NOT NULL CHECK (scope ~ '^[a-z_]+:[a-z_.]+$'),
  key              text NOT NULL CHECK (length(key) BETWEEN 8 AND 200),
  -- Empreinte du corps : même clé + corps différent => erreur IDEM-01.
  request_hash     text NOT NULL,
  status           text NOT NULL DEFAULT 'en_cours' CHECK (status IN ('en_cours', 'terminee')),
  response_status  integer,
  response_body    jsonb,
  created_at       timestamptz NOT NULL DEFAULT now(),
  expires_at       timestamptz NOT NULL,
  PRIMARY KEY (organization_id, scope, key)
);
CREATE INDEX idempotency_keys_expiry_idx ON idempotency_keys (expires_at);

-- Boîte d'envoi transactionnelle des six événements du PRD §6 (specs/events.md).
CREATE TABLE outbox_events (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  event_type       text NOT NULL CHECK (event_type IN ('claim.requested', 'claim.decided',
                                                       'contribution.received',
                                                       'member.status_changed',
                                                       'ledger.entry_posted',
                                                       'authorization.synced')),
  event_version    integer NOT NULL DEFAULT 1 CHECK (event_version > 0),
  aggregate_id     uuid NOT NULL,
  payload          jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
  occurred_at      timestamptz NOT NULL DEFAULT now(),
  published_at     timestamptz,
  UNIQUE (organization_id, id)
);
CREATE INDEX outbox_events_pending_idx ON outbox_events (occurred_at) WHERE published_at IS NULL;

-- -----------------------------------------------------------------------------
-- Mesure produit (Phase 2, voie B ; migration 0003, CR-P2-01 — à valider)
-- -----------------------------------------------------------------------------
-- Événements d'usage des écrans, liste blanche FERMÉE (nom, surface, variante). Aucune donnée
-- identifiante : ni utilisateur, ni adhérent, ni carte, ni texte libre. `session_ref` est une
-- empreinte SHA-256 (organisation, jour UTC, identifiant de session aléatoire du navigateur) :
-- pseudonyme et tournée chaque jour ; l'identifiant brut n'est jamais stocké. `occurred_at` est
-- l'heure du serveur. Rétention : `expires_at` posé à l'insertion (durée configurable), purge
-- par DELETE (seule suppression permise) ; une ligne expirée n'est plus comptée.
CREATE TABLE product_events (
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
                                                 'employeur', 'admin', 'adherent', 'assureur',
                                                 'admin_plateforme')),
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
CREATE INDEX product_events_name_idx ON product_events (organization_id, name, occurred_at);
CREATE INDEX product_events_expiry_idx ON product_events (organization_id, expires_at);

-- -----------------------------------------------------------------------------
-- Marque blanche, espaces assureur et employeur, accueil d'organisation
-- (Phase 3, voie A ; migration 0004, CR-P3-01 — à valider)
-- -----------------------------------------------------------------------------
-- Vente clé en main aux assureurs (décision de Dajan du 01/10, PRD §2 amendé). Une organisation
-- « plateforme » (capacité `plateforme`) accueille de nouvelles organisations : chacune reçoit
-- une COPIE de gabarit (nouvelles lignes, nouvelle version), jamais une ligne partagée.
-- `admin_plateforme` n'existe que dans une organisation « plateforme » (garde ci-dessous) ;
-- `assureur` lit des agrégats k-anonymes de SON organisation, rien d'autre.

CREATE FUNCTION user_roles_platform_admin_guard() RETURNS trigger
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

CREATE TRIGGER user_roles_platform_admin_guard
  BEFORE INSERT OR UPDATE ON user_roles
  FOR EACH ROW EXECUTE FUNCTION user_roles_platform_admin_guard();

-- Marque blanche : une ligne par organisation. Aucune couleur libre : `theme` ne contient que
-- des jetons de la liste fermée (accent, accent_hover, accent_fg, brand_deep), en clair ou
-- sombre, au format #rrggbb (le contraste WCAG AA est vérifié par l'API, api.branding.palette).
-- Logo : chemin interne, https vers un hôte de la liste blanche, ou data-URI d'image bornée.
-- Textes légaux en texte brut (aucun balisage).
CREATE FUNCTION branding_theme_is_closed(p_theme jsonb) RETURNS boolean
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

CREATE TABLE organization_branding (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES organizations (id),
  display_name     text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 80
                                        AND display_name !~ '[<>[:cntrl:]]'),
  logo_kind        text CHECK (logo_kind IN ('url', 'data_uri')),
  logo_src         text CHECK (length(logo_src) <= 43800),
  theme            jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (branding_theme_is_closed(theme)),
  custom_domain    text UNIQUE CHECK (length(custom_domain) <= 253 AND custom_domain
                                      ~ '^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$'),
  -- Preuve de propriété du domaine (CR-P3-02, migration 0005) : jeton propre au domaine
  -- déclaré (enregistrement DNS TXT) et instant de la preuve ; un domaine non prouvé n'est
  -- jamais servi par la lecture publique.
  custom_domain_token        text CONSTRAINT organization_branding_domain_token_check
                               CHECK (custom_domain_token ~ '^[0-9a-f]{32}$'),
  custom_domain_verified_at  timestamptz,
  legal_notice     text CHECK (length(legal_notice) <= 4000 AND legal_notice !~ '[<>]'),
  privacy_notice   text CHECK (length(privacy_notice) <= 4000 AND privacy_notice !~ '[<>]'),
  updated_by       uuid,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CHECK ((logo_kind IS NULL) = (logo_src IS NULL)),
  CHECK (logo_kind IS DISTINCT FROM 'url' OR logo_src ~ '^(/[^/]|https://)'),
  CHECK (logo_kind IS DISTINCT FROM 'data_uri'
         OR logo_src ~ '^data:image/(png|webp|jpeg|svg\+xml);base64,[A-Za-z0-9+/]+={0,2}$'),
  CONSTRAINT organization_branding_domain_proof_check CHECK (
    (custom_domain IS NOT NULL
     OR (custom_domain_token IS NULL AND custom_domain_verified_at IS NULL))
    AND (custom_domain_verified_at IS NULL OR custom_domain_token IS NOT NULL)),
  UNIQUE (organization_id),
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, updated_by) REFERENCES users (organization_id, id)
);
CREATE INDEX organization_branding_updated_by_idx
  ON organization_branding (organization_id, updated_by);

CREATE FUNCTION organization_branding_domain_reverify() RETURNS trigger
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

CREATE TRIGGER organization_branding_domain_reverify
  BEFORE INSERT OR UPDATE ON organization_branding
  FOR EACH ROW EXECUTE FUNCTION organization_branding_domain_reverify();

-- Gabarit de configuration versionné (en ajout seul), propriété de l'organisation
-- « plateforme » : instantané de ses produits, règles, barème et plan de comptes en vigueur.
-- L'accueil d'une organisation COPIE le gabarit dans de nouvelles lignes de l'organisation
-- accueillie (versions `brouillon` à publier par elle) : aucune ligne n'est partagée.
CREATE TABLE configuration_templates (
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
CREATE INDEX configuration_templates_created_by_idx
  ON configuration_templates (organization_id, created_by);

CREATE TRIGGER configuration_templates_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON configuration_templates
  FOR EACH STATEMENT
  EXECUTE FUNCTION forbid_mutation('Publiez une nouvelle version du gabarit.');

-- -----------------------------------------------------------------------------
-- Import de l'existant en lecture seule (L11, R14, ADR-006 ; migration 0006, CR-L11-01 —
-- appliqué sur instruction de Dajan, à valider)
-- -----------------------------------------------------------------------------
-- `import_runs` : journal des imports APPLIQUÉS (un import à blanc n'écrit rien, pas même ce
-- journal). `external_ids` : clé d'origine (source, type, clé) → ligne de One, en ajout seul ;
-- l'unicité (organisation, source, type, clé) rend l'import rejouable sans doublon. Une adresse
-- électronique n'est jamais une clé. `import_status` : statut normalisé de la source pour un
-- adhérent (table de correspondance versionnée, `status_map_version`), p. ex. PENDING_REVIEW
-- pour un adhérent actif dans la source (revue humaine avant toute ouverture de droits dans One).

CREATE TABLE import_runs (
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

CREATE TABLE external_ids (
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
CREATE INDEX external_ids_one_idx ON external_ids (organization_id, kind, one_id);
CREATE INDEX external_ids_run_idx ON external_ids (organization_id, import_run_id);

CREATE FUNCTION import_runs_currency_guard() RETURNS trigger
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

CREATE FUNCTION import_runs_progress_guard() RETURNS trigger
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

CREATE FUNCTION external_ids_target_guard() RETURNS trigger
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

CREATE TRIGGER import_runs_currency_guard
  BEFORE INSERT ON import_runs
  FOR EACH ROW EXECUTE FUNCTION import_runs_currency_guard();

CREATE TRIGGER import_runs_progress_guard
  BEFORE UPDATE ON import_runs
  FOR EACH ROW EXECUTE FUNCTION import_runs_progress_guard();

CREATE TRIGGER external_ids_target_guard
  BEFORE INSERT ON external_ids
  FOR EACH ROW EXECUTE FUNCTION external_ids_target_guard();

CREATE TRIGGER external_ids_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON external_ids
  FOR EACH STATEMENT
  EXECUTE FUNCTION forbid_mutation('Une clé d''origine ne change pas.');

-- -----------------------------------------------------------------------------
-- Tables en ajout seul
-- -----------------------------------------------------------------------------

CREATE TRIGGER ledger_entries_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON ledger_entries
  FOR EACH STATEMENT
  EXECUTE FUNCTION forbid_mutation('Corrigez par une contre-passation.');

CREATE TRIGGER ledger_lines_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON ledger_lines
  FOR EACH STATEMENT
  EXECUTE FUNCTION forbid_mutation('Corrigez par une contre-passation.');

CREATE TRIGGER audit_events_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_events
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();

CREATE TRIGGER ai_actions_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON ai_actions
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();

CREATE TRIGGER claim_decisions_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON claim_decisions
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();

CREATE TRIGGER member_status_history_append_only
  BEFORE UPDATE OR DELETE OR TRUNCATE ON member_status_history
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();

-- -----------------------------------------------------------------------------
-- Versions figées et sans chevauchement (R3)
-- -----------------------------------------------------------------------------

CREATE TRIGGER plan_versions_frozen
  BEFORE UPDATE OR DELETE ON plan_versions
  FOR EACH ROW EXECUTE FUNCTION freeze_published_version();

CREATE TRIGGER plan_versions_no_overlap
  BEFORE INSERT OR UPDATE ON plan_versions
  FOR EACH ROW EXECUTE FUNCTION forbid_overlapping_versions('plan_id', 'plans');

CREATE TRIGGER rule_versions_frozen
  BEFORE UPDATE OR DELETE ON rule_versions
  FOR EACH ROW EXECUTE FUNCTION freeze_published_version();

CREATE TRIGGER rule_versions_no_overlap
  BEFORE INSERT OR UPDATE ON rule_versions
  FOR EACH ROW EXECUTE FUNCTION forbid_overlapping_versions('rule_id', 'rules');

-- -----------------------------------------------------------------------------
-- Isolation par organisation : Row Level Security (R10)
-- -----------------------------------------------------------------------------
-- Chaque table reçoit la même et unique politique, et la RLS est FORCÉE : même le
-- propriétaire y est soumis (seuls un superutilisateur ou un rôle BYPASSRLS y échappent).

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON organizations
  USING (id = app_current_organization_id())
  WITH CHECK (id = app_current_organization_id());

DO $$
DECLARE
  t text;
BEGIN
  FOR t IN
    SELECT c.table_name
    FROM information_schema.columns c
    JOIN information_schema.tables tb
      ON tb.table_schema = c.table_schema AND tb.table_name = c.table_name
    WHERE c.table_schema = current_schema()
      AND c.column_name = 'organization_id'
      AND tb.table_type = 'BASE TABLE'
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I '
      'USING (organization_id = app_current_organization_id()) '
      'WITH CHECK (organization_id = app_current_organization_id())', t);
  END LOOP;
END
$$;

-- Résolutions sans contexte d'organisation, limitées au strict nécessaire :
-- webhook de paiement (organisation dans l'URL) et lien de paiement public (payeur diaspora).
CREATE FUNCTION resolve_organization_by_slug(p_slug text) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT id FROM organizations WHERE slug = p_slug AND status <> 'inactive'
$$;

CREATE FUNCTION resolve_payment_link(p_token_hash text)
RETURNS TABLE (organization_id uuid, contribution_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT organization_id, contribution_id
  FROM payment_links
  WHERE token_hash = p_token_hash AND used_at IS NULL AND expires_at > now()
$$;

-- Marque publique d'une organisation ACTIVE, par identifiant public ou par domaine PROUVÉ
-- (CR-P3-02) : champs non sensibles seulement (aucun identifiant interne, aucun utilisateur,
-- aucune donnée métier). Inconnue, non active ou domaine non prouvé : aucune ligne (même 404).
CREATE FUNCTION resolve_organization_branding(p_slug text, p_domain text)
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

-- Création d'une organisation accueillie, par un administrateur ACTIF d'une organisation
-- « plateforme » ACTIVE (vérifié ici, en plus de la matrice de l'API). Nouvelle organisation en
-- statut `integration`, jamais « plateforme ». MCP01 : refusé ; MCP02 : identifiant déjà pris.
CREATE FUNCTION platform_create_organization(
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

-- -----------------------------------------------------------------------------
-- Rôle applicatif (R7, R10)
-- -----------------------------------------------------------------------------
-- L'API se connecte avec un rôle de connexion membre de `mulema_app` (créé par
-- l'exploitation, jamais ici : pas de mot de passe dans le contrat). `mulema_app` :
-- non propriétaire, sans BYPASSRLS, sans DDL ; privilèges minimaux ci-dessous.
-- Le rôle est global au serveur ; sa création exige CREATEROLE chez le rôle de migration.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mulema_app') THEN
    CREATE ROLE mulema_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO mulema_app;

-- Organisation : lecture seule (créée par l'administration de la plateforme).
GRANT SELECT ON organizations TO mulema_app;

-- Tables métier : lecture, insertion, mise à jour. Aucune suppression ni TRUNCATE.
GRANT SELECT, INSERT, UPDATE ON
  users, employers, providers, provider_conventions, counter_devices, user_roles, persons,
  plans, plan_versions, coverages, acts, tariff_items, members, dependents, cards,
  identity_checks, rules, rule_versions, claims, claim_items, claim_documents, authorizations,
  contributions, payments, payment_links, outbound_messages, ledger_accounts, outbox_events,
  idempotency_keys
TO mulema_app;

-- Purge des clés d'idempotence expirées : seule suppression autorisée.
GRANT DELETE ON idempotency_keys TO mulema_app;

-- Mesure produit (0003) : lecture, ajout, purge par rétention ; jamais de mise à jour.
GRANT SELECT, INSERT, DELETE ON product_events TO mulema_app;

-- Tables en ajout seul : lecture et insertion uniquement.
GRANT SELECT, INSERT ON
  ledger_entries, ledger_lines, audit_events, ai_actions, claim_decisions,
  member_status_history
TO mulema_app;
REVOKE UPDATE, DELETE, TRUNCATE ON
  ledger_entries, ledger_lines, audit_events, ai_actions, claim_decisions,
  member_status_history
FROM mulema_app;

-- Marque blanche (0004) : lecture, création, mise à jour ; gabarits (0004) en ajout seul.
GRANT SELECT, INSERT, UPDATE ON organization_branding TO mulema_app;
GRANT SELECT, INSERT ON configuration_templates TO mulema_app;
REVOKE UPDATE, DELETE, TRUNCATE ON configuration_templates FROM mulema_app;

-- Import de l'existant (0006) : journal en lecture, création, avancement ; clés en ajout seul.
GRANT SELECT, INSERT, UPDATE ON import_runs TO mulema_app;
GRANT SELECT, INSERT ON external_ids TO mulema_app;
REVOKE UPDATE, DELETE, TRUNCATE ON external_ids FROM mulema_app;

-- Résolutions sans contexte : réservées au rôle applicatif.
REVOKE ALL ON FUNCTION resolve_organization_by_slug(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION resolve_payment_link(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_organization_by_slug(text) TO mulema_app;
GRANT EXECUTE ON FUNCTION resolve_payment_link(text) TO mulema_app;
REVOKE ALL ON FUNCTION resolve_organization_branding(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_create_organization(uuid, text, text, text, text, text[], text)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_organization_branding(text, text) TO mulema_app;
GRANT EXECUTE ON FUNCTION platform_create_organization(uuid, text, text, text, text, text[], text)
  TO mulema_app;
