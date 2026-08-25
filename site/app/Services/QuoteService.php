<?php
declare(strict_types=1);

namespace App\Services;

/**
 * Moteur de Tarification & Devis en Temps Réel pour MulemaCare
 */
class QuoteService {
    private array $config;

    public function __construct(array $config) {
        $this->config = $config;
    }

    /**
     * Calcule le tarif d'une formule mutuelle santé pour particuliers & diaspora
     */
    public function calculateIndividualQuote(string $planId, string $composition = 'solo', string $currency = 'XAF'): array {
        $plan = $this->config['plans'][$planId] ?? $this->config['plans']['silver'];
        $comp = in_array($composition, ['solo', 'couple', 'family']) ? $composition : 'solo';
        $curr = in_array($currency, ['XAF', 'EUR', 'USD']) ? $currency : 'XAF';

        $priceObj = $plan['prices'][$comp][$curr] ?? $plan['prices']['solo']['XAF'];

        return [
            'plan_id'         => $plan['id'],
            'plan_name'       => $plan['name'],
            'headline'        => $plan['headline'],
            'badge'           => $plan['badge'],
            'composition'     => $comp,
            'currency'        => $curr,
            'amount'          => $priceObj['amount'],
            'label'           => $priceObj['label'],
            'sub'             => $priceObj['sub'],
            'ceiling'         => $plan['ceiling_xaf'],
            'features'        => $plan['features'],
            'tiers_payant'    => $plan['tiers_payant'],
        ];
    }

    /**
     * Calcule le devis santé collective pour une PME / Entreprise
     */
    public function calculateCorporateQuote(int $employeeCount, string $planTier = 'silver'): array {
        $count = max(5, $employeeCount);
        $baseRate = 30000; // Tarif de base mensuel en FCFA par salarié
        $discountPct = 0;
        $tierName = 'PME Standard';

        if ($count >= 101) {
            $discountPct = 25;
            $tierName = 'Grand Compte';
        } elseif ($count >= 21) {
            $discountPct = 20;
            $tierName = 'Moyenne Entreprise (20-100 salariés)';
        } elseif ($count >= 10) {
            $discountPct = 10;
            $tierName = 'Petite Entreprise (10-20 salariés)';
        }

        $unitRate = (int) round($baseRate * (1 - ($discountPct / 100)));
        $monthlyTotal = $unitRate * $count;
        $annualTotal = $monthlyTotal * 12;

        return [
            'employee_count'    => $count,
            'tier_name'         => $tierName,
            'discount_percent'  => $discountPct,
            'unit_rate_monthly' => $unitRate,
            'unit_rate_label'   => number_format($unitRate, 0, ',', ' ') . ' FCFA / salarié / mois',
            'monthly_total'     => $monthlyTotal,
            'monthly_label'     => number_format($monthlyTotal, 0, ',', ' ') . ' FCFA / mois',
            'annual_total'      => $annualTotal,
            'annual_label'      => number_format($annualTotal, 0, ',', ' ') . ' FCFA / an',
            'tax_deductible'    => '100% déductible des charges d\'exploitation',
        ];
    }
}
