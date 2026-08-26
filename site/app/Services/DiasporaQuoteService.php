<?php
declare(strict_types=1);

namespace App\Services;

use InvalidArgumentException;

/**
 * Calcule un devis dans la grammaire de la grille Diaspora v6.1.0.
 *
 * L'ancienne grammaire — `plan_id` (bronze/silver/gold/platinium) ×
 * `composition` (solo/couple/family/seniors) — est incompatible avec cette
 * grille : il n'y a plus de formules uniques, mais deux gammes qui ne se
 * ressemblent pas. « Europe » est un choix plat parmi quatre offres. « Famille
 * au pays » croise un profil (bornes d'âge, nombre de bénéficiaires) avec une
 * formule A/B/C que tous les profils ne proposent pas. `QuoteService` garde
 * l'ancienne grammaire pour ses appelants existants ; ce service est le
 * nouveau, et les deux coexistent jusqu'à ce que simulateur et tunnel soient
 * rebranchés.
 *
 * Différence délibérée avec `PricingCatalog` : ce dernier renvoie `null` pour
 * un cas métier valide (`homeTier('etudiant', 'A')` — Étudiant n'a pas de
 * formule A). Ici, un identifiant d'offre ou une formule absente est une
 * erreur de saisie de l'appelant, pas un cas métier : elle doit lever, pas se
 * résoudre silencieusement vers une offre par défaut. C'est précisément le
 * silence qui masquait les défauts trouvés dans l'ancien moteur.
 */
final class DiasporaQuoteService
{
    private PricingCatalog $catalog;

    public function __construct(?PricingCatalog $catalog = null)
    {
        $this->catalog = $catalog ?? PricingCatalog::load();
    }

    /**
     * Devis pour une offre Europe (Essentiel, Famille +, Chronique, Premium).
     *
     * @throws InvalidArgumentException si l'offre n'existe pas.
     */
    public function quoteEurope(string $offerId, string $cycle = 'annual'): array
    {
        $offer = $this->catalog->europeOffer($offerId);
        if ($offer === null) {
            throw new InvalidArgumentException(sprintf(
                "Offre Europe inconnue : « %s ». Offres disponibles : %s.",
                $offerId,
                implode(', ', array_column($this->catalog->europeOffers(), 'id'))
            ));
        }

        $cycle = $cycle === 'monthly' ? 'monthly' : 'annual';
        $monthly = (int) $offer['monthly_cents'];
        $annual = (int) $offer['annual_cents'];

        return [
            'line'               => 'europe',
            'offer_id'           => $offer['id'],
            'label'              => $offer['label'],
            'cycle'              => $cycle,
            'monthly_cents'      => $monthly,
            'annual_cents'       => $annual,
            'selected_cents'     => $cycle === 'monthly' ? $monthly : $annual,
            'coverage_rate_pct'  => (int) $offer['coverage_rate_pct'],
            'ceiling_cents'      => (int) $offer['ceiling_cents'],
            'ceiling_currency'   => 'EUR',
            'beneficiaries'      => $offer['scope'],
            'monthly_label'      => $this->catalog->formatEur($monthly),
            'annual_label'       => $this->catalog->formatEur($annual),
            'ceiling_label'      => $this->catalog->formatEur((int) $offer['ceiling_cents']),
        ];
    }

    /**
     * Devis pour un profil « famille au pays », dans une formule A/B/C.
     *
     * `$age`, si fourni, est confronté aux bornes du profil et le résultat
     * apparaît dans `age_eligible`. Aucune borne d'âge n'existait dans
     * l'ancien moteur ; les profils de cette grille en portent (Collégien
     * 10–25 ans, Senior 45 ans et plus…) et un devis qui les ignore vend une
     * couverture que la mutuelle serait fondée à refuser à la souscription.
     *
     * @throws InvalidArgumentException si le profil est inconnu, ou si la
     *         formule demandée n'est pas proposée par ce profil.
     */
    public function quoteFamilleAuPays(string $profileId, string $formula, string $cycle = 'annual', ?int $age = null): array
    {
        $profile = $this->catalog->homeProfile($profileId);
        if ($profile === null) {
            throw new InvalidArgumentException(sprintf(
                "Profil « famille au pays » inconnu : « %s ». Profils disponibles : %s.",
                $profileId,
                implode(', ', array_column($this->catalog->homeProfiles(), 'id'))
            ));
        }

        $formula = strtoupper($formula);
        $tier = $this->catalog->homeTier($profileId, $formula);
        if ($tier === null) {
            throw new InvalidArgumentException(sprintf(
                'Le profil « %s » ne propose pas la formule %s. Formules disponibles : %s.',
                $profile['label'],
                $formula,
                implode(', ', $this->catalog->homeFormulas($profileId))
            ));
        }

        $cycle = $cycle === 'monthly' ? 'monthly' : 'annual';
        $monthly = (int) $tier['monthly_cents'];
        $annual = $this->catalog->annualCents($monthly);
        $ceilingXaf = (int) $tier['ceiling_xaf'];
        $ceilingEurCents = $this->catalog->xafToEurCents($ceilingXaf);

        return [
            'line'               => 'famille_au_pays',
            'profile_id'         => $profile['id'],
            'profile_label'      => $profile['label'],
            'formula'            => $formula,
            'cycle'              => $cycle,
            'monthly_cents'      => $monthly,
            'annual_cents'       => $annual,
            'selected_cents'     => $cycle === 'monthly' ? $monthly : $annual,
            'coverage_rate_pct'  => (int) $tier['coverage_rate_pct'],
            'ceiling_xaf'        => $ceilingXaf,
            'ceiling_eur_cents'  => $ceilingEurCents,
            'beneficiaries_min'  => (int) $profile['beneficiaries_min'],
            'beneficiaries_max'  => (int) $profile['beneficiaries_max'],
            'age_label'          => $profile['age_label'],
            'age_eligible'       => $this->isAgeEligible($profile, $age),
            'monthly_label'      => $this->catalog->formatEur($monthly),
            'annual_label'       => $this->catalog->formatEur($annual),
            'ceiling_label'      => sprintf(
                '%s (%s)',
                $this->catalog->formatXaf($ceilingXaf),
                $this->catalog->formatEur($ceilingEurCents)
            ),
        ];
    }

    /**
     * `null` si l'âge n'est pas fourni — « pas encore évalué », distinct de
     * `false` qui signifie « évalué et hors bornes ». Un appelant qui ne
     * connaît pas encore l'âge du bénéficiaire ne doit pas voir un refus
     * qu'il n'a pas demandé.
     */
    private function isAgeEligible(array $profile, ?int $age): ?bool
    {
        if ($age === null) {
            return null;
        }

        if ($age < (int) $profile['age_min']) {
            return false;
        }

        if ($profile['age_max'] !== null && $age > (int) $profile['age_max']) {
            return false;
        }

        return true;
    }
}
