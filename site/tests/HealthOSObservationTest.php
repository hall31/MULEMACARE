<?php
declare(strict_types=1);

use App\Services\HealthOSIdentityMap;
use App\Services\HealthOSObservation;
use App\Services\HealthOSRightsReader;
use App\Services\MembershipService;

/** Droits HealthOS servis depuis un scénario, et qui compte ce qu'on lui demande. */
final class FakeRightsReader implements HealthOSRightsReader
{
    public int $calls = 0;

    /** @param array<string,array<string,mixed>|null> $rightsByPatient */
    public function __construct(private array $rightsByPatient, private bool $enabled = true)
    {
    }

    public function isEnabled(): bool
    {
        return $this->enabled;
    }

    public function eligibility(string $healthosPatientId): ?array
    {
        $this->calls++;
        return $this->rightsByPatient[$healthosPatientId] ?? null;
    }
}

/** Adhésions servies depuis un scénario, sans base ni fichier. */
final class FakeMemberships extends MembershipService
{
    /** @param array<string,array<string,mixed>|null> $cards */
    public function __construct(private array $cards)
    {
        parent::__construct([]);
    }

    public function verifyCard(string $cssaId): ?array
    {
        return $this->cards[strtoupper(trim($cssaId))] ?? null;
    }
}

/**
 * Le rapprochement en mode observation.
 *
 * Deux choses sont vérifiées ici : que les écarts réels sont vus, et que les
 * écarts inventés ne le sont pas. Un rapprochement qui crie au loup sur des
 * unités mal converties ou sur des adhésions de démonstration ne sera pas lu,
 * et le bridge s'ouvrira sans que personne n'ait rien vérifié.
 */
final class HealthOSObservationTest
{
    private array $written = [];

    public function __destruct()
    {
        foreach ($this->written as $path) {
            @unlink($path);
        }
    }

    private function card(array $overrides = []): array
    {
        return array_merge([
            'source' => 'record',
            'cssa_id' => 'CSSA-4921-26',
            'status' => 'ACTIVE',
            'annual_cap' => 1500000.0,
            'consumed_cap' => 124500.0,
            'remaining_cap' => 1375500.0,
            'carence_general' => 'Validé · Carence achevée',
        ], $overrides);
    }

    private function rights(array $overrides = []): array
    {
        return array_merge([
            'eligible' => true,
            'plan' => 'CONFORT',
            'coverage_percent' => 70,
            'remaining_balance' => 1375500,
            'waiting_period' => false,
            'policy_id' => 'policy-amina',
        ], $overrides);
    }

    private function observation(
        array $cards,
        array $rightsByPatient,
        array $bridge = [],
        ?array $entries = null
    ): array {
        $path = sys_get_temp_dir() . '/mulemacare_obs_map_' . bin2hex(random_bytes(6)) . '.json';
        file_put_contents($path, json_encode([
            'tenant' => 'mulemacare-pilote',
            'entries' => $entries ?? [[
                'cssa_number' => 'CSSA-4921-26',
                'healthos_patient_id' => 'patient-amina',
                'validated_at' => '2026-08-20',
                'validated_by' => 'migration de données',
            ]],
        ], JSON_UNESCAPED_UNICODE));
        $this->written[] = $path;

        $config = ['healthos_bridge' => array_merge(['mode' => 'observe'], $bridge)];
        $reader = new FakeRightsReader($rightsByPatient);
        $observation = new HealthOSObservation(
            $config,
            new FakeMemberships($cards),
            $reader,
            new HealthOSIdentityMap($config, $path)
        );

        return [$observation, $reader];
    }

    public function testTwoSystemsThatAgreeProduceNoDivergence(): void
    {
        [$observation] = $this->observation(
            ['CSSA-4921-26' => $this->card()],
            ['patient-amina' => $this->rights()]
        );

        $report = $observation->compare('CSSA-4921-26');

        assertSame(HealthOSObservation::VERDICT_MATCH, $report['verdict']);
        assertSame([], $report['divergences']);
        assertSame('patient-amina', $report['patient_id']);
    }

    public function testCoverageDisagreementIsReportedAndExplained(): void
    {
        [$observation] = $this->observation(
            ['CSSA-4921-26' => $this->card()],
            ['patient-amina' => $this->rights(['eligible' => false])]
        );

        $report = $observation->compare('CSSA-4921-26');

        assertSame(HealthOSObservation::VERDICT_DIVERGENT, $report['verdict']);
        assertSame('covered', $report['divergences'][0]['field']);
        assertContainsString('plafond épuisé', $report['divergences'][0]['explanation']);
    }

    public function testARemainingCapGapIsMeasured(): void
    {
        [$observation] = $this->observation(
            ['CSSA-4921-26' => $this->card()],
            ['patient-amina' => $this->rights(['remaining_balance' => 1000000])]
        );

        $report = $observation->compare('CSSA-4921-26');

        assertSame('remaining_cap', $report['divergences'][0]['field']);
        assertSame(375500.0, $report['divergences'][0]['gap']);
    }

    public function testAGapUnderToleranceIsNotReported(): void
    {
        [$observation] = $this->observation(
            ['CSSA-4921-26' => $this->card()],
            ['patient-amina' => $this->rights(['remaining_balance' => 1375400])],
            ['cap_tolerance' => 500.0]
        );

        $report = $observation->compare('CSSA-4921-26');

        assertSame(HealthOSObservation::VERDICT_MATCH, $report['verdict']);
    }

    public function testAnUnlimitedHealthosCapIsNotAZeroCap(): void
    {
        [$observation] = $this->observation(
            ['CSSA-4921-26' => $this->card()],
            ['patient-amina' => $this->rights(['remaining_balance' => null])]
        );

        $report = $observation->compare('CSSA-4921-26');

        assertSame(HealthOSObservation::VERDICT_MATCH, $report['verdict'], 'Un plafond illimité n\'est pas un plafond épuisé.');
        assertSame(null, $report['healthos']['remaining_cap']);
    }

    public function testTheMinorUnitDivisorIsApplied(): void
    {
        [$observation] = $this->observation(
            ['CSSA-4921-26' => $this->card()],
            ['patient-amina' => $this->rights(['remaining_balance' => 137550000])],
            ['minor_units_per_unit' => 100]
        );

        $report = $observation->compare('CSSA-4921-26');

        assertSame(HealthOSObservation::VERDICT_MATCH, $report['verdict'], 'Une conversion d\'unité ratée ferait diverger tout le monde.');
    }

    public function testAnUnknownWaitingPeriodLabelInventsNothing(): void
    {
        [$observation] = $this->observation(
            ['CSSA-4921-26' => $this->card(['carence_general' => 'Statut particulier à qualifier'])],
            ['patient-amina' => $this->rights(['waiting_period' => true])]
        );

        $report = $observation->compare('CSSA-4921-26');

        assertSame(null, $report['site']['waiting_period']);
        assertSame(HealthOSObservation::VERDICT_MATCH, $report['verdict'], 'Un libellé non compris est un doute, pas un écart.');
    }

    public function testAnUnreachableGatewayIsSaidNotGuessed(): void
    {
        [$observation] = $this->observation(
            ['CSSA-4921-26' => $this->card()],
            ['patient-amina' => null]
        );

        $report = $observation->compare('CSSA-4921-26');

        assertSame(HealthOSObservation::VERDICT_UNREACHABLE, $report['verdict']);
        assertSame([], $report['divergences'], 'Une absence de réponse n\'est pas une concordance ni un écart.');
    }

    public function testAnUnmappedMemberIsNeverAskedAbout(): void
    {
        [$observation, $reader] = $this->observation(
            ['CSSA-9999-26' => $this->card(['cssa_id' => 'CSSA-9999-26'])],
            ['patient-amina' => $this->rights()]
        );

        $report = $observation->compare('CSSA-9999-26');

        assertSame(HealthOSObservation::VERDICT_UNMAPPED, $report['verdict']);
        assertSame(0, $reader->calls, 'Aucun appel ne doit partir pour un adhérent non rapproché.');
    }

    public function testADemoMembershipIsNeverCompared(): void
    {
        [$observation, $reader] = $this->observation(
            ['CSSA-4921-26' => $this->card(['source' => 'demo_fallback'])],
            ['patient-amina' => $this->rights()]
        );

        $report = $observation->compare('CSSA-4921-26');

        assertSame(HealthOSObservation::VERDICT_NOT_A_RECORD, $report['verdict']);
        assertSame(0, $reader->calls, 'Comparer une fiche de démonstration produirait un écart qui ne dit rien.');
    }

    public function testTheRunRefusesOutsideObservationMode(): void
    {
        [$observation] = $this->observation(
            ['CSSA-4921-26' => $this->card()],
            ['patient-amina' => $this->rights()],
            ['mode' => 'read']
        );

        $result = $observation->run();

        assertFalse($observation->isRunnable());
        assertSame([], $result['reports']);
        assertContainsString('mode « observe »', implode("\n", $result['blockers']));
    }

    public function testTheRunSummarisesEveryMappedMember(): void
    {
        [$observation] = $this->observation(
            [
                'CSSA-4921-26' => $this->card(),
                'CSSA-1088-26' => $this->card(['cssa_id' => 'CSSA-1088-26', 'status' => 'SUSPENDED']),
            ],
            [
                'patient-amina' => $this->rights(),
                'patient-kofi' => $this->rights(),
            ],
            [],
            [
                ['cssa_number' => 'CSSA-4921-26', 'healthos_patient_id' => 'patient-amina', 'validated_at' => '2026-08-20', 'validated_by' => 'migration'],
                ['cssa_number' => 'CSSA-1088-26', 'healthos_patient_id' => 'patient-kofi', 'validated_at' => '2026-08-20', 'validated_by' => 'migration'],
            ]
        );

        $result = $observation->run();

        assertSame(2, count($result['reports']));
        assertSame(1, $result['summary'][HealthOSObservation::VERDICT_MATCH]);
        assertSame(1, $result['summary'][HealthOSObservation::VERDICT_DIVERGENT]);
    }

    /**
     * Le mode observation n'observe que si personne ne s'en sert pour décider.
     *
     * Ce test regarde le code du site : si un contrôleur ou une vue se met à
     * appeler le rapprochement, un adhérent peut se voir refuser une prise en
     * charge à cause d'un écart que l'on est justement en train de mesurer.
     */
    public function testNoPageDependsOnTheObservation(): void
    {
        $siteRoot = dirname(__DIR__);
        $callers = [];
        $directories = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($siteRoot));
        foreach ($directories as $file) {
            if (!$file->isFile() || $file->getExtension() !== 'php') {
                continue;
            }
            $path = (string) $file->getPathname();
            if (str_starts_with($path, $siteRoot . '/tests/')
                || str_starts_with($path, $siteRoot . '/scripts/')
                || str_starts_with($path, $siteRoot . '/app/Services/')) {
                continue;
            }
            if (str_contains((string) file_get_contents($path), 'HealthOSObservation')) {
                $callers[] = substr($path, strlen($siteRoot) + 1);
            }
        }

        assertSame([], $callers, 'Aucune page ne doit dépendre du rapprochement pendant la phase d\'observation.');
    }
}
