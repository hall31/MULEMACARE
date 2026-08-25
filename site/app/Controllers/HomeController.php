<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Core\SEO;
use App\Services\MembershipService;

/**
 * Contrôleur Principal & Moteur de Rendu pour MulemaCare Health Group
 */
class HomeController {
    private array $config;

    private const COUNTRIES = [
        'cameroun' => [
            'name' => 'Cameroun',
            'flag' => '🇨🇲',
            'cities' => 'Douala, Yaoundé, Bafoussam, Garoua',
            'clinics_count' => 18,
            'currency' => 'FCFA (XAF)',
            'price_from' => '15 000 FCFA',
            'price_eur' => '23 €',
            'momo' => 'Orange Money (#150*1*1*52112021*) & MTN MoMo (*126*1*65145837*)',
            'headline' => 'La Mutuelle Santé n°1 au Cameroun sans Avance de Frais',
            'sub' => 'Tiers-payant direct à la Polyclinique Mermoz, Clinique de l\'Étoile, Centre Médico-Chirurgical d\'Akwa et Pharmacie des Nations.',
        ],
        'rdc' => [
            'name' => 'RDC (Congo Kinshasa)',
            'flag' => '🇨🇩',
            'cities' => 'Kinshasa, Lubumbashi, Goma',
            'clinics_count' => 12,
            'currency' => 'USD / CDF',
            'price_from' => '25 $ / 70 000 CDF',
            'price_eur' => '23 €',
            'momo' => 'Airtel Money, Vodacom M-Pesa & Orange Money RDC',
            'headline' => 'Mutuelle Santé & Tiers-Payant en République Démocratique du Congo',
            'sub' => 'Couverture immédiate au Centre Médical de la Gombe, Clinique Ngaliema et Pharmacie Centrale.',
        ],
        'cote-divoire' => [
            'name' => 'Côte d\'Ivoire',
            'flag' => '🇨🇮',
            'cities' => 'Abidjan, Bouaké, San Pedro',
            'clinics_count' => 14,
            'currency' => 'FCFA (XOF)',
            'price_from' => '15 000 FCFA',
            'price_eur' => '23 €',
            'momo' => 'Wave Côte d\'Ivoire, Orange Money & MTN MoMo CI',
            'headline' => 'Mutuelle Santé Solidaire en Côte d\'Ivoire sans Avance de Frais',
            'sub' => 'Prise en charge à la Polyclinique PISAM, Clinique Deux-Plateaux et Grande Pharmacie de Marcory.',
        ],
        'senegal' => [
            'name' => 'Sénégal',
            'flag' => '🇸🇳',
            'cities' => 'Dakar, Thiès, Saint-Louis',
            'clinics_count' => 10,
            'currency' => 'FCFA (XOF)',
            'price_from' => '15 000 FCFA',
            'price_eur' => '23 €',
            'momo' => 'Wave Sénégal & Orange Money Sénégal',
            'headline' => 'Mutuelle Santé et Tiers-Payant au Sénégal (Dakar & Régions)',
            'sub' => 'Soins garantis sans avance à la Clinique de la Madeleine, Centre Médical Almadies et Pharmacie Mermoz.',
        ],
        'gabon' => [
            'name' => 'Gabon',
            'flag' => '🇬🇦',
            'cities' => 'Libreville, Port-Gentil',
            'clinics_count' => 8,
            'currency' => 'FCFA (XAF)',
            'price_from' => '15 000 FCFA',
            'price_eur' => '23 €',
            'momo' => 'Airtel Money Gabon & Moov Money',
            'headline' => 'Mutuelle Santé Solidaire au Gabon pour la Famille et la Diaspora',
            'sub' => 'Couverture santé complète avec tiers-payant immédiat dans les centres conventionnés de Libreville.',
        ],
        'congo' => [
            'name' => 'Congo Brazzaville',
            'flag' => '🇨🇬',
            'cities' => 'Brazzaville, Pointe-Noire',
            'clinics_count' => 7,
            'currency' => 'FCFA (XAF)',
            'price_from' => '15 000 FCFA',
            'price_eur' => '23 €',
            'momo' => 'MTN Mobile Money & Airtel Money Congo',
            'headline' => 'Mutuelle Santé au Congo (Brazzaville & Pointe-Noire)',
            'sub' => 'Tiers-payant garanti dans notre réseau hospitalier partenaire.',
        ],
        'benin' => [
            'name' => 'Bénin',
            'flag' => '🇧🇯',
            'cities' => 'Cotonou, Porto-Novo',
            'clinics_count' => 6,
            'currency' => 'FCFA (XOF)',
            'price_from' => '15 000 FCFA',
            'price_eur' => '23 €',
            'momo' => 'MTN Mobile Money Bénin & Moov Money',
            'headline' => 'Mutuelle Santé au Bénin sans Avance de Frais',
            'sub' => 'Prise en charge directe en clinique conventionnée à Cotonou.',
        ],
        'madagascar' => [
            'name' => 'Madagascar',
            'flag' => '🇲🇬',
            'cities' => 'Antananarivo, Tamatave',
            'clinics_count' => 5,
            'currency' => 'Ariary (MGA)',
            'price_from' => '115 000 MGA',
            'price_eur' => '23 €',
            'momo' => 'Orange Money Madagascar, MVola & Airtel Money',
            'headline' => 'Mutuelle Santé à Madagascar pour la Famille & Diaspora',
            'sub' => 'Remboursements directs et tiers-payant hospitalier.',
        ],
    ];

    private const DIASPORA_HUBS = [
        'france' => [
            'name' => 'France',
            'flag' => '🇫🇷',
            'cities' => 'Paris, Lyon, Marseille, Bordeaux, Lille',
            'clinics_count' => 45,
            'currency' => 'EUR (€)',
            'price_from' => '23 € / mois',
            'price_eur' => '23 €',
            'momo' => 'Carte Bancaire (CB / Visa / Mastercard / Stripe) & Virement SEPA',
            'headline' => 'Souscrire depuis la France pour Protéger sa Famille au Pays',
            'sub' => 'Payez par CB/SEPA depuis la France, vos proches se soignent en Afrique sans avance de frais dans 45+ cliniques.',
        ],
        'belgique' => [
            'name' => 'Belgique',
            'flag' => '🇧🇪',
            'cities' => 'Bruxelles, Liège, Anvers, Charleroi',
            'clinics_count' => 45,
            'currency' => 'EUR (€)',
            'price_from' => '23 € / mois',
            'price_eur' => '23 €',
            'momo' => 'Bancontact, Visa / Mastercard / Stripe & SEPA',
            'headline' => 'Mutuelle Santé Diaspora Belgique pour l\'Afrique',
            'sub' => 'Adhésion en ligne sécurisée depuis la Belgique pour toute la famille restée au pays.',
        ],
        'canada' => [
            'name' => 'Canada',
            'flag' => '🇨🇦',
            'cities' => 'Montréal, Québec, Ottawa, Toronto',
            'clinics_count' => 45,
            'currency' => 'CAD ($)',
            'price_from' => '34 $ CAD / mois',
            'price_eur' => '23 €',
            'momo' => 'Carte de Crédit / Débit Visa & Mastercard via Stripe',
            'headline' => 'Mutuelle Santé Diaspora Canada pour Protéger ses Proches en Afrique',
            'sub' => 'Tranquillité d\'esprit totale depuis le Canada : zéro facture médicale imprévue au pays.',
        ],
        'suisse' => [
            'name' => 'Suisse',
            'flag' => '🇨🇭',
            'cities' => 'Genève, Lausanne, Zurich',
            'clinics_count' => 45,
            'currency' => 'CHF',
            'price_from' => '22 CHF / mois',
            'price_eur' => '23 €',
            'momo' => 'Cartes Bancaires Suisses & Virement IBAN',
            'headline' => 'Mutuelle Santé Diaspora Suisse pour l\'Afrique',
            'sub' => 'Couverture santé solidaire haute qualité financée depuis la Suisse.',
        ],
        'allemagne' => [
            'name' => 'Allemagne',
            'flag' => '🇩🇪',
            'cities' => 'Berlin, Francfort, Munich, Cologne',
            'clinics_count' => 45,
            'currency' => 'EUR (€)',
            'price_from' => '23 € / mois',
            'price_eur' => '23 €',
            'momo' => 'Giropay, SOFORT, SEPA & Cartes Bancaires',
            'headline' => 'Mutuelle Santé Diaspora Allemagne pour vos Proches au Pays',
            'sub' => 'Tiers-payant direct en clinique pour votre famille en Afrique.',
        ],
        'haiti' => [
            'name' => 'Haïti & Caraïbes',
            'flag' => '🇭🇹',
            'cities' => 'Port-au-Prince, Cap-Haïtien',
            'clinics_count' => 10,
            'currency' => 'USD ($)',
            'price_from' => '25 $ / mois',
            'price_eur' => '23 €',
            'momo' => 'MonCash & Cartes Internationales',
            'headline' => 'Mutuelle Santé Solidaire Haïti & Caraïbes',
            'sub' => 'Programme de solidarité santé et tiers-payant.',
        ],
    ];

    public function __construct() {
        $this->config = require __DIR__ . '/../../config.php';
    }

    private function render(string $viewPath, array $data, SEO $seo): void {
        $plans = $this->config['plans'] ?? [];
        $corporate = $this->config['corporate'] ?? [];
        $clinics = $this->config['clinics'] ?? [];
        $ecosystem = $this->config['ecosystem'] ?? [];
        $contact = $this->config['contact'] ?? [];
        $mobileMoney = $this->config['mobile_money'] ?? [];

        extract($data);

        require __DIR__ . '/../../views/layout/header.php';
        require __DIR__ . '/../../views/pages/' . $viewPath . '.php';
        require __DIR__ . '/../../views/layout/footer.php';
    }

    /**
     * Portail Central Hub (https://mulemacare.com)
     * GET /
     */
    public function index(): void {
        $seo = new SEO($this->config, '/', null, 'home');
        $this->render('home', [], $seo);
    }

    /**
     * Page Détail Mutuelle Particuliers & Diaspora
     * GET /mutuelle-sante
     */
    public function mutuelle(): void {
        $seo = new SEO($this->config, '/mutuelle-sante', null, 'mutuelle');
        $this->render('mutuelle-particuliers', [], $seo);
    }

    /**
     * Page Offre Santé Collective Entreprises & PME
     * GET /entreprises
     */
    public function entreprises(): void {
        $seo = new SEO($this->config, '/entreprises', null, 'entreprises');
        $this->render('mutuelle-entreprises', [], $seo);
    }

    /**
     * Annuaire & Carte du Réseau de Soins Agréé
     * GET /reseau-soins
     */
    public function reseau(): void {
        $seo = new SEO($this->config, '/reseau-soins', null, 'reseau');
        $this->render('reseau-soins', [], $seo);
    }

    /**
     * Page Conventionnement & Partenaires Professionnels de Santé
     * GET /partenaires et GET /devenir-partenaire
     */
    public function partenaires(): void {
        $seo = new SEO($this->config, '/partenaires', null, 'partenaires');
        $this->render('partenaires', [], $seo);
    }

    /**
     * Page Dédiée par Pays Africain
     * GET /pays/{slug}
     */
    public function pays(string $slug): void {
        $countryKey = strtolower(trim($slug));
        $countryInfo = self::COUNTRIES[$countryKey] ?? self::COUNTRIES['cameroun'];
        $seo = new SEO($this->config, "/pays/{$countryKey}", $countryInfo, 'pays');
        $this->render('pays', ['countrySlug' => $countryKey, 'countryInfo' => $countryInfo], $seo);
    }

    /**
     * Page Dédiée par Pôle Diaspora Internationale
     * GET /diaspora/{slug}
     */
    public function diaspora(string $slug): void {
        $hubKey = strtolower(trim($slug));
        $hubInfo = self::DIASPORA_HUBS[$hubKey] ?? self::DIASPORA_HUBS['france'];
        $seo = new SEO($this->config, "/diaspora/{$hubKey}", $hubInfo, 'pays');
        $this->render('pays', ['countrySlug' => $hubKey, 'countryInfo' => $hubInfo], $seo);
    }

    /**
     * Fiche Officielle de Devis en Ligne
     * GET /devis/{id}
     */
    public function devis(string $id = ''): void {
        $seo = new SEO($this->config, "/devis/{$id}", null, 'home');
        $this->render('devis', ['quoteId' => $id], $seo);
    }

    /**
     * Tunnel de Souscription & Adhésion 100% Automatisé
     * GET /adhesion
     */
    public function adhesion(): void {
        $seo = new SEO($this->config, '/adhesion', null, 'home');
        $this->render('adhesion', [], $seo);
    }

    /**
     * Borne Tiers-Payant Établissements & Pharmacies
     * GET /borne-clinique ou /verifier
     */
    public function borneClinique(): void {
        $seo = new SEO($this->config, '/borne-clinique', null, 'home');
        $this->render('borne-clinique', [], $seo);
    }

    /**
     * Espace Adhérent Family Hub
     * GET /espace-adherent
     */
    public function adherent(): void {
        $seo = new SEO($this->config, '/espace-adherent', null, 'home');
        $this->render('espace-adherent', [], $seo);
    }

    /**
     * Espace Admin & Régulation Mutuelle
     * GET /admin
     */
    public function admin(): void {
        $seo = new SEO($this->config, '/admin', null, 'home');
        $this->render('espace-admin', [], $seo);
    }

    /**
     * Page Publique de Vérification de Carte Mutuelle CSSA
     * GET /carte/{memberId}
     */
    public function carte(string $memberId): void {
        $memService = new MembershipService($this->config);
        $cardData = $memService->verifyCard($memberId);
        $seo = new SEO($this->config, "/carte/{$memberId}", $cardData, 'carte');
        $this->render('verif-carte', ['cardData' => $cardData, 'memberId' => $memberId], $seo);
    }

    /**
     * Flux Sitemap XML Dynamique Étendu
     * GET /sitemap.xml
     */
    public function sitemap(): void {
        if (!headers_sent()) {
            header('Content-Type: application/xml; charset=utf-8');
        }
        $baseUrl = rtrim($this->config['app']['url'], '/');
        $date = date('Y-m-d');

        echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
        echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">' . "\n";

        $routes = [
            '/'                 => '1.0',
            '/mutuelle-sante'   => '0.9',
            '/entreprises'      => '0.9',
            '/reseau-soins'     => '0.9',
            '/partenaires'      => '0.85',
            '/espace-adherent'  => '0.7',
        ];

        // Ajouter tous les pays africains
        foreach (array_keys(self::COUNTRIES) as $c) {
            $routes["/pays/{$c}"] = '0.85';
        }

        // Ajouter tous les pôles diaspora
        foreach (array_keys(self::DIASPORA_HUBS) as $d) {
            $routes["/diaspora/{$d}"] = '0.85';
        }

        foreach ($routes as $path => $priority) {
            echo "  <url>\n    <loc>{$baseUrl}{$path}</loc>\n    <lastmod>{$date}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>{$priority}</priority>\n  </url>\n";
        }

        echo '</urlset>';
    }

    /**
     * Directives Robots.txt
     * GET /robots.txt
     */
    public function robots(): void {
        if (!headers_sent()) {
            header('Content-Type: text/plain; charset=utf-8');
        }
        $baseUrl = rtrim($this->config['app']['url'], '/');
        echo "User-agent: *\n";
        echo "Allow: /\n";
        echo "Disallow: /api/\n";
        echo "Disallow: /data/\n\n";
        echo "Sitemap: {$baseUrl}/sitemap.xml\n";
    }

    /**
     * Directives llms.txt (AI Search & Assistant Context)
     * GET /llms.txt
     */
    public function llmsTxt(): void {
        if (!headers_sent()) {
            header('Content-Type: text/plain; charset=utf-8');
        }
        $llmsFile = __DIR__ . '/../../llms.txt';
        if (file_exists($llmsFile)) {
            readfile($llmsFile);
        } else {
            echo "# MulemaCare Health Group\nhttps://mulemacare.com\n";
        }
    }
}
