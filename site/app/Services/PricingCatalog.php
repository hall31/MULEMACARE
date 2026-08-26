<?php
declare(strict_types=1);

namespace App\Services;

use JsonException;
use RuntimeException;

/**
 * Source unique de la grille tarifaire Diaspora.
 *
 * Le site portait deux grilles qui divergeaient de 36 % sur la formule haute :
 * l'une écrite en dur dans les pages, l'autre dans `config.php`. Le client
 * achetait au prix de la page et recevait un devis officiel à l'autre. Ce
 * service existe pour qu'il n'y ait plus qu'un endroit où un montant est écrit.
 *
 * Les montants sont manipulés **en centimes entiers**, jamais en flottants :
 * `15.99 * 12` ne vaut pas `191.88` en virgule flottante, et une cotisation qui
 * dérive d'un centime au douzième mois est une réclamation.
 *
 * Le FCFA n'a pas de sous-unité : les plafonds « famille au pays » sont des
 * entiers de francs, pas des centimes.
 */
final class PricingCatalog
{
    /** Parité fixe EUR/XAF. Ce n'est pas un taux de marché : le franc CFA est arrimé à l'euro. */
    public const XAF_PER_EUR = 655.957;

    private array $data;

    private function __construct(array $data)
    {
        $this->data = $data;
    }

    /** Charge et valide la grille. Lève si le fichier est absent, illisible ou structurellement faux. */
    public static function load(?string $path = null): self
    {
        $path ??= __DIR__ . '/../../pricing/diaspora-2026.json';

        if (!is_readable($path)) {
            throw new RuntimeException("Grille tarifaire introuvable : {$path}");
        }

        try {
            $data = json_decode((string) file_get_contents($path), true, 32, JSON_THROW_ON_ERROR);
        } catch (JsonException $e) {
            throw new RuntimeException("Grille tarifaire illisible : {$e->getMessage()}", 0, $e);
        }

        if (!is_array($data) || !isset($data['lines']['europe']['offers'], $data['lines']['famille_au_pays']['profiles'])) {
            throw new RuntimeException('Grille tarifaire incomplète : les deux gammes sont obligatoires.');
        }

        return new self($data);
    }

    public function version(): string
    {
        return (string) ($this->data['version'] ?? 'inconnue');
    }

    public function effectiveDate(): string
    {
        return (string) ($this->data['effective_date'] ?? '');
    }

    /**
     * Vrai tant que la grille n'a pas reçu la validation actuarielle et réglementaire.
     *
     * Toute surface publique doit consulter ce drapeau : publier un tarif non
     * validé engage la mutuelle sur un prix qu'elle n'a pas le droit d'opposer.
     */
    public function isProvisional(): bool
    {
        return ($this->data['status'] ?? '') !== 'validated';
    }

    public function statusNote(): string
    {
        return (string) ($this->data['status_note'] ?? '');
    }

    /** Qui a prononcé la validation, ou `null` tant qu'elle n'a pas eu lieu. */
    public function validatedBy(): ?string
    {
        $by = $this->data['validated_by'] ?? null;

        return is_string($by) && $by !== '' ? $by : null;
    }

    /** Date de la validation au format `AAAA-MM-JJ`, ou `null`. */
    public function validatedAt(): ?string
    {
        $at = $this->data['validated_at'] ?? null;

        return is_string($at) && $at !== '' ? $at : null;
    }

    /** Ratio maximal prime annuelle / plafond annuel, en pourcentage entier, pour la gamme « famille au pays ». */
    public function maxPremiumRatioPct(): int
    {
        return (int) ($this->data['rules']['famille_au_pays_max_premium_ratio_pct'] ?? 56);
    }

    // ---------------------------------------------------------------- Europe

    /** @return list<array<string,mixed>> */
    public function europeOffers(): array
    {
        return array_values($this->data['lines']['europe']['offers']);
    }

    /** @return array<string,mixed>|null */
    public function europeOffer(string $id): ?array
    {
        foreach ($this->europeOffers() as $offer) {
            if ($offer['id'] === $id) {
                return $offer;
            }
        }

        return null;
    }

    // ------------------------------------------------------- Famille au pays

    /** @return list<array<string,mixed>> */
    public function homeProfiles(): array
    {
        return array_values($this->data['lines']['famille_au_pays']['profiles']);
    }

    /** @return array<string,mixed>|null */
    public function homeProfile(string $id): ?array
    {
        foreach ($this->homeProfiles() as $profile) {
            if ($profile['id'] === $id) {
                return $profile;
            }
        }

        return null;
    }

    /**
     * Retourne une formule d'un profil, ou `null` si elle n'existe pas.
     *
     * Le `null` est un cas métier, pas une erreur : le profil « Étudiant » n'a
     * pas de formule A. Un appelant qui suppose A/B/C partout se trompe.
     *
     * @return array<string,mixed>|null
     */
    public function homeTier(string $profileId, string $formula): ?array
    {
        $profile = $this->homeProfile($profileId);
        $tier = $profile['tiers'][strtoupper($formula)] ?? null;

        return is_array($tier) ? $tier : null;
    }

    /** Formules réellement proposées pour ce profil, dans l'ordre A, B, C. @return list<string> */
    public function homeFormulas(string $profileId): array
    {
        $profile = $this->homeProfile($profileId);
        if ($profile === null) {
            return [];
        }

        $ordered = [];
        foreach (($this->data['lines']['famille_au_pays']['formulas'] ?? []) as $letter) {
            if (isset($profile['tiers'][$letter])) {
                $ordered[] = $letter;
            }
        }

        return $ordered;
    }

    // -------------------------------------------------------------- Calculs

    /**
     * Cotisation annuelle = douze mensualités. La grille ne prévoit aucune remise annuelle.
     *
     * Le code précédent appliquait `* 12 * 0.90`, une remise de 10 % qui
     * n'existe nulle part dans le tarif validé.
     */
    public function annualCents(int $monthlyCents): int
    {
        return $monthlyCents * 12;
    }

    /** Convertit des francs CFA en centimes d'euro, arrondi au centime le plus proche. */
    public function xafToEurCents(int $xaf): int
    {
        return (int) round($xaf / self::XAF_PER_EUR * 100);
    }

    /** Convertit des centimes d'euro en francs CFA, arrondi au franc le plus proche. */
    public function eurCentsToXaf(int $cents): int
    {
        return (int) round($cents / 100 * self::XAF_PER_EUR);
    }

    /** Formate des centimes d'euro pour l'affichage : `1599` → `15,99 €`. */
    public function formatEur(int $cents): string
    {
        return number_format($cents / 100, 2, ',', ' ') . ' €';
    }

    /** Formate des francs CFA pour l'affichage : `35000` → `35 000 FCFA`. */
    public function formatXaf(int $xaf): string
    {
        return number_format($xaf, 0, ',', ' ') . ' FCFA';
    }

    // ----------------------------------------------------------- Invariants

    /**
     * Contrôle les règles que la grille doit respecter, et renvoie les écarts.
     *
     * Deux règles, toutes deux vérifiées sur la grille v6.1.0 :
     *
     *  1. la cotisation annuelle vaut exactement douze mensualités ;
     *  2. pour « famille au pays », la prime annuelle ne dépasse pas 56 % du
     *     plafond annuel. Le profil Collégien A est **exactement** à 56,000 % :
     *     c'est cette règle qui a fixé son prix. Toute baisse de plafond ou
     *     hausse de cotisation la fait sortir, et ce contrôle doit le dire.
     *
     * La comparaison se fait en francs entiers : convertir la prime en FCFA
     * plutôt que le plafond en euros évite qu'un arrondi au centime décide
     * du verdict sur un cas saturé.
     *
     * @return list<string> Vide si la grille est conforme.
     */
    public function invariantViolations(): array
    {
        $violations = [];
        $maxRatio = $this->maxPremiumRatioPct();

        foreach ($this->europeOffers() as $offer) {
            $expected = $this->annualCents((int) $offer['monthly_cents']);
            if ((int) $offer['annual_cents'] !== $expected) {
                $violations[] = sprintf(
                    'Europe/%s : cotisation annuelle %d, attendue %d (douze mensualités).',
                    $offer['id'],
                    (int) $offer['annual_cents'],
                    $expected
                );
            }
        }

        foreach ($this->homeProfiles() as $profile) {
            foreach ($profile['tiers'] as $letter => $tier) {
                $annualXaf = $this->eurCentsToXaf($this->annualCents((int) $tier['monthly_cents']));
                $ceiling = (int) $tier['ceiling_xaf'];

                // Entiers des deux côtés : `prime * 100 <= ratio * plafond`.
                if ($annualXaf * 100 > $maxRatio * $ceiling) {
                    $violations[] = sprintf(
                        'Famille au pays/%s %s : prime annuelle %s pour un plafond de %s, soit %.2f %% (maximum %d %%).',
                        $profile['id'],
                        $letter,
                        $this->formatXaf($annualXaf),
                        $this->formatXaf($ceiling),
                        $annualXaf / $ceiling * 100,
                        $maxRatio
                    );
                }
            }
        }

        return $violations;
    }
}
