-- =============================================================================
-- Migration 0002 — espace adhérent (Phase 1, CR-P1-01, appliqué sur instruction de Dajan pour
-- enchaîner la Phase 1 — à valider).
--
-- STRICTEMENT ADDITIVE et REJOUABLE :
--   * une colonne nullable `user_roles.member_id` (aucune ligne existante n'est réécrite) ;
--   * le rôle `adherent` est ajouté à la liste autorisée (la contrainte est élargie : tout ce
--     qui était accepté l'est encore) ;
--   * `member_id` est obligatoire pour `adherent` et interdit pour les autres rôles, ce que
--     toutes les lignes existantes respectent déjà (member_id NULL, rôle différent d'adherent) ;
--   * clé étrangère composite vers `members` (pas de référence inter-organisations) et son index.
-- Chaque instruction est gardée (IF NOT EXISTS, ou suppression puis recréation de la même
-- contrainte) : rejouer ce fichier ne change rien. Les droits de `mulema_app` sur user_roles
-- (SELECT, INSERT, UPDATE) couvrent la nouvelle colonne ; RLS inchangée.
-- =============================================================================

ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS member_id uuid;

ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_role_check;
ALTER TABLE user_roles ADD CONSTRAINT user_roles_role_check
  CHECK (role IN ('gestionnaire', 'medecin_conseil', 'clinique', 'employeur', 'admin',
                  'adherent'));

ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_adherent_scope_check;
ALTER TABLE user_roles ADD CONSTRAINT user_roles_adherent_scope_check
  CHECK ((role = 'adherent') = (member_id IS NOT NULL));

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'user_roles_member_fk' AND conrelid = 'user_roles'::regclass
  ) THEN
    ALTER TABLE user_roles ADD CONSTRAINT user_roles_member_fk
      FOREIGN KEY (organization_id, member_id) REFERENCES members (organization_id, id);
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS user_roles_member_idx ON user_roles (organization_id, member_id);
