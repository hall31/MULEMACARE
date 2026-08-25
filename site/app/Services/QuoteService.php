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

    public function __construct(array $config) {
        $this->config = $config;
        $this->storagePath = __DIR__ . '/../../data/quotes.json';
    }

    /**
     * Calcule le tarif d'une formule mutuelle santé pour particuliers & diaspora
     */
    public function calculateIndividualQuote(string $planId, string $composition = 'solo', string $currency = 'EUR', string $cycle = 'annual'): array {
        $plan = $this->config['plans'][$planId] ?? $this->config['plans']['silver'];
        $comp = in_array($composition, ['solo', 'couple', 'family', 'seniors']) ? $composition : 'solo';
        $curr = in_array($currency, ['XAF', 'EUR', 'USD']) ? $currency : 'EUR';

        $priceObj = $plan['prices'][$comp][$curr] ?? $plan['prices']['solo'][$curr] ?? $plan['prices']['solo']['EUR'];

        $monthlyAmount = (float)$priceObj['amount'];
        $annualAmount = round($monthlyAmount * 12 * 0.90, 2); // 10% de remise annuelle
        $monthlyEquivalent = round($annualAmount / 12, 2);

        $selectedAmount = ($cycle === 'monthly') ? $monthlyAmount : $annualAmount;
        $savingsAnnual = round(($monthlyAmount * 12) - $annualAmount, 2);

        $ceilingXaf = $plan['ceiling_xaf'];
        $ceilingEur = (int) round($ceilingXaf / 655.957);

        return [
            'plan_id'            => $plan['id'],
            'plan_name'          => $plan['name'],
            'headline'           => $plan['headline'],
            'badge'              => $plan['badge'],
            'composition'        => $comp,
            'currency'           => $curr,
            'cycle'              => $cycle,
            'monthly_amount'     => $monthlyAmount,
            'annual_amount'      => $annualAmount,
            'monthly_equivalent' => $monthlyEquivalent,
            'selected_amount'    => $selectedAmount,
            'savings_annual'     => $savingsAnnual,
            'label'              => $priceObj['label'],
            'sub'                => $priceObj['sub'],
            'ceiling_xaf'        => $ceilingXaf,
            'ceiling_eur'        => $ceilingEur,
            'ceiling_label'      => number_format($ceilingXaf, 0, ',', ' ') . ' FCFA (' . number_format($ceilingEur, 0, ',', ' ') . ' €) / an',
            'features'           => $plan['features'],
            'tiers_payant'       => $plan['tiers_payant'],
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
        $currency = in_array(($data['currency'] ?? 'EUR'), ['EUR', 'USD', 'XAF']) ? $data['currency'] : 'EUR';
        $cycle = ($data['cycle'] ?? 'annual') === 'monthly' ? 'monthly' : 'annual';

        if ($type === 'corporate') {
            $employeeCount = (int)($data['employee_count'] ?? 10);
            $planTier = $data['plan_tier'] ?? 'silver';
            $calculation = $this->calculateCorporateQuote($employeeCount, $planTier, $currency);
            $planName = 'Mutuelle Entreprise (' . $calculation['tier_name'] . ')';
            $annualAmount = (float)$calculation['annual_total'];
            $monthlyAmount = (float)$calculation['monthly_total'];
        } else {
            $planId = $data['plan_id'] ?? $data['plan'] ?? 'silver';
            $composition = $data['composition'] ?? 'family';
            $calculation = $this->calculateIndividualQuote($planId, $composition, $currency, $cycle);
            $planName = $calculation['plan_name'];
            $annualAmount = (float)$calculation['annual_amount'];
            $monthlyAmount = (float)$calculation['monthly_amount'];
        }

        $validUntil = date('Y-m-d', strtotime('+30 days'));

        $quote = [
            'quote_number'       => $quoteNumber,
            'type'               => $type,
            'prospect_name'      => $prospectName,
            'prospect_email'     => $prospectEmail,
            'prospect_phone'     => $prospectPhone,
            'city'               => $city,
            'currency'           => $currency,
            'cycle'              => $cycle,
            'plan_name'          => $planName,
            'annual_amount'      => $annualAmount,
            'monthly_amount'     => $monthlyAmount,
            'calculation'        => $calculation,
            'status'             => 'sent',
            'valid_until'        => $validUntil,
            'valid_until_label'  => date('d/m/Y', strtotime($validUntil)),
            'created_at'         => date('Y-m-d H:i:s'),
            'created_at_label'   => date('d/m/Y à H:i'),
            'view_url'           => '/devis/' . $quoteNumber,
            'subscribe_url'      => '/adhesion?quote=' . $quoteNumber,
        ];

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
