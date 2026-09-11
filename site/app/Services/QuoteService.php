<?php
declare(strict_types=1);

namespace App\Services;

use PDO;
use Exception;

/**
 * Moteur de Tarification, Devis & Simulation en Temps Réel pour MulemaCare
 */
class QuoteService {
    private array $config;
    private string $storagePath;
    private TariffCatalog $tariffs;

    public function __construct(array $config) {
        $this->config = $config;
        $configured = $config['data_dir'] ?? null;
        $dataDir = rtrim((string) ($configured ?: (__DIR__ . '/../../data')), '/');
        $this->storagePath = $dataDir . '/quotes.json';
        $this->tariffs = new TariffCatalog($config);
    }

    public function tariffVersion(): string
    {
        return $this->tariffs->version();
    }

    /**
     * Calcule le tarif d'une formule mutuelle santé pour particuliers & diaspora
     */
    public function calculateIndividualQuote(string $planId, string $composition = 'solo', string $currency = 'EUR', string $cycle = 'annual'): array {
        $plan = $this->tariffs->plan($planId);
        if ($plan === []) {
            $plan = $this->config['plans']['silver'] ?? [];
        }
        $comp = in_array($composition, ['solo', 'couple', 'family', 'seniors']) ? $composition : 'solo';
        $curr = in_array($currency, ['XAF', 'EUR', 'USD']) ? $currency : 'EUR';

        $priceObj = $plan['prices'][$comp][$curr] ?? $plan['prices']['solo'][$curr] ?? $plan['prices']['solo']['EUR'] ?? ['amount' => 0, 'label' => '', 'sub' => ''];

        $monthlyAmount = (float)$priceObj['amount'];
        $discount = $this->tariffs->annualDiscountPct() / 100.0;
        $annualAmount = round($monthlyAmount * 12 * (1.0 - $discount), 2);
        $monthlyEquivalent = round($annualAmount / 12, 2);

        $selectedAmount = ($cycle === 'monthly') ? $monthlyAmount : $annualAmount;
        $savingsAnnual = round(($monthlyAmount * 12) - $annualAmount, 2);

        // Le plafond est stocké soit en entier, soit en libellé ("1 500 000 FCFA / an ...")
        $ceilingRaw = (string) ($plan['ceiling_xaf'] ?? '0');
        preg_match('/\d[\d\s\x{00A0}\x{202F}]*/u', $ceilingRaw, $ceilingMatch);
        $ceilingXaf = (int) preg_replace('/\D/u', '', $ceilingMatch[0] ?? '0');
        $ceilingEur = $ceilingXaf > 0 ? (int) round($ceilingXaf / 655.957) : 0;
        $ceilingLabel = is_numeric($ceilingRaw)
            ? number_format($ceilingXaf, 0, ',', ' ') . ' FCFA (' . number_format($ceilingEur, 0, ',', ' ') . ' €) / an'
            : $ceilingRaw;

        return [
            'plan_id'            => $plan['id'] ?? $planId,
            'plan_name'          => $plan['name'] ?? $planId,
            'headline'           => $plan['headline'] ?? '',
            'badge'              => $plan['badge'] ?? '',
            'composition'        => $comp,
            'currency'           => $curr,
            'cycle'              => $cycle,
            'tariff_version'     => $this->tariffs->version(),
            'annual_discount_pct'=> $this->tariffs->annualDiscountPct(),
            'monthly_amount'     => $monthlyAmount,
            'annual_amount'      => $annualAmount,
            'monthly_equivalent' => $monthlyEquivalent,
            'selected_amount'    => $selectedAmount,
            'savings_annual'     => $savingsAnnual,
            'label'              => $priceObj['label'] ?? '',
            'sub'                => $priceObj['sub'] ?? '',
            'ceiling_xaf'        => $ceilingXaf,
            'ceiling_eur'        => $ceilingEur,
            'ceiling_label'      => $ceilingLabel,
            'features'           => $plan['features'] ?? [],
            'tiers_payant'       => $plan['tiers_payant'] ?? '',
            'waiting_periods'    => [
                'urgences'         => '0 jour (Immédiat dès l\'adhésion)',
                'teleconsultation' => '0 jour (Lisacare 24/7 sur WhatsApp)',
                'soins_courants'   => '90 jours (3 mois pour consultations & pharmacie)',
                'hospitalisation'  => '90 jours (3 mois pour chirurgie programmée)',
                'dentaire_optique' => '90 jours (3 mois pour verres et prothèses)',
                'maternite'        => '180 jours (6 mois pour femmes enceintes & accouchement)',
            ],
        ];
    }

    /**
     * Calcule le devis santé collective pour une PME / Entreprise
     */
    public function calculateCorporateQuote(int $employeeCount, string $planTier = 'silver', string $currency = 'XAF'): array {
        $count = max(5, $employeeCount);
        $baseRate = 30000; // Tarif de base mensuel en FCFA par salarié
        $discountPct = 0;
        $tierName = 'PME Standard';

        if ($count >= 101) {
            $discountPct = 25;
            $tierName = 'Grand Compte (+100 salariés)';
        } elseif ($count >= 21) {
            $discountPct = 20;
            $tierName = 'Moyenne Entreprise (21-100 salariés)';
        } elseif ($count >= 10) {
            $discountPct = 10;
            $tierName = 'Petite Entreprise (10-20 salariés)';
        }

        $unitRateMonthly = (int) round($baseRate * (1 - ($discountPct / 100)));
        $unitRateAnnual = (int) round($unitRateMonthly * 12 * 0.90);
        $monthlyTotal = $unitRateMonthly * $count;
        $annualTotal = (int) round($monthlyTotal * 12 * 0.90);

        return [
            'employee_count'     => $count,
            'tier_name'          => $tierName,
            'plan_tier'          => $planTier,
            'currency'           => 'XAF',
            'tariff_version'     => $this->tariffs->version(),
            'discount_percent'   => $discountPct,
            'unit_rate_monthly'  => $unitRateMonthly,
            'unit_rate_annual'   => $unitRateAnnual,
            'unit_rate_label'    => number_format($unitRateMonthly, 0, ',', ' ') . ' FCFA / salarié / mois',
            'monthly_total'      => $monthlyTotal,
            'monthly_label'      => number_format($monthlyTotal, 0, ',', ' ') . ' FCFA / mois',
            'annual_total'       => $annualTotal,
            'annual_label'       => number_format($annualTotal, 0, ',', ' ') . ' FCFA / an',
            'tax_deductible'     => '100 % déductible fiscalement au titre des charges sociales',
            'tiers_payant'       => '100 % Tiers-Payant dans les cliniques conventionnées',
        ];
    }

    /** Normalise profil simulateur → composition devis. */
    public function normalizeComposition(string $raw): string
    {
        $c = strtolower(trim($raw));
        $map = [
            'solo' => 'solo',
            'couple' => 'couple',
            'family' => 'family',
            'famille' => 'family',
            'seniors' => 'seniors',
            'senior' => 'seniors',
        ];
        return $map[$c] ?? 'family';
    }

    /**
     * Crée, enregistre et retourne un devis officiel
     */
    public function createQuote(array $data): array {
        $type = $data['type'] ?? 'individual';
        $quoteNumber = 'DEV-' . date('Y') . '-' . strtoupper(bin2hex(random_bytes(3)));
        $prospectName = trim($data['name'] ?? $data['prospect_name'] ?? 'Prospect MulemaCare');
        $prospectEmail = trim($data['email'] ?? $data['prospect_email'] ?? '');
        $prospectPhone = trim($data['phone'] ?? $data['prospect_phone'] ?? '');
        $city = trim($data['city'] ?? 'douala');
        $currency = (string) ($data['currency'] ?? ($type === 'corporate' ? 'XAF' : 'EUR'));
        if (!in_array($currency, ['EUR', 'USD', 'XAF'], true)) {
            $currency = $type === 'corporate' ? 'XAF' : 'EUR';
        }
        $cycle = ($data['cycle'] ?? 'annual') === 'monthly' ? 'monthly' : 'annual';

        if ($type === 'corporate') {
            $employeeCount = (int)($data['employee_count'] ?? 10);
            $planTier = $data['plan_tier'] ?? $data['plan_id'] ?? 'silver';
            $calculation = $this->calculateCorporateQuote($employeeCount, $planTier, $currency);
            $calculation['tariff_version'] = $this->tariffs->version();
            $planName = 'Mutuelle Entreprise · ' . strtoupper((string) $planTier) . ' (' . $calculation['tier_name'] . ')';
            $annualAmount = (float)$calculation['annual_total'];
            $monthlyAmount = (float)$calculation['monthly_total'];
            $companyName = trim($data['company_name'] ?? $data['company'] ?? $prospectName);
        } else {
            $planId = $data['plan_id'] ?? $data['plan'] ?? 'silver';
            $composition = $this->normalizeComposition((string) ($data['composition'] ?? 'family'));
            $calculation = $this->calculateIndividualQuote($planId, $composition, $currency, $cycle);
            $planName = $calculation['plan_name'];
            $annualAmount = (float)$calculation['annual_amount'];
            $monthlyAmount = (float)$calculation['monthly_amount'];
            $companyName = '';
        }

        $validUntil = date('Y-m-d', strtotime('+30 days'));
        $desk = preg_replace('/\D/', '', (string) ($this->config['contact']['whatsapp_desk'] ?? '23752112021'));

        $quote = [
            'quote_number'       => $quoteNumber,
            'type'               => $type,
            'prospect_name'      => $prospectName,
            'prospect_email'     => $prospectEmail,
            'prospect_phone'     => $prospectPhone,
            'company_name'       => $companyName,
            'city'               => $city,
            'currency'           => $type === 'corporate' ? 'XAF' : $currency,
            'cycle'              => $cycle,
            'plan_id'            => $data['plan_id'] ?? $data['plan'] ?? ($data['plan_tier'] ?? 'silver'),
            'composition'        => $type === 'corporate' ? 'corporate' : $this->normalizeComposition((string) ($data['composition'] ?? 'family')),
            'employee_count'     => $type === 'corporate' ? (int) ($data['employee_count'] ?? 10) : null,
            'plan_name'          => $planName,
            'annual_amount'      => $annualAmount,
            'monthly_amount'     => $monthlyAmount,
            'tariff_version'     => $calculation['tariff_version'] ?? $this->tariffs->version(),
            'calculation'        => $calculation,
            'status'             => 'sent',
            'valid_until'        => $validUntil,
            'valid_until_label'  => date('d/m/Y', strtotime($validUntil)),
            'created_at'         => date('Y-m-d H:i:s'),
            'created_at_label'   => date('d/m/Y à H:i'),
            'view_url'           => '/devis/' . $quoteNumber,
            'subscribe_url'      => $type === 'corporate'
                ? '/entreprises?quote=' . rawurlencode($quoteNumber)
                : '/adhesion?express=1&quote=' . rawurlencode($quoteNumber),
        ];

        $waMsg = $type === 'corporate'
            ? "BONJOUR MULEMACARE PRO — DEVIS ENTREPRISE\n\nN° devis : {$quoteNumber}\nEntreprise : {$companyName}\nContact : {$prospectName}\nTél : {$prospectPhone}\nEffectif : " . ($quote['employee_count'] ?? '') . "\nBudget annuel : " . number_format($annualAmount, 0, ',', ' ') . " XAF\n\nJe souhaite finaliser la convention RH."
            : "BONJOUR MULEMACARE — DEVIS\n\nN° : {$quoteNumber}\nTitulaire : {$prospectName}\nFormule : {$planName}\nMontant : " . number_format($annualAmount, 0, ',', ' ') . " {$quote['currency']} / an\n\nJe souhaite adhérer immédiatement.";
        $quote['whatsapp_url'] = 'https://wa.me/' . $desk . '?text=' . rawurlencode($waMsg);

        // 1. Sauvegarde en MySQL si disponible
        $pdo = Database::getConnection();
        if ($pdo) {
            try {
                $stmt = $pdo->prepare("INSERT INTO mulema_quotes 
                    (quote_number, prospect_name, prospect_email, prospect_phone, plan, composition, currency, annual_amount, monthly_equivalent, status) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'sent')");
                $stmt->execute([
                    $quoteNumber,
                    $prospectName,
                    $prospectEmail,
                    $prospectPhone,
                    $data['plan_id'] ?? 'silver',
                    $data['composition'] ?? 'family',
                    $currency,
                    $annualAmount,
                    $calculation['monthly_equivalent'] ?? $monthlyAmount
                ]);
            } catch (Exception $e) {
                // Table might not exist yet; silently fall back to JSON
            }
        }

        // 2. Sauvegarde dans quotes.json
        $this->saveToJson($quote);

        return $quote;
    }

    /**
     * Récupère un devis par son numéro
     */
    public function getQuote(string $quoteNumber): ?array {
        $quotes = $this->loadFromJson();
        return $quotes[$quoteNumber] ?? null;
    }

    /**
     * Liste les derniers devis émis
     */
    public function listQuotes(int $limit = 50): array {
        $quotes = array_values($this->loadFromJson());
        usort($quotes, fn($a, $b) => strcmp($b['created_at'] ?? '', $a['created_at'] ?? ''));
        return array_slice($quotes, 0, $limit);
    }

    private function loadFromJson(): array {
        if (!file_exists($this->storagePath)) {
            return [];
        }
        $raw = file_get_contents($this->storagePath);
        return json_decode($raw, true) ?: [];
    }

    private function saveToJson(array $quote): void {
        $quotes = $this->loadFromJson();
        $quotes[$quote['quote_number']] = $quote;
        if (!is_dir(dirname($this->storagePath))) {
            mkdir(dirname($this->storagePath), 0755, true);
        }
        file_put_contents($this->storagePath, json_encode($quotes, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    }
}
