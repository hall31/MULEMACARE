-- =============================================================================
-- MulemaCare One — jeu de démonstration FICTIF (lot L0)
--
-- Porte en données les seuils du PRD §5 et les paramètres de produit du prototype.
-- Toutes les valeurs marquées (proto) sont à valider (PRD §10 Q3/Q4, specs/QUESTIONS.md).
-- Ne contient aucune personne, aucun adhérent : uniquement du paramétrage.
-- Pas une migration : se charge à la demande (dev, tests), jamais en production.
-- =============================================================================

-- RLS forcée : le jeu se charge dans le contexte de l'organisation de démonstration.
SELECT set_config('app.organization_id', '00000000-0000-4000-8000-000000000001', true);

INSERT INTO organizations (id, slug, name, country_code, timezone, capabilities, regulator)
VALUES ('00000000-0000-4000-8000-000000000001', 'mulemacare-ci-demo',
        'Mutuelle MulemaCare (démonstration)', 'CI', 'Africa/Abidjan',
        ARRAY['porteur_de_risque', 'gestionnaire'], 'AIRMS');

-- Plan de comptes initial (LOTS.md, L3).
INSERT INTO ledger_accounts (organization_id, code, label, account_class)
SELECT '00000000-0000-4000-8000-000000000001', code, label, account_class
FROM (VALUES
  ('4011', 'Prestataires à payer', 'passif'),
  ('5110', 'Banque', 'actif'),
  ('5121', 'Mobile money · Wave', 'actif'),
  ('5122', 'Mobile money · Orange Money', 'actif'),
  ('6011', 'Prestations santé', 'charge'),
  ('7061', 'Cotisations acquises', 'produit')
) AS a (code, label, account_class);

-- Règles de décision (PRD §5) et règles techniques (R1, R13). Versions et dates d'effet
-- reprises du prototype (« R-12 v3 en vigueur depuis le 01/01/2026 »).
INSERT INTO rules (organization_id, code, label, kind)
SELECT '00000000-0000-4000-8000-000000000001', code, label, kind
FROM (VALUES
  ('R-01', 'Droits ouverts (statut actif, cotisation à jour)', 'droits'),
  ('R-04', 'Prestataire conventionné, barème de l''année', 'reseau'),
  ('R-07', 'Délai de carence écoulé', 'carence'),
  ('R-09', 'Plafond annuel familial restant suffisant', 'plafond'),
  ('R-12', 'Accord automatique', 'accord_automatique'),
  ('R-20', 'Routage vers le médecin-conseil', 'revue'),
  ('ID-03', 'Code SMS : blocage après codes faux', 'identification'),
  ('HL-01', 'Accord provisoire hors ligne', 'hors_ligne')
) AS r (code, label, kind);

INSERT INTO rule_versions (organization_id, rule_id, version, valid_from, params, state)
SELECT r.organization_id, r.id, v.version, v.valid_from, v.params::jsonb, 'en_vigueur'
FROM rules r
JOIN (VALUES
  -- (proto) suspension automatique à J+45 d'impayé (PRD §4 R8).
  ('R-01', 1, DATE '2026-01-01',
   '{"statuts_ouvrant_droits": ["actif"], "suspension_apres_jours_impayes": 45}'),
  ('R-04', 2, DATE '2026-01-01', '{"convention_active_a_la_date_du_soin": true}'),
  -- La durée de carence est portée par la version de produit (60 j en v2, proto).
  ('R-07', 1, DATE '2026-01-01', '{"delai_source": "plan_version"}'),
  ('R-09', 1, DATE '2026-01-01', '{"perimetre": "famille"}'),
  -- (proto) total < 50 000 FCFA et score de fraude < 0,20, bornes exclues.
  ('R-12', 3, DATE '2026-01-01',
   '{"total_max_exclu_xof": 50000, "score_fraude_max_exclu": 0.20}'),
  -- (proto) délai cible de revue : 2 h.
  ('R-20', 2, DATE '2026-01-01', '{"delai_cible_minutes": 120}'),
  -- (proto) trois codes faux bloquent la carte 15 min (PRD §4 R1).
  ('ID-03', 1, DATE '2026-01-01', '{"codes_faux_avant_blocage": 3, "duree_blocage_minutes": 15}'),
  -- (proto) accord provisoire valable 2 h ; seuil = celui de R-12 (PRD §4 R13).
  ('HL-01', 1, DATE '2026-01-01', '{"validite_accord_provisoire_minutes": 120}')
) AS v (code, version, valid_from, params) ON v.code = r.code
WHERE r.organization_id = '00000000-0000-4000-8000-000000000001';

-- Produit « Santé Famille Or » et ses versions (prototype, écran Produits).
INSERT INTO plans (id, organization_id, code, name)
VALUES ('00000000-0000-4000-8000-000000000101', '00000000-0000-4000-8000-000000000001',
        'FAMILLE-OR', 'Santé Famille Or');

INSERT INTO plan_versions (id, organization_id, plan_id, version, valid_from, valid_to, state,
                           coverage_rate_bp, family_annual_ceiling_xof, waiting_period_days,
                           monthly_contribution_xof)
VALUES
  ('00000000-0000-4000-8000-000000000111', '00000000-0000-4000-8000-000000000001',
   '00000000-0000-4000-8000-000000000101', 1, DATE '2025-01-01', DATE '2025-12-31', 'cloturee',
   8000, 2500000, 90, 27500),
  ('00000000-0000-4000-8000-000000000112', '00000000-0000-4000-8000-000000000001',
   '00000000-0000-4000-8000-000000000101', 2, DATE '2026-01-01', DATE '2026-12-31',
   'en_vigueur', 8000, 3000000, 60, 27500),
  ('00000000-0000-4000-8000-000000000113', '00000000-0000-4000-8000-000000000001',
   '00000000-0000-4000-8000-000000000101', 3, DATE '2027-01-01', NULL, 'brouillon',
   8000, 3200000, 60, 27500);

-- Garanties de la version 2 (prototype, onglet Garanties).
INSERT INTO coverages (organization_id, plan_version_id, category, label, annual_limit_xof)
SELECT '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000112',
       category, label, annual_limit_xof
FROM (VALUES
  ('soins_courants', 'Soins courants', NULL::bigint),
  ('hospitalisation', 'Hospitalisation', 1800000),
  ('optique', 'Optique', 90000),
  ('dentaire', 'Dentaire', 150000),
  ('maternite', 'Maternité', 400000)
) AS c (category, label, annual_limit_xof);

-- Nomenclature et barème conventionné (prototype, comptoir).
INSERT INTO acts (organization_id, code, label, coverage_category)
SELECT '00000000-0000-4000-8000-000000000001', code, label, 'soins_courants'
FROM (VALUES
  ('CONS-GEN', 'Consultation généraliste'),
  ('BIO-NFS', 'NFS (numération)'),
  ('CARD-ECG', 'ECG'),
  ('IMG-ECHO-ABD', 'Échographie abdominale'),
  ('IMG-RX-THO', 'Radiographie thorax'),
  ('CONS-SPE', 'Consultation spécialiste')
) AS a (code, label);

INSERT INTO tariff_items (organization_id, act_id, amount_xof, valid_from, valid_to)
SELECT a.organization_id, a.id, t.amount_xof, t.valid_from, t.valid_to
FROM acts a
JOIN (VALUES
  ('CONS-GEN', 22000, DATE '2025-01-01', DATE '2025-12-31'),
  ('CONS-GEN', 25000, DATE '2026-01-01', NULL),
  ('BIO-NFS', 8000, DATE '2026-01-01', NULL),
  ('CARD-ECG', 15000, DATE '2026-01-01', NULL),
  ('IMG-ECHO-ABD', 30000, DATE '2026-01-01', NULL),
  ('IMG-RX-THO', 18000, DATE '2026-01-01', NULL),
  ('CONS-SPE', 35000, DATE '2026-01-01', NULL)
) AS t (code, amount_xof, valid_from, valid_to) ON t.code = a.code
WHERE a.organization_id = '00000000-0000-4000-8000-000000000001';
