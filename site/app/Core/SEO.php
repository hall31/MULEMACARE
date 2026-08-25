<?php
declare(strict_types=1);

namespace App\Core;

/**
 * Moteur SEO, GEO (Generative Engine Optimization) & AI Search pour MulemaCare Health Group
 */
class SEO {
    private array $config;
    private string $title;
    private string $description;
    private string $canonicalUrl;
    private array $keywords;
    private string $ogImage;
    private string $currentPath;
    private string $pageType;
    private ?array $pageData;

    public function __construct(array $config, string $currentPath = '/', ?array $pageData = null, string $pageType = 'home') {
        $this->config = $config;
        $this->currentPath = $currentPath;
        $this->pageData = $pageData;
        $this->pageType = $pageType;

        $baseUrl = rtrim($this->config['app']['url'], '/');
        $this->canonicalUrl = $baseUrl . ($currentPath === '/' ? '' : $currentPath);
        $this->ogImage = $baseUrl . '/assets/img/logo.png';

        $this->computeMetadata();
    }

    private function computeMetadata(): void {
        switch ($this->pageType) {
            case 'mutuelle':
                $this->title = "Mutuelle Santé Afrique & Diaspora — Devis Immédiat & Tiers-Payant | MulemaCare";
                $this->description = "Découvrez nos 4 formules de mutuelle santé (Bronze, Silver, Gold, Platinium) avec prise en charge à 100% des hospitalisations et tiers-payant sans avance de frais dans 45+ cliniques.";
                $this->keywords = ["mutuelle santé afrique", "assurance santé cameroun", "mutuelle famille diaspora", "tiers payant clinique douala", "assurance santé abidjan", "mutuelle kinshasa", "assurance rapatriement afrique"];
                break;

            case 'entreprises':
                $this->title = "Mutuelle Santé Entreprise & PME en Afrique — Couverture Collective 100% Déductible | MulemaCare Pro";
                $this->description = "Offrez le tiers-payant direct en clinique à vos salariés et leurs familles. Déductibilité fiscale 100% (CGI/OHADA), gestion RH dématérialisée et téléconsultation 24/7.";
                $this->keywords = ["mutuelle entreprise cameroun", "assurance santé collective afrique", "couverture maladie salariés abidjan", "mutuelle pme kinshasa", "assurance groupe afrique", "santé travail douala yaounde"];
                break;

            case 'reseau':
                $this->title = "Réseau de Soins Agréé & 45+ Cliniques Partenaires Tiers-Payant | MulemaCare";
                $this->description = "Accédez à plus de 45 hôpitaux, polycliniques et pharmacies conventionnées à Douala, Yaoundé, Kinshasa, Abidjan et Dakar sans faire aucune avance de frais.";
                $this->keywords = ["cliniques partenaires mulemacare", "tiers payant clinique douala", "pharmacie conventionnee yaounde", "hopital agree abidjan", "soins kinshasa sans avance", "clinique de l etoile bonapriso", "polyclinique bonanjo"];
                break;

            case 'pays':
                $countryName = $this->pageData['name'] ?? 'Afrique';
                $flag = $this->pageData['flag'] ?? '🌍';
                $this->title = "Mutuelle Santé {$countryName} {$flag} — Tiers-Payant & Soins Famille au Pays | MulemaCare";
                $this->description = "Assurez votre famille en {$countryName} sans avance de frais dès 23 € / 15 000 FCFA/mois. Prise en charge immédiate en clinique, télétriage Lisacare 24/7 et visites Ongwa.";
                $this->keywords = ["mutuelle santé {$countryName}", "assurance maladie {$countryName}", "tiers payant {$countryName}", "soins famille {$countryName} diaspora", "cliniques agreees {$countryName}"];
                break;

            case 'partenaires':
                $this->title = "Devenir Établissement Partenaire & Réseau Tiers-Payant | MulemaCare";
                $this->description = "Rejoignez le 1er réseau de santé tiers-payant en Afrique subsaharienne. Règlement garanti sous 72h, validation QR instantanée et 12 400+ assurés solvables orientés vers votre structure.";
                $this->keywords = ["convention clinique mulemacare", "devenir partenaire tiers payant afrique", "conventionnement pharmacie douala", "reseau soins agree cameroun", "partenariat sante abidjan", "convention hopital kinshasa"];
                break;

            case 'carte':
                $member = $this->pageData['name'] ?? 'Adhérent';
                $this->title = "Vérification Carte Mutuelle CSSA — {$member} | MulemaCare";
                $this->description = "Vérification cryptographique en temps réel des droits de prise en charge tiers-payant de l'assuré MulemaCare Health Group.";
                $this->keywords = ["verification carte mutuelle", "cssa tiers payant", "prise en charge clinique mulemacare", "qr code sante mulema"];
                break;

            case 'home':
            default:
                $this->title = "MulemaCare Health Group — Mutuelle Santé Solidaire, Tiers-Payant & Soins en Afrique";
                $this->description = "La première mutuelle santé digitale pour l'Afrique et la Diaspora. Cotisez depuis l'Europe ou l'Afrique, protégez vos proches au pays sans avance de frais dans 45+ cliniques partenaires. Télémédecine 24/7 incluse.";
                $this->keywords = [
                    "mutuelle santé diaspora cameroun",
                    "assurance santé famille afrique sans avance de frais",
                    "tiers payant sans avance de frais",
                    "mutuelle famille diaspora",
                    "payer mutuelle parents afrique",
                    "télémédecine afrique lisacare",
                    "soins à domicile seniors ongwa",
                    "assurance maladie douala yaounde",
                    "mutuelle santé kinshasa",
                    "assurance santé abidjan",
                    "mutuelle dakar senegal"
                ];
                break;
        }
    }

    public function renderMetaTags(): string {
        $kw = implode(', ', $this->keywords);
        $baseUrl = rtrim($this->config['app']['url'], '/');

        return <<<HTML
    <!-- Primary SEO Meta Tags -->
    <title>{$this->title}</title>
    <meta name="title" content="{$this->title}">
    <meta name="description" content="{$this->description}">
    <meta name="keywords" content="{$kw}">
    <meta name="author" content="SOCIETE E-SANTE MULEMACARE FRANCE & MulemaCare Health Group">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">

    <!-- Canonical & Alternate Hreflang (International Diaspora & African Hubs) -->
    <link rel="canonical" href="{$this->canonicalUrl}">
    <link rel="alternate" hreflang="fr-FR" href="{$baseUrl}/diaspora/france">
    <link rel="alternate" hreflang="fr-BE" href="{$baseUrl}/diaspora/belgique">
    <link rel="alternate" hreflang="fr-CA" href="{$baseUrl}/diaspora/canada">
    <link rel="alternate" hreflang="fr-CH" href="{$baseUrl}/diaspora/suisse">
    <link rel="alternate" hreflang="fr-CM" href="{$baseUrl}/pays/cameroun">
    <link rel="alternate" hreflang="fr-CD" href="{$baseUrl}/pays/rdc">
    <link rel="alternate" hreflang="fr-CI" href="{$baseUrl}/pays/cote-divoire">
    <link rel="alternate" hreflang="fr-SN" href="{$baseUrl}/pays/senegal">
    <link rel="alternate" hreflang="fr-GA" href="{$baseUrl}/pays/gabon">
    <link rel="alternate" hreflang="fr-CG" href="{$baseUrl}/pays/congo">
    <link rel="alternate" hreflang="fr" href="{$baseUrl}/">
    <link rel="alternate" hreflang="x-default" href="{$baseUrl}/">

    <!-- Theme & Colors -->
    <meta name="theme-color" content="#097268">

    <!-- Open Graph / WhatsApp / Facebook Preview Card -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="{$this->canonicalUrl}">
    <meta property="og:title" content="{$this->title}">
    <meta property="og:description" content="{$this->description}">
    <meta property="og:image" content="{$this->ogImage}">
    <meta property="og:locale" content="fr_FR">
    <meta property="og:site_name" content="MulemaCare Health Group">

    <!-- Twitter Summary Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{$this->title}">
    <meta name="twitter:description" content="{$this->description}">
    <meta name="twitter:image" content="{$this->ogImage}">
HTML;
    }

    public function renderSchemaOrgJsonLd(): string {
        $baseUrl = rtrim($this->config['app']['url'], '/');
        $appName = $this->config['app']['name'];

        $graph = [
            // 1. Medical Organization
            [
                '@type' => 'MedicalOrganization',
                '@id' => "{$baseUrl}/#organization",
                'name' => $appName,
                'legalName' => 'SOCIETE E-SANTE MULEMACARE FRANCE',
                'alternateName' => 'MulemaCare Health Group & Mutuelle Santé Solidaire',
                'url' => $baseUrl,
                'logo' => "{$baseUrl}/assets/logo.png",
                'image' => $this->ogImage,
                'description' => $this->description,
                'telephone' => '+33 6 59 51 34 58',
                'email' => 'contact@mulemacare.com',
                'taxID' => '8807 7661 2000 17',
                'priceRange' => '15000 XAF - 75400 XAF / 23 EUR - 115 EUR',
                'currenciesAccepted' => 'XAF, EUR, USD, CAD, CHF, GBP, XOF, CDF',
                'paymentAccepted' => 'Carte Bancaire, Stripe, Apple Pay, Orange Money, MTN Mobile Money',
                'address' => [
                    [
                        '@type' => 'PostalAddress',
                        'streetAddress' => '208 Avenue Aristide Briand',
                        'addressLocality' => 'Bagneux',
                        'postalCode' => '92220',
                        'addressCountry' => 'FR'
                    ],
                    [
                        '@type' => 'PostalAddress',
                        'streetAddress' => '85 Avenue de l\'Indépendance / Rue Njo-Njo',
                        'addressLocality' => 'Douala',
                        'addressRegion' => 'Littoral',
                        'addressCountry' => 'CM'
                    ]
                ],
                'sameAs' => [
                    'https://www.facebook.com/Mulemacare-2117419645247839',
                    'https://www.instagram.com/mulemacare',
                    'https://wa.me/33659513458',
                    'https://wa.me/23752112021'
                ],
                'aggregateRating' => [
                    '@type' => 'AggregateRating',
                    'ratingValue' => '4.8',
                    'bestRating' => '5',
                    'worstRating' => '1',
                    'ratingCount' => '1234',
                    'reviewCount' => '1234'
                ],
                'knowsAbout' => [
                    'Mutuelle santé solidaire pour la diaspora africaine',
                    'Tiers-payant hospitalisation et pharmacie en Afrique',
                    'Téléconsultation médicale d\'urgence 24/7 sur WhatsApp',
                    'Soins gériatriques et infirmières à domicile pour seniors au pays',
                    'Mutuelle santé entreprise déductible fiscalement (OHADA/CGI)'
                ]
            ],

            // 2. WebSite with Search Action
            [
                '@type' => 'WebSite',
                '@id' => "{$baseUrl}/#website",
                'url' => $baseUrl,
                'name' => $appName,
                'publisher' => ['@id' => "{$baseUrl}/#organization"],
                'inLanguage' => 'fr-FR',
                'potentialAction' => [
                    '@type' => 'SearchAction',
                    'target' => "{$baseUrl}/reseau-soins?q={search_term_string}",
                    'query-input' => 'required name=search_term_string'
                ]
            ],

            // 3. Health Insurance Plans (Schema.org HealthInsurancePlan)
            [
                '@type' => 'HealthInsurancePlan',
                '@id' => "{$baseUrl}/#plan-silver",
                'name' => 'MulemaCare Silver (Famille & Soins Courants)',
                'description' => 'Couverture complète des hospitalisations à 100% en tiers-payant, consultations spécialistes 80%, pharmacie 80% et télétriage Lisacare 24/7 inclus.',
                'usesMedicalStore' => true,
                'benefitsSummaryUrl' => "{$baseUrl}/#garanties",
                'healthPlanCopay' => '0%',
                'healthPlanDrugTier' => 'Garantie Médicaments Essentiels 80%',
                'offers' => [
                    '@type' => 'Offer',
                    'price' => '42',
                    'priceCurrency' => 'EUR',
                    'unitText' => 'MONTH',
                    'availability' => 'https://schema.org/InStock',
                    'url' => "{$baseUrl}/#simulateur"
                ]
            ],

            // 4. FAQPage (Alimentation Directe pour Google AI Overviews & Featured Snippets)
            [
                '@type' => 'FAQPage',
                '@id' => "{$baseUrl}/#faq",
                'mainEntity' => [
                    [
                        '@type' => 'Question',
                        'name' => 'Comment fonctionne le tiers-payant MulemaCare en clinique au Cameroun et en Afrique ?',
                        'acceptedAnswer' => [
                            '@type' => 'Answer',
                            'text' => 'Le tiers-payant MulemaCare permet aux assurés de se soigner dans plus de 45 cliniques et pharmacies conventionnées sans faire aucune avance de frais. Le patient présente simplement le QR Code de sa Carte Mutuelle Digitale CSSA sur son smartphone. La clinique valide la prise en charge en 0.2 seconde et MulemaCare règle directement l\'établissement sous 72 heures.'
                        ]
                    ],
                    [
                        '@type' => 'Question',
                        'name' => 'Puis-je souscrire à MulemaCare depuis l\'Europe pour ma famille vivant en Afrique ?',
                        'acceptedAnswer' => [
                            '@type' => 'Answer',
                            'text' => 'Oui, absolument. Plus de 60 % de nos adhérents résident en France, Belgique, Canada, Suisse ou aux États-Unis et cotisent par Carte Bancaire, Stripe ou prélèvement automatique pour couvrir leurs parents et proches restés au pays.'
                        ]
                    ],
                    [
                        '@type' => 'Question',
                        'name' => 'Quels sont les délais de carence appliqués chez MulemaCare ?',
                        'acceptedAnswer' => [
                            '@type' => 'Answer',
                            'text' => 'Les accidents, urgences vitales (SAMU, réanimation) et le service de régulation Lisacare 24/7 sont pris en charge à 0 jour (immédiatement dès l\'adhésion). Le délai de carence est de 3 mois pour les soins programmés, consultations et hospitalisations, et de 6 mois pour la maternité et les femmes enceintes (bilans prénataux et accouchement).'
                        ]
                    ],
                    [
                        '@type' => 'Question',
                        'name' => 'Comment contacter le médecin de garde Lisacare 24/7 ?',
                        'acceptedAnswer' => [
                            '@type' => 'Answer',
                            'text' => 'Les adhérents MulemaCare bénéficient d\'un accès illimité au service Lisacare directement sur WhatsApp (+33 6 59 51 34 58 ou +237 521 120 21). Un médecin régulateur qualifié répond en moyenne en 4 minutes, de jour comme de nuit, pour orienter le patient ou prescrire une ordonnance numérique.'
                        ]
                    ],
                    [
                        '@type' => 'Question',
                        'name' => 'L\'offre mutuelle entreprise MulemaCare Pro est-elle déductible des impôts ?',
                        'acceptedAnswer' => [
                            '@type' => 'Answer',
                            'text' => 'Oui, toutes les cotisations patronales versées au titre de MulemaCare Pro sont 100 % déductibles du bénéfice imposable de l\'entreprise conformément au Code Général des Impôts et aux normes comptables OHADA.'
                        ]
                    ]
                ]
            ]
        ];

        return '<script type="application/ld+json">' . json_encode(['@context' => 'https://schema.org', '@graph' => $graph], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . '</script>';
    }
}
