<?php
declare(strict_types=1);

use App\Services\HealthOSIdentityMap;

/**
 * La table de correspondance CSSA -> patient_id HealthOS.
 *
 * Ce qui est vérifié ici n'est pas du confort : une correspondance devinée,
 * périmée ou ambiguë montre les droits de santé de quelqu'un à quelqu'un
 * d'autre.
 */
final class HealthOSIdentityMapTest
{
    private array $written = [];

    public function __destruct()
    {
        foreach ($this->written as $path) {
            @unlink($path);
        }
    }

    private function mapWith(array $payload, array $bridge = []): HealthOSIdentityMap
    {
        $path = sys_get_temp_dir() . '/mulemacare_identity_map_' . bin2hex(random_bytes(6)) . '.json';
        file_put_contents($path, json_encode($payload, JSON_UNESCAPED_UNICODE));
        $this->written[] = $path;
        return new HealthOSIdentityMap(['healthos_bridge' => $bridge], $path);
    }

    private function validEntry(string $cssa, string $patientId): array
    {
        return [
            'cssa_number' => $cssa,
            'healthos_patient_id' => $patientId,
            'validated_at' => '2026-08-20',
            'validated_by' => 'migration de données, relue par la mutuelle',
        ];
    }

    public function testAValidatedPairIsResolved(): void
    {
        $map = $this->mapWith([
            'tenant' => 'mulemacare-pilote',
            'entries' => [$this->validEntry('CSSA-4921-26', 'patient-amina')],
        ]);

        assertTrue($map->isUsable(), 'La table devrait être exploitable.');
        assertSame('patient-amina', $map->patientIdFor('CSSA-4921-26'));
        assertSame('patient-amina', $map->patientIdFor('  cssa-4921-26 '), 'La casse et les espaces ne changent pas un adhérent.');
    }

    public function testAnUnmappedNumberResolvesToNothing(): void
    {
        $map = $this->mapWith([
            'tenant' => 'mulemacare-pilote',
            'entries' => [$this->validEntry('CSSA-4921-26', 'patient-amina')],
        ]);

        assertSame(null, $map->patientIdFor('CSSA-0000-26'), 'Un numéro absent n\'a pas de correspondance.');
    }

    public function testAnUnvalidatedPairIsIgnored(): void
    {
        $map = $this->mapWith([
            'tenant' => 'mulemacare-pilote',
            'entries' => [
                $this->validEntry('CSSA-4921-26', 'patient-amina'),
                ['cssa_number' => 'CSSA-1088-26', 'healthos_patient_id' => 'patient-kofi'],
            ],
        ]);

        assertSame(null, $map->patientIdFor('CSSA-1088-26'), 'Une correspondance non relue vaut une correspondance devinée.');
        assertSame('patient-amina', $map->patientIdFor('CSSA-4921-26'), 'Les lignes validées survivent.');
        assertSame(1, count($map->problems()), 'Le rejet doit être dit, pas tu.');
    }

    public function testTwoPatientsForOneCardCancelTheWholeTable(): void
    {
        $map = $this->mapWith([
            'tenant' => 'mulemacare-pilote',
            'entries' => [
                $this->validEntry('CSSA-4921-26', 'patient-amina'),
                $this->validEntry('CSSA-4921-26', 'patient-kofi'),
                $this->validEntry('CSSA-1088-26', 'patient-ines'),
            ],
        ]);

        assertFalse($map->isUsable(), 'Une table ambiguë ne doit pas servir.');
        assertSame([], $map->pairs(), 'Aucune ligne, pas même les non ambiguës.');
        assertSame(null, $map->patientIdFor('CSSA-1088-26'));
    }

    public function testOnePatientForTwoCardsCancelsTheWholeTable(): void
    {
        $map = $this->mapWith([
            'tenant' => 'mulemacare-pilote',
            'entries' => [
                $this->validEntry('CSSA-4921-26', 'patient-amina'),
                $this->validEntry('CSSA-1088-26', 'patient-amina'),
            ],
        ]);

        assertFalse($map->isUsable());
        assertContainsString('Ambiguïté', implode("\n", $map->problems()));
    }

    public function testTheTableOfAnotherTenantIsRefused(): void
    {
        $map = $this->mapWith(
            [
                'tenant' => 'un-autre-tenant',
                'entries' => [$this->validEntry('CSSA-4921-26', 'patient-amina')],
            ],
            ['pilot_tenant' => 'mulemacare-pilote']
        );

        assertFalse($map->isUsable(), 'Une table du mauvais périmètre ne doit pas s\'appliquer.');
        assertContainsString('un-autre-tenant', implode("\n", $map->problems()));
    }

    public function testAMissingTableIsAStatedProblemNotACrash(): void
    {
        $map = new HealthOSIdentityMap(
            ['healthos_bridge' => []],
            sys_get_temp_dir() . '/mulemacare_identity_map_absente.json'
        );

        assertFalse($map->isUsable());
        assertSame([], $map->pairs());
        assertContainsString('absente ou illisible', implode("\n", $map->problems()));
    }
}
