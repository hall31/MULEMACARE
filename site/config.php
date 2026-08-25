<?php
/**
 * MulemaCare Health Group & Mutuelle Santé — Configuration Globale & Taxonomie Panafricaine / Diaspora
 */

return [
    'app' => [
        'name'        => 'MulemaCare Health Group',
        'subname'     => 'Mutuelle Santé Solidaire & Tiers-Payant Afrique',
        'tagline'     => 'La Mutuelle Santé qui protège votre famille au pays et en entreprise, sans avance de frais.',
        'url'         => 'https://mulemacare.com',
        'environment' => 'production',
        'locale'      => 'fr_FR',
        'default_cur' => 'XAF', // XAF, EUR, USD
    ],

    // Base de données Relationnelle MySQL (1&1 IONOS)
    'db' => [
        'host'     => getenv('DB_HOST') ?: 'db5015599908.hosting-data.io',
        'port'     => getenv('DB_PORT') ?: 3306,
        'database' => getenv('DB_NAME') ?: 'dbs12741132',
        'username' => getenv('DB_USER') ?: 'dbu1391065',
        'password' => getenv('DB_PASS') ?: 'Eagle_1983*Icare_2050#Mom1956*Dad1947',
        'charset'  => 'utf8mb4',
    ],

    // Entités Juridiques & Régulation
    'corporate' => [
        'france' => [
            'company_name' => 'SOCIETE E-SANTE MULEMACARE FRANCE',
            'siret'        => '8807 7661 2000 17',
            'address'      => '208 Avenue Aristide Briand, 92220 Bagneux, France',
            'phone'        => '+33 6 59 51 34 58',
            'phone_raw'    => '33659513458',
        ],
        'cameroun' => [
            'company_name' => 'MULEMACARE MUTUELLE SANTÉ CAMEROUN',
            'agreement'    => 'Agrément CSSA n° 045/CSSA/2024',
            'address'      => '85 Avenue de l\'Indépendance / Rue Njo-Njo, Bonapriso, Douala, Cameroun',
            'phone'        => '+237 521 120 21',
            'phone_raw'    => '23752112021',
            'phone_mtn'    => '+237 65 14 58 37',
        ],
    ],

    // Contact, Desk Médical & Réseaux Sociaux Officiels
    'contact' => [
        'email_support'   => 'contact@mulemacare.com',
        'email_rh'        => 'entreprises@mulemacare.com',
        'phone_fr'        => '+33 6 59 51 34 58',
        'phone_cm'        => '+237 521 120 21',
        'phone_mtn'       => '+237 65 14 58 37',
        'whatsapp_fr'     => '33659513458',
        'whatsapp_cm'     => '23752112021',
        'whatsapp_desk'   => '33659513458',
        'phone_display'   => '+33 6 59 51 34 58 (FR) / +237 521 120 21 (CM)',
        'address_fr'      => '208 Avenue Aristide Briand, 92220 Bagneux, France',
        'address_cm'      => '85 Avenue de l\'Indépendance, Douala, Cameroun',
        'facebook'        => 'https://www.facebook.com/Mulemacare-2117419645247839',
        'instagram'       => 'https://www.instagram.com/mulemacare',
        'ga_id'           => 'G-NWCD16MREK',
        'emergency_samu'  => '119 / 15 (Cameroun) • 185 (RDC) • 185 (CI) • 1515 (Sénégal) • 15 (France)',
    ],

    // Moyens de Paiement Mobile Money Officiels (Cameroun & CEMAC)
    'mobile_money' => [
        'orange_money' => [
            'id'            => 'orange_money',
            'name'          => 'Orange Money Cameroun',
            'phone_display' => '+237 521 120 21',
            'phone_raw'     => '23752112021',
            'ussd_syntax'   => '#150*1*1*52112021*MONTANT#',
            'merchant_name' => 'MULEMACARE HEALTH',
        ],
        'mtn_momo' => [
            'id'            => 'mtn_momo',
            'name'          => 'MTN Mobile Money',
            'phone_display' => '+237 65 14 58 37',
            'phone_raw'     => '23765145837',
            'ussd_syntax'   => '*126*1*65145837*MONTANT#',
            'merchant_name' => 'MULEMACARE HEALTH',
        ],
    ],

    // Écosystème MulemaCare Connecté
    'ecosystem' => [
        'lisacare' => [
            'name'        => 'Lisacare Telehealth',
            'tagline'     => 'Télétriage & Consultation Vidéo 24/7 sur WhatsApp',
            'url'         => 'https://lisacare.mulemacare.com',
            'icon'        => 'stethoscope',
            'price_label' => 'Dès 2 000 FCFA / consultation',
            'included'    => 'Illimité & gratuit pour tous les adhérents MulemaCare Silver, Gold & Platinium',
        ],
        'ongwa' => [
            'name'        => 'Ongwa Senior Care',
            'tagline'     => 'Aide, Nursing & Soins à Domicile pour les Parents Âgés',
            'url'         => 'https://ongwa.mulemacare.com',
            'icon'        => 'heart-pulse',
            'price_label' => 'Dès 32 000 FCFA / 49 € par mois',
            'included'    => 'Option intégrée avec visites d\'infirmières et télé-suivi des constantes',
        ],
    ],

    // 1. Grille des 4 Formules Mutuelle Santé
    'plans' => [
        'bronze' => [
            'id'             => 'bronze',
            'name'           => 'Mulema Bronze',
            'headline'       => 'Urgences Vitales & SAMU',
            'badge'          => 'Formule Essentielle',
            'color'          => 'emerald',
            'prices'         => [
                'solo' => [
                    'XAF' => ['amount' => 15000, 'label' => '15 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 25, 'label' => '25 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 28, 'label' => '28 $', 'sub' => '/mois'],
                ],
                'couple' => [
                    'XAF' => ['amount' => 28000, 'label' => '28 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 45, 'label' => '45 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 50, 'label' => '50 $', 'sub' => '/mois'],
                ],
                'family' => [
                    'XAF' => ['amount' => 45000, 'label' => '45 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 75, 'label' => '75 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 82, 'label' => '82 $', 'sub' => '/mois'],
                ],
            ],
            'ceiling_xaf'    => '500 000 FCFA / an / personne (760 €)',
            'features'       => [
                'Hospitalisation d\'urgence prise en charge à 100% (Plafond 500 000 FCFA / an)',
                'Frais de réanimation et chirurgie d\'urgence inclus (Carence 0 jour)',
                'Télétriage & Régulation médicale Lisacare 24/7 (Carence 0 jour)',
                'Transport sanitaire d\'urgence (SAMU / Ambulance)',
                'Carte d\'assuré digitale CSSA avec QR Code',
            ],
            'tiers_payant'   => 'Hospitalisation d\'urgence uniquement',
            'featured'       => false,
        ],
        'silver' => [
            'id'             => 'silver',
            'name'           => 'Mulema Silver',
            'headline'       => 'Soins Courants & Famille',
            'badge'          => 'Le Choix Préféré des Familles',
            'color'          => 'royal',
            'prices'         => [
                'solo' => [
                    'XAF' => ['amount' => 30000, 'label' => '30 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 49, 'label' => '49 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 55, 'label' => '55 $', 'sub' => '/mois'],
                ],
                'couple' => [
                    'XAF' => ['amount' => 55000, 'label' => '55 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 89, 'label' => '89 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 98, 'label' => '98 $', 'sub' => '/mois'],
                ],
                'family' => [
                    'XAF' => ['amount' => 85000, 'label' => '85 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 139, 'label' => '139 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 150, 'label' => '150 $', 'sub' => '/mois'],
                ],
            ],
            'ceiling_xaf'    => '1 500 000 FCFA / an / personne (2 290 €)',
            'features'       => [
                'Hospitalisation médicale & chirurgicale 100% (Plafond 1 500 000 FCFA / an, carence 90j)',
                'Consultations spécialistes & généralistes à 80% (Carence 30j)',
                'Pharmacie certifiée prise en charge à 80% (Carence 30j)',
                'Examens de biologie médicale, radiologie et échographie (Carence 30j)',
                'Maternité : Forfait accouchement & soins nouveau-né (Carence 300j)',
                'Téléconsultation vidéo Lisacare illimitée 24/7 (Carence 0j)',
            ],
            'tiers_payant'   => 'Hospitalisations + Consultations spécialistes + Labo',
            'featured'       => true,
        ],
        'gold' => [
            'id'             => 'gold',
            'name'           => 'Mulema Gold',
            'headline'       => 'Confort Total & Tiers-Payant 100%',
            'badge'          => 'Zéro Avance de Frais',
            'color'          => 'gold',
            'prices'         => [
                'solo' => [
                    'XAF' => ['amount' => 65000, 'label' => '65 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 99, 'label' => '99 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 110, 'label' => '110 $', 'sub' => '/mois'],
                ],
                'couple' => [
                    'XAF' => ['amount' => 120000, 'label' => '120 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 189, 'label' => '189 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 210, 'label' => '210 $', 'sub' => '/mois'],
                ],
                'family' => [
                    'XAF' => ['amount' => 180000, 'label' => '180 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 280, 'label' => '280 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 310, 'label' => '310 $', 'sub' => '/mois'],
                ],
            ],
            'ceiling_xaf'    => '3 500 000 FCFA / an / personne (5 335 €)',
            'features'       => [
                'Tiers-payant 100% intégral en clinique et pharmacie (Plafond 3 500 000 FCFA / an)',
                'Chambre individuelle confort lors des hospitalisations (Carence 90j)',
                'Forfait Optique (Lunettes & Verres) & Soins Dentaires (Carence 180j)',
                'Bilan de santé annuel complet avec bilan sanguin & ECG (Carence 180j)',
                '1 visite soignante à domicile par mois incluse (Ongwa)',
                'Assistance téléphonique prioritaire VIP',
            ],
            'tiers_payant'   => 'Intégral 100% (Cliniques, Labos, Pharmacies, Dentaire, Optique)',
            'featured'       => false,
        ],
        'platinium' => [
            'id'             => 'platinium',
            'name'           => 'Mulema Platinium',
            'headline'       => 'Excellence, Diaspora & Évacuation',
            'badge'          => 'Couverture Internationale',
            'color'          => 'slate',
            'prices'         => [
                'solo' => [
                    'XAF' => ['amount' => 130000, 'label' => '130 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 199, 'label' => '199 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 220, 'label' => '220 $', 'sub' => '/mois'],
                ],
                'couple' => [
                    'XAF' => ['amount' => 240000, 'label' => '240 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 370, 'label' => '370 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 410, 'label' => '410 $', 'sub' => '/mois'],
                ],
                'family' => [
                    'XAF' => ['amount' => 350000, 'label' => '350 000 FCFA', 'sub' => '/mois'],
                    'EUR' => ['amount' => 540, 'label' => '540 €', 'sub' => '/mois'],
                    'USD' => ['amount' => 590, 'label' => '590 $', 'sub' => '/mois'],
                ],
            ],
            'ceiling_xaf'    => '8 000 000 FCFA / an / personne (12 200 €)',
            'features'       => [
                'Plafond annuel maîtrisé de 8 000 000 FCFA (12 200 €) par an et par bénéficiaire',
                'Évacuation sanitaire internationale vers centres d\'excellence (Plafond 8M FCFA, Carence 180j)',
                'Suite VIP d\'hospitalisation avec lit accompagnant (Carence 90j)',
                'Option Ongwa Senior Care complète incluse pour les parents',
                'Conciergerie médicale dédiée 24/7 avec médecin référent personnel',
            ],
            'tiers_payant'   => 'Intégral Monde & Évacuation Sanitaire',
            'featured'       => false,
        ],
    ],

    // Délais de Carence Actuariels & Prudentiels (Marge de rentabilité cible 45%)
    'waiting_periods' => [
        'urgences' => [
            'act'   => 'Accidents & Urgences Vitales (SAMU, Réanimation, Traumatisme)',
            'delay' => '0 jour',
            'desc'  => 'Prise en charge immédiate dès la validation de votre adhésion',
        ],
        'teleconsultation' => [
            'act'   => 'Télétriage & Téléconsultation Lisacare 24/7 sur WhatsApp',
            'delay' => '0 jour',
            'desc'  => 'Accès illimité et instantané au médecin de garde',
        ],
        'soins_courants' => [
            'act'   => 'Consultations Généralistes, Spécialistes & Pharmacie Tiers-Payant',
            'delay' => '30 jours (1 mois)',
            'desc'  => 'Valable pour les soins programmés du quotidien',
        ],
        'hospitalisation' => [
            'act'   => 'Hospitalisation Médicale & Chirurgie Programmée',
            'delay' => '90 jours (3 mois)',
            'desc'  => 'Prise en charge des séjours programmés et interventions',
        ],
        'dentaire_optique' => [
            'act'   => 'Soins Dentaires, Prothèses & Optique Médicale (Gold & Platinium)',
            'delay' => '180 jours (6 mois)',
            'desc'  => 'Forfaits lunettes, verres correcteurs et soins dentaires',
        ],
        'evacuation' => [
            'act'   => 'Évacuation Sanitaire Internationale (Platinium)',
            'delay' => '180 jours (6 mois)',
            'desc'  => 'Hors accidents de la voie publique survenus post-adhésion (0j)',
        ],
        'maternite' => [
            'act'   => 'Maternité, Accouchement & Soins Néonataux',
            'delay' => '300 jours (10 mois)',
            'desc'  => 'Couverture accouchement voie basse, césarienne et suites de couches',
        ],
    ],

    // 2. Offre Santé Collective Entreprises & PME
    'corporate' => [
        'headline'       => 'La Mutuelle Santé PME & Grands Groupes en Afrique',
        'subheadline'    => 'Valorisez votre marque employeur et protégez vos collaborateurs et leurs ayants droit avec une couverture modulable et le tiers-payant direct.',
        'tiers'          => [
            'small'  => ['min' => 5, 'max' => 20, 'discount' => '10% de remise groupe', 'rate_per_employee_xaf' => 25000],
            'medium' => ['min' => 21, 'max' => 100, 'discount' => '20% de remise groupe', 'rate_per_employee_xaf' => 22000],
            'large'  => ['min' => 101, 'max' => 1000, 'discount' => 'Tarif Grands Comptes Sur-Mesure', 'rate_per_employee_xaf' => 18000],
        ],
        'advantages'     => [
            'Déductibilité fiscale intégrale des cotisations patronales',
            'Plateforme RH pour ajout/retrait de salariés en 1 clic',
            'Zéro avance de trésorerie pour les employés en pharmacie et clinique',
            'Rapports de santé au travail anonymisés et bilans de prévention',
        ]
    ],

    // 3. Réseau de Soins Partenaires (45+ Cliniques & Pharmacies)
    'clinics' => [
        'douala' => [
            'city'      => 'Douala',
            'country'   => 'Cameroun',
            'flag'      => '🇨🇲',
            'partners'  => [
                ['name' => 'Polyclinique Mermoz', 'district' => 'Bonapriso', 'type' => 'Hôpital Médico-Chirurgical', 'services' => 'Urgences 24/7, Bloc, Réanimation, Maternité'],
                ['name' => 'Centre Médico-Chirurgical d\'Akwa', 'district' => 'Akwa', 'type' => 'Clinique Spécialisée', 'services' => 'Cardiologie, Imagerie, Chirurgie'],
                ['name' => 'Clinique de l\'Aéroport', 'district' => 'Bonapriso', 'type' => 'Clinique & Maternité', 'services' => 'Pédiatrie, Gynécologie, Laboratoire'],
                ['name' => 'Pharmacie des Nations', 'district' => 'Akwa', 'type' => 'Pharmacie Conventionnée', 'services' => 'Tiers-payant ordonnances, Anti-contrefaçon'],
                ['name' => 'Pharmacie de Bonamoussadi', 'district' => 'Bonamoussadi', 'type' => 'Pharmacie Partenaire', 'services' => 'Délivrance directe sans avance de frais'],
            ]
        ],
        'yaounde' => [
            'city'      => 'Yaoundé',
            'country'   => 'Cameroun',
            'flag'      => '🇨🇲',
            'partners'  => [
                ['name' => 'Centre Médical Bastos', 'district' => 'Bastos', 'type' => 'Polyclinique Internationale', 'services' => 'Urgences, Médecine Interne, Radiologie'],
                ['name' => 'Clinique Sainte Anne', 'district' => 'Omnisports', 'type' => 'Clinique Médico-Chirurgicale', 'services' => 'Chirurgie générale, Pédiatrie'],
                ['name' => 'Pharmacie du Mfoundi', 'district' => 'Centre', 'type' => 'Pharmacie Conventionnée', 'services' => 'Médicaments certifiés & Tiers-payant'],
            ]
        ],
        'kinshasa' => [
            'city'      => 'Kinshasa',
            'country'   => 'RDC',
            'flag'      => '🇨🇩',
            'partners'  => [
                ['name' => 'Centre Médical de la Gombe', 'district' => 'Gombe', 'type' => 'Centre Hospitalier Agréé', 'services' => 'Plateau technique moderne, Urgences 24/7'],
                ['name' => 'Clinique Ngaliema Partenaire', 'district' => 'Ngaliema', 'type' => 'Clinique Polyvalente', 'services' => 'Soins intensifs, Maternité, Cardiologie'],
                ['name' => 'Pharmacie Centrale de Kinshasa', 'district' => 'Limete', 'type' => 'Pharmacie Agréée', 'services' => 'Tiers-payant assuré MulemaCare'],
            ]
        ],
        'abidjan' => [
            'city'      => 'Abidjan',
            'country'   => 'Côte d\'Ivoire',
            'flag'      => '🇨🇮',
            'partners'  => [
                ['name' => 'Polyclinique Sainte Anne-Marie (PISAM)', 'district' => 'Cocody', 'type' => 'Hôpital de Référence', 'services' => 'Grand plateau technique, Chirurgie lourde'],
                ['name' => 'Clinique Médicale Deux-Plateaux', 'district' => 'Deux-Plateaux', 'type' => 'Clinique Spécialisée', 'services' => 'Consultations spécialistes, Pédiatrie'],
                ['name' => 'Grande Pharmacie de Marcory', 'district' => 'Marcory', 'type' => 'Pharmacie Conventionnée', 'services' => 'Tiers-payant 100%'],
            ]
        ],
        'dakar' => [
            'city'      => 'Dakar',
            'country'   => 'Sénégal',
            'flag'      => '🇸🇳',
            'partners'  => [
                ['name' => 'Clinique Madeleine Dakar', 'district' => 'Plateau', 'type' => 'Clinique Médico-Chirurgicale', 'services' => 'Urgences, Soins continus, Maternité'],
                ['name' => 'Centre Médical Almadies', 'district' => 'Almadies', 'type' => 'Polyclinique Moderne', 'services' => 'Cardiologie, Laboratoire d\'analyses'],
                ['name' => 'Pharmacie de la Corniche', 'district' => 'Mermoz', 'type' => 'Pharmacie Conventionnée', 'services' => 'Délivrance ordonnances garanties'],
            ]
        ],
    ],
];
