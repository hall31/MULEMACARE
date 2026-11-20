-- Jeu FICTIF : au moins une ligne dans chaque table, pour l'organisation __ORG__.
-- Chargé par le propriétaire (test d'isolation R10). Toute nouvelle table doit y être ajoutée,
-- sinon test_isolation.py::test_le_jeu_couvre_chaque_table échoue.
DO $$
DECLARE
  o uuid := '__ORG__';
  u uuid; emp uuid; prov uuid; dev uuid; pers uuid; pers2 uuid; pl uuid; pv uuid;
  act uuid; tar uuid; mem uuid; card uuid; idc uuid; rl uuid; clm uuid; contr uuid;
  acc_d uuid; acc_c uuid; ent uuid; run uuid;
BEGIN
  PERFORM set_config('app.organization_id', o::text, true);

  INSERT INTO organizations (id, slug, name, country_code, timezone, capabilities)
  VALUES (o, '__SLUG__', 'Organisation fictive __SLUG__', 'CI', 'Africa/Abidjan',
          ARRAY['porteur_de_risque', 'gestionnaire']);
  INSERT INTO users (organization_id, idp_subject, display_name)
  VALUES (o, 'sub-__SLUG__', 'Agent fictif') RETURNING id INTO u;
  INSERT INTO employers (organization_id, name, contract_start)
  VALUES (o, 'Employeur fictif', DATE '2026-01-01') RETURNING id INTO emp;
  INSERT INTO providers (organization_id, name, kind, city, country_code)
  VALUES (o, 'Clinique fictive', 'clinique', 'Abidjan', 'CI') RETURNING id INTO prov;
  INSERT INTO provider_conventions (organization_id, provider_id, valid_from)
  VALUES (o, prov, DATE '2026-01-01');
  INSERT INTO counter_devices (organization_id, provider_id, label, public_key)
  VALUES (o, prov, 'Comptoir 1', 'cle-publique-fictive') RETURNING id INTO dev;
  INSERT INTO user_roles (organization_id, user_id, role, provider_id)
  VALUES (o, u, 'clinique', prov);
  INSERT INTO persons (organization_id, given_name, family_name, birth_date)
  VALUES (o, 'Prénom', 'Fictif', DATE '1990-01-01') RETURNING id INTO pers;
  INSERT INTO persons (organization_id, given_name, family_name, birth_date)
  VALUES (o, 'Enfant', 'Fictif', DATE '2020-01-01') RETURNING id INTO pers2;
  INSERT INTO plans (organization_id, code, name)
  VALUES (o, 'FORMULE-T', 'Formule test') RETURNING id INTO pl;
  INSERT INTO plan_versions (organization_id, plan_id, version, valid_from, state,
                             coverage_rate_bp, family_annual_ceiling_xof,
                             waiting_period_days, monthly_contribution_xof)
  VALUES (o, pl, 1, DATE '2026-01-01', 'en_vigueur', 8000, 3000000, 60, 27500)
  RETURNING id INTO pv;
  INSERT INTO coverages (organization_id, plan_version_id, category, label)
  VALUES (o, pv, 'soins_courants', 'Soins courants');
  INSERT INTO acts (organization_id, code, label, coverage_category)
  VALUES (o, 'CONS-GEN', 'Consultation', 'soins_courants') RETURNING id INTO act;
  INSERT INTO tariff_items (organization_id, act_id, amount_xof, valid_from)
  VALUES (o, act, 25000, DATE '2026-01-01') RETURNING id INTO tar;
  INSERT INTO members (organization_id, person_id, member_number, plan_id, employer_id, status,
                       enrolled_on, waiting_period_ends_on)
  VALUES (o, pers, 'MC-00000001', pl, emp, 'actif', DATE '2026-01-01', DATE '2026-03-02')
  RETURNING id INTO mem;
  INSERT INTO member_status_history (organization_id, member_id, to_status, reason_code)
  VALUES (o, mem, 'actif', 'adhesion');
  INSERT INTO dependents (organization_id, member_id, person_id, relationship, valid_from)
  VALUES (o, mem, pers2, 'enfant', DATE '2026-01-01');
  INSERT INTO cards (organization_id, member_id, person_id, qr_secret_ciphertext)
  VALUES (o, mem, pers, '\x00'::bytea) RETURNING id INTO card;
  INSERT INTO identity_checks (organization_id, card_id, provider_id, operator_user_id)
  VALUES (o, card, prov, u) RETURNING id INTO idc;
  INSERT INTO rules (organization_id, code, label, kind)
  VALUES (o, 'R-12', 'Accord automatique', 'accord_automatique') RETURNING id INTO rl;
  INSERT INTO rule_versions (organization_id, rule_id, version, valid_from, params, state)
  VALUES (o, rl, 3, DATE '2026-01-01', '{"total_max_exclu_xof": 50000}', 'en_vigueur');
  INSERT INTO claims (organization_id, claim_number, member_id, beneficiary_person_id,
                      provider_id, identity_check_id, channel, service_date, plan_version_id,
                      status, total_xof, covered_xof, patient_share_xof, decision_rule_id,
                      decision_rule_version, created_by)
  VALUES (o, 'PEC-26-00001', mem, pers, prov, idc, 'comptoir', DATE '2026-09-30', pv,
          'accordee_auto', 25000, 20000, 5000, rl, 3, u)
  RETURNING id INTO clm;
  INSERT INTO claim_items (organization_id, claim_id, line_no, act_id, tariff_item_id,
                           unit_amount_xof, amount_xof, covered_xof)
  VALUES (o, clm, 1, act, tar, 25000, 25000, 20000);
  INSERT INTO claim_decisions (organization_id, claim_id, sequence, outcome, source, rule_id,
                               rule_version, reason_code)
  VALUES (o, clm, 1, 'accordee_auto', 'regle', rl, 3, 'R-12');
  INSERT INTO claim_documents (organization_id, claim_id, kind, healthos_document_ref,
                               submitted_by)
  VALUES (o, clm, 'facture', 'doc-fictif-1', u);
  INSERT INTO authorizations (organization_id, authorization_number, claim_id, kind, status,
                              covered_xof, rule_id, rule_version, issued_at, expires_at,
                              device_id, offline_ref, device_signature, signed_payload)
  VALUES (o, 'ACC-00001', clm, 'provisoire_hors_ligne', 'synchronisee', 20000, rl, 3,
          now() - interval '1 hour', now() + interval '1 hour', dev, gen_random_uuid(),
          'signature-fictive', '{}'::jsonb);
  INSERT INTO contributions (organization_id, member_id, period_start, due_on, amount_xof)
  VALUES (o, mem, DATE '2026-10-01', DATE '2026-10-05', 27500) RETURNING id INTO contr;
  INSERT INTO payments (organization_id, contribution_id, channel, provider_reference,
                        amount_xof, status, payer_kind)
  VALUES (o, contr, 'simulation', 'ref-__SLUG__', 27500, 'en_attente', 'proche');
  INSERT INTO payment_links (organization_id, contribution_id, token_hash, expires_at)
  VALUES (o, contr, 'hash-__SLUG__', now() + interval '1 day');
  INSERT INTO outbound_messages (organization_id, person_id, channel, template_code)
  VALUES (o, pers, 'sms', 'relance_cotisation');
  INSERT INTO ledger_accounts (organization_id, code, label, account_class)
  VALUES (o, '6011', 'Prestations santé', 'charge') RETURNING id INTO acc_d;
  INSERT INTO ledger_accounts (organization_id, code, label, account_class)
  VALUES (o, '4011', 'Prestataires à payer', 'passif') RETURNING id INTO acc_c;
  INSERT INTO ledger_entries (organization_id, entry_number, accounting_date, label,
                              source_type, source_id)
  VALUES (o, 'J-00001', DATE '2026-09-30', 'Accord', 'prise_en_charge', clm)
  RETURNING id INTO ent;
  INSERT INTO ledger_lines (organization_id, entry_id, line_no, account_id, debit_xof,
                            provider_id)
  VALUES (o, ent, 1, acc_d, 20000, prov);
  INSERT INTO ledger_lines (organization_id, entry_id, line_no, account_id, credit_xof,
                            provider_id)
  VALUES (o, ent, 2, acc_c, 20000, prov);
  INSERT INTO audit_events (organization_id, actor_user_id, action, target_type, target_id)
  VALUES (o, u, 'claim.medical_reason.read', 'claim', clm);
  INSERT INTO ai_actions (organization_id, user_id, kind, tool, sources)
  VALUES (o, u, 'reponse', 'lire_dossier', jsonb_build_array(jsonb_build_object(
          'type', 'claim', 'id', clm)));
  INSERT INTO idempotency_keys (organization_id, scope, key, request_hash, expires_at)
  VALUES (o, 'command:claim.create', 'cle-__SLUG__', 'empreinte', now() + interval '1 day');
  INSERT INTO outbox_events (organization_id, event_type, aggregate_id, payload)
  VALUES (o, 'claim.decided', clm, '{}'::jsonb);
  -- Mesure produit (0003) : un événement neutre, compté par aucun agrégat.
  INSERT INTO product_events (organization_id, name, surface, role, session_ref, occurred_at,
                              expires_at)
  VALUES (o, 'offline_banner_seen', 'comptoir', 'clinique',
          md5('session-__SLUG__') || md5('jour-__SLUG__'), now(), now() + interval '90 days');
  -- Marque blanche et gabarit de configuration (0004) : une ligne chacun.
  INSERT INTO organization_branding (organization_id, display_name, theme, updated_by)
  VALUES (o, 'Marque fictive __SLUG__', '{"light": {"accent": "#1d4ed8"}}'::jsonb, u);
  INSERT INTO configuration_templates (organization_id, code, version, country_code, label,
                                       payload, created_by)
  VALUES (o, 'gabarit-__SLUG__', 1, 'CI', 'Gabarit fictif', '{"plans": []}'::jsonb, u);
  -- Import de l'existant (0006) : un journal et une clé d'origine fictive.
  INSERT INTO import_runs (organization_id, source, spec_version, status_map_version,
                           source_currency)
  VALUES (o, 'laravel_2026', 'laravel-2026.1', 'statuts-2026-10-02.1', 'XOF')
  RETURNING id INTO run;
  INSERT INTO external_ids (organization_id, source, kind, key_name, external_key, one_id,
                            import_run_id, import_status, status_map_version)
  VALUES (o, 'laravel_2026', 'member', 'subscription_number',
          'subscription_number:SUB-__SLUG__', mem, run, 'PENDING_REVIEW',
          'statuts-2026-10-02.1');
END
$$;
