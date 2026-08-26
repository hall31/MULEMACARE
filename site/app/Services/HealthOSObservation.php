<?php
declare(strict_types=1);

namespace App\Services;

/**
 * Mode observation du bridge HealthOS : comparer, mesurer, n'écrire nulle part.
 *
 * Avant d'ouvrir les droits HealthOS aux adhérents MulemaCare, il faut savoir
 * si les deux systèmes disent la même chose des mêmes personnes. C'est ce que
 * fait cette classe : pour chaque numéro CSSA rapproché, elle demande sa
 * décision au site, demande celle de HealthOS, et décrit l'écart.
 *
 * Trois propriétés font que le mot « observation » est tenu :
 *
 * 1. Rien n'écrit. Le service n'a ni PDO, ni chemin de fichier, ni méthode qui
 *    modifie une adhésion. Le seul appel sortant est un `GET` d'éligibilité —
 *    et la clé partenaire du pilote ne porte que `eligibility:read`, donc
 *    HealthOS refuserait une écriture même demandée (`0018`).
 * 2. Rien ne dépend de la réponse. Aucune page, aucun contrôleur n'appelle ce
 *    service : il est exécuté par `scripts/healthos_observation_run.php`. Un
 *    adhérent ne voit jamais la décision de HealthOS pendant cette phase, donc
 *    une divergence ne peut pas lui coûter un remboursement.
 * 3. Rien n'est comparé à une fiction. Les adhésions servies par le repli de
 *    démonstration de `MembershipService::verifyCard()` sont écartées : elles
 *    ne décrivent personne, et l'écart mesuré sur elles ne dirait rien.
 */
final class HealthOSObservation
{
    public const VERDICT_MATCH = 'match';
    public const VERDICT_DIVERGENT = 'divergent';
    public const VERDICT_UNREACHABLE = 'unreachable';
    public const VERDICT_UNMAPPED = 'unmapped';
    public const VERDICT_NOT_A_RECORD = 'not_a_record';
    public const VERDICT_UNKNOWN_TO_SITE = 'unknown_to_site';

    private array $bridge;

    public function __construct(
        array $config,
        private MembershipService $memberships,
        private HealthOSRightsReader $client,
        private HealthOSIdentityMap $identityMap
    ) {
        $this->bridge = $config['healthos_bridge'] ?? [];
    }

    /**
     * Le rapprochement est-il exécutable ?
     *
     * Il faut le bridge activé, le mode `observe`, et une table de
     * correspondance exploitable. Trois conditions, trois raisons distinctes de
     * ne rien faire — l'appelant a besoin de savoir laquelle.
     */
    public function isRunnable(): bool
    {
        return $this->client->isEnabled()
            && $this->mode() === 'observe'
            && $this->identityMap->isUsable();
    }

    /** @return list<string> Ce qui empêche l'exécution, en clair. */
    public function blockers(): array
    {
        $blockers = [];
        if (!$this->client->isEnabled()) {
            $blockers[] = 'Bridge désactivé (MULEMACARE_HEALTHOS_BRIDGE_ENABLED, HEALTHOS_BASE_URL, HEALTHOS_PARTNER_API_KEY).';
        }
        if ($this->mode() !== 'observe') {
            $blockers[] = sprintf('Mode « %s » : le rapprochement ne tourne qu\'en mode « observe ».', $this->mode());
        }
        if (!$this->identityMap->isUsable()) {
            foreach ($this->identityMap->problems() as $problem) {
                $blockers[] = $problem;
            }
        }
        return $blockers;
    }

    public function mode(): string
    {
        $mode = strtolower(trim((string) ($this->bridge['mode'] ?? 'observe')));
        return $mode !== '' ? $mode : 'observe';
    }

    /**
     * Compare la décision du site et celle de HealthOS pour un numéro CSSA.
     *
     * Retourne toujours un compte rendu, y compris quand la comparaison n'a pas
     * pu avoir lieu : un rapprochement qui tait ses trous n'est pas un
     * rapprochement.
     */
    public function compare(string $cssaNumber): array
    {
        $cssa = strtoupper(trim($cssaNumber));
        $report = [
            'cssa_number' => $cssa,
            'patient_id' => null,
            'verdict' => self::VERDICT_UNMAPPED,
            'divergences' => [],
            'site' => null,
            'healthos' => null,
        ];

        $patientId = $this->identityMap->patientIdFor($cssa);
        if ($patientId === null) {
            return $report;
        }
        $report['patient_id'] = $patientId;

        $card = $this->memberships->verifyCard($cssa);
        if ($card === null) {
            $report['verdict'] = self::VERDICT_UNKNOWN_TO_SITE;
            return $report;
        }
        if (($card['source'] ?? '') !== 'record') {
            $report['verdict'] = self::VERDICT_NOT_A_RECORD;
            return $report;
        }

        $site = $this->siteDecision($card);
        $report['site'] = $site;

        $rights = $this->client->eligibility($patientId);
        if ($rights === null) {
            $report['verdict'] = self::VERDICT_UNREACHABLE;
            return $report;
        }

        $healthos = $this->healthosDecision($rights);
        $report['healthos'] = $healthos;
        $report['divergences'] = $this->divergences($site, $healthos);
        $report['verdict'] = $report['divergences'] === []
            ? self::VERDICT_MATCH
            : self::VERDICT_DIVERGENT;

        return $report;
    }

    /**
     * Rapproche tous les numéros de la table de correspondance.
     *
     * @return array{blockers: list<string>, reports: list<array>, summary: array<string,int>}
     */
    public function run(): array
    {
        $blockers = $this->blockers();
        if ($blockers !== []) {
            return ['blockers' => $blockers, 'reports' => [], 'summary' => []];
        }

        $reports = [];
        $summary = [];
        foreach (array_keys($this->identityMap->pairs()) as $cssa) {
            $report = $this->compare($cssa);
            $reports[] = $report;
            $verdict = $report['verdict'];
            $summary[$verdict] = ($summary[$verdict] ?? 0) + 1;
        }

        return ['blockers' => [], 'reports' => $reports, 'summary' => $summary];
    }

    /** @param array<string,mixed> $card */
    private function siteDecision(array $card): array
    {
        $remaining = (float) ($card['remaining_cap'] ?? 0.0);
        $status = strtoupper((string) ($card['status'] ?? ''));
        return [
            'covered' => $status === 'ACTIVE' && $remaining > 0.0,
            'status' => $status,
            'remaining_cap' => $remaining,
            'annual_cap' => (float) ($card['annual_cap'] ?? 0.0),
            'waiting_period' => $this->siteWaitingPeriod($card),
        ];
    }

    /**
     * La carence est un libellé côté site, un booléen côté HealthOS.
     *
     * Les libellés connus sont traduits ; tout autre libellé rend `null`, et
     * `null` ne se compare pas. Deviner qu'un libellé inconnu signifie « pas de
     * carence » inventerait une concordance là où il y a un doute.
     */
    private function siteWaitingPeriod(array $card): ?bool
    {
        $label = mb_strtolower(trim((string) ($card['carence_general'] ?? '')));
        if ($label === '') {
            return null;
        }
        if (str_contains($label, 'achevée') || str_contains($label, 'achevee') || str_contains($label, 'validé') || str_contains($label, 'valide')) {
            return false;
        }
        if (str_contains($label, 'en cours') || str_contains($label, 'carence restante')) {
            return true;
        }
        return null;
    }

    /** @param array<string,mixed> $rights */
    private function healthosDecision(array $rights): array
    {
        $remainingMinor = $rights['remaining_balance'] ?? null;
        return [
            'covered' => ($rights['eligible'] ?? false) === true,
            'plan' => (string) ($rights['plan'] ?? ''),
            'coverage_percent' => isset($rights['coverage_percent']) ? (int) $rights['coverage_percent'] : null,
            // `null` signifie « plafond annuel illimité » dans HealthOS, pas zéro.
            'remaining_cap' => $remainingMinor === null ? null : $this->fromMinorUnits((int) $remainingMinor),
            'waiting_period' => isset($rights['waiting_period']) ? (bool) $rights['waiting_period'] : null,
        ];
    }

    /**
     * HealthOS compte en unités mineures, le site en francs CFA.
     *
     * Le franc CFA n'a pas de subdivision en usage : le diviseur vaut 1 par
     * défaut. Il reste configurable parce qu'une comparaison faussée d'un
     * facteur 100 produirait un écart sur chaque adhérent, et que découvrir ce
     * facteur au milieu d'un rapport de rapprochement coûte une journée.
     */
    private function fromMinorUnits(int $amountMinor): float
    {
        $divisor = (int) ($this->bridge['minor_units_per_unit'] ?? 1);
        return $divisor > 0 ? $amountMinor / $divisor : (float) $amountMinor;
    }

    /**
     * @param array<string,mixed> $site
     * @param array<string,mixed> $healthos
     * @return list<array<string,mixed>>
     */
    private function divergences(array $site, array $healthos): array
    {
        $divergences = [];

        if ($site['covered'] !== $healthos['covered']) {
            $divergences[] = [
                'field' => 'covered',
                'site' => $site['covered'],
                'healthos' => $healthos['covered'],
                'explanation' => $site['covered']
                    ? 'Le site couvre cet adhérent, HealthOS non : police absente, expirée, ou plafond épuisé côté HealthOS.'
                    : 'HealthOS couvre cet adhérent, le site non : statut d\'adhésion ou plafond restant divergent côté site.',
            ];
        }

        if ($site['waiting_period'] !== null && $healthos['waiting_period'] !== null
            && $site['waiting_period'] !== $healthos['waiting_period']) {
            $divergences[] = [
                'field' => 'waiting_period',
                'site' => $site['waiting_period'],
                'healthos' => $healthos['waiting_period'],
                'explanation' => 'Les deux systèmes ne datent pas la carence de la même façon : date d\'effet ou durée de plan à rapprocher.',
            ];
        }

        if ($healthos['remaining_cap'] !== null) {
            $gap = abs($site['remaining_cap'] - $healthos['remaining_cap']);
            $tolerance = (float) ($this->bridge['cap_tolerance'] ?? 0.0);
            if ($gap > $tolerance) {
                $divergences[] = [
                    'field' => 'remaining_cap',
                    'site' => $site['remaining_cap'],
                    'healthos' => $healthos['remaining_cap'],
                    'gap' => $gap,
                    'explanation' => 'Plafond restant différent : sinistres réglés d\'un côté et pas de l\'autre, ou préautorisations réservées dans HealthOS.',
                ];
            }
        }

        return $divergences;
    }
}
