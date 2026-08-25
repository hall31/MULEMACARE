-- MulemaCare MySQL Database Dump
-- Database: dbs12741132
-- Generated at: 2026-08-25 01:44:13

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `mulema_admin_users`;
CREATE TABLE `mulema_admin_users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` enum('superadmin','doctor','claims_manager','accountant','partner_agent') COLLATE utf8mb4_unicode_ci DEFAULT 'claims_manager',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `mulema_beneficiaries`;
CREATE TABLE `mulema_beneficiaries` (
  `id` int NOT NULL AUTO_INCREMENT,
  `subscriber_id` int NOT NULL,
  `full_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `birth_date` date DEFAULT NULL,
  `relationship` enum('self','spouse','child','parent','employee') COLLATE utf8mb4_unicode_ci DEFAULT 'self',
  `photo_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('active','inactive') COLLATE utf8mb4_unicode_ci DEFAULT 'active',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sub_id` (`subscriber_id`),
  CONSTRAINT `fk_sub_beneficiary` FOREIGN KEY (`subscriber_id`) REFERENCES `mulema_subscribers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `mulema_cards`;
CREATE TABLE `mulema_cards` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cssa_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `subscriber_id` int NOT NULL,
  `beneficiary_id` int DEFAULT NULL,
  `card_holder_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `plan` enum('bronze','silver','gold','platinium') COLLATE utf8mb4_unicode_ci NOT NULL,
  `annual_cap` decimal(12,2) NOT NULL,
  `consumed_cap` decimal(12,2) DEFAULT '0.00',
  `currency` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT 'XAF',
  `valid_until` date NOT NULL,
  `qr_hash` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tiers_payant_status` enum('active','suspended','expired') COLLATE utf8mb4_unicode_ci DEFAULT 'active',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `cssa_number` (`cssa_number`),
  KEY `idx_cssa` (`cssa_number`),
  KEY `fk_card_sub` (`subscriber_id`),
  CONSTRAINT `fk_card_sub` FOREIGN KEY (`subscriber_id`) REFERENCES `mulema_subscribers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `mulema_cards` (`id`, `cssa_number`, `subscriber_id`, `beneficiary_id`, `card_holder_name`, `plan`, `annual_cap`, `consumed_cap`, `currency`, `valid_until`, `qr_hash`, `tiers_payant_status`, `created_at`) VALUES
('1', 'CSSA-A2FA-26', '1', NULL, 'Jean-Paul Kamga', 'gold', '6000000.00', '0.00', 'EUR', '2027-08-25', '7090eeabfcf53fa4', 'active', '2026-08-25 01:43:26');

DROP TABLE IF EXISTS `mulema_claims`;
CREATE TABLE `mulema_claims` (
  `id` int NOT NULL AUTO_INCREMENT,
  `claim_reference` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `cssa_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `partner_id` int NOT NULL,
  `patient_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `act_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `total_amount` decimal(12,2) NOT NULL,
  `covered_amount` decimal(12,2) NOT NULL,
  `currency` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT 'XAF',
  `status` enum('approved','pending_approval','rejected','reimbursed_to_clinic') COLLATE utf8mb4_unicode_ci DEFAULT 'approved',
  `invoice_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `settlement_batch_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `claim_reference` (`claim_reference`),
  KEY `idx_claim_cssa` (`cssa_number`),
  KEY `idx_claim_partner` (`partner_id`),
  CONSTRAINT `fk_claim_partner` FOREIGN KEY (`partner_id`) REFERENCES `mulema_partners` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `mulema_partners`;
CREATE TABLE `mulema_partners` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `city` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `district` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` enum('clinic','pharmacy','center') COLLATE utf8mb4_unicode_ci NOT NULL,
  `tiers_payant` tinyint(1) DEFAULT '1',
  `rating` decimal(2,1) DEFAULT '4.5',
  `specialties` text COLLATE utf8mb4_unicode_ci,
  `phone` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_city_type` (`city`,`type`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `mulema_partners` (`id`, `name`, `city`, `district`, `type`, `tiers_payant`, `rating`, `specialties`, `phone`, `email`, `is_active`, `created_at`) VALUES
('1', 'Clinique de l\'Étoile', 'douala', 'Bonapriso', 'clinic', '1', '4.7', 'Urgences 24/7, Imagerie, Maternité', NULL, NULL, '1', '2026-08-25 01:42:44'),
('2', 'Polyclinique Bonanjo', 'douala', 'Bonanjo', 'clinic', '1', '4.5', 'Cardiologie, Laboratoire', NULL, NULL, '1', '2026-08-25 01:42:44'),
('3', 'Centre Médical Bonamoussadi', 'douala', 'Bonamoussadi', 'center', '0', '4.2', 'Médecine générale, Vaccination', NULL, NULL, '1', '2026-08-25 01:42:44'),
('4', 'Pharmacie du Centre', 'douala', 'Akwa', 'pharmacy', '1', '4.6', 'Garde 24/7, Tiers-payant', NULL, NULL, '1', '2026-08-25 01:42:44'),
('5', 'Clinique Bastos', 'yaounde', 'Bastos', 'clinic', '1', '4.8', 'Urgences, Pédiatrie, Maternité', NULL, NULL, '1', '2026-08-25 01:42:44'),
('6', 'Clinique de la Cathédrale', 'yaounde', 'Centre-ville', 'clinic', '1', '4.4', 'Spécialistes, Laboratoire', NULL, NULL, '1', '2026-08-25 01:42:44'),
('7', 'Pharmacie Obili', 'yaounde', 'Obili', 'pharmacy', '1', '4.3', 'Garde de nuit', NULL, NULL, '1', '2026-08-25 01:42:44'),
('8', 'Clinique Ngaliema', 'kinshasa', 'Gombe', 'clinic', '1', '4.6', 'Urgences, Imagerie', NULL, NULL, '1', '2026-08-25 01:42:44'),
('9', 'Centre Médical du Fleuve', 'kinshasa', 'Gombe', 'center', '1', '4.5', 'Médecine générale, Laboratoire', NULL, NULL, '1', '2026-08-25 01:42:44'),
('10', 'Pharmacie du Boulevard', 'kinshasa', 'Gombe', 'pharmacy', '0', '4.1', 'Ouvert 7j/7', NULL, NULL, '1', '2026-08-25 01:42:44'),
('11', 'Clinique PISAM', 'abidjan', 'Cocody', 'clinic', '1', '4.7', 'Urgences, Cardiologie, Maternité', NULL, NULL, '1', '2026-08-25 01:42:44'),
('12', 'Pharmacie Cocody Centre', 'abidjan', 'Cocody', 'pharmacy', '1', '4.4', 'Tiers-payant', NULL, NULL, '1', '2026-08-25 01:42:44'),
('13', 'Clinique de la Madeleine', 'dakar', 'Point E', 'clinic', '1', '4.6', 'Urgences, Néonatologie', NULL, NULL, '1', '2026-08-25 01:42:44'),
('14', 'Pharmacie Mermoz', 'dakar', 'Mermoz', 'pharmacy', '1', '4.2', 'Garde 24/7', NULL, NULL, '1', '2026-08-25 01:42:44');

DROP TABLE IF EXISTS `mulema_payments`;
CREATE TABLE `mulema_payments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `subscriber_id` int NOT NULL,
  `amount` decimal(12,2) NOT NULL,
  `currency` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `payment_method` enum('card','apple','om','momo','sepa') COLLATE utf8mb4_unicode_ci NOT NULL,
  `payment_reference` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `period` enum('monthly','annual') COLLATE utf8mb4_unicode_ci DEFAULT 'monthly',
  `status` enum('succeeded','pending','failed') COLLATE utf8mb4_unicode_ci DEFAULT 'succeeded',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_payment_sub` (`subscriber_id`),
  CONSTRAINT `fk_payment_sub` FOREIGN KEY (`subscriber_id`) REFERENCES `mulema_subscribers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `mulema_payments` (`id`, `subscriber_id`, `amount`, `currency`, `payment_method`, `payment_reference`, `period`, `status`, `created_at`) VALUES
('1', '1', '280.00', 'EUR', 'card', NULL, 'monthly', 'succeeded', '2026-08-25 01:43:26');

DROP TABLE IF EXISTS `mulema_subscribers`;
CREATE TABLE `mulema_subscribers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `membership_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `residence_type` enum('diaspora','local') COLLATE utf8mb4_unicode_ci DEFAULT 'diaspora',
  `full_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `country_code` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT '+237',
  `city` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'douala',
  `status` enum('active','pending','suspended','cancelled') COLLATE utf8mb4_unicode_ci DEFAULT 'active',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `membership_id` (`membership_id`),
  KEY `idx_email` (`email`),
  KEY `idx_membership` (`membership_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `mulema_subscribers` (`id`, `membership_id`, `residence_type`, `full_name`, `email`, `phone`, `country_code`, `city`, `status`, `created_at`, `updated_at`) VALUES
('1', 'ADH-1A036284F54', 'diaspora', 'Jean-Paul Kamga', 'jp.kamga@example.com', '+33 6 12 34 56 78', '+237', 'douala', 'active', '2026-08-25 01:43:26', '2026-08-25 01:43:26');

SET FOREIGN_KEY_CHECKS = 1;
