<?php
declare(strict_types=1);

namespace App\Services;

/**
 * Table de correspondance validée entre un numéro CSSA et un `patient_id` HealthOS.
 *
 * `docs/HEALTHOS_BRIDGE.md` l'exige et interdit de deviner l'identifiant
 * HealthOS depuis une carte ou une adresse email. Cette classe est ce qui rend
 * l'interdiction opposable : elle n'expose aucune recherche approximative,
 * aucune dérivation, aucun repli. Un numéro absent de la table n'a pas de
 * correspondance, et le bridge ne l'appelle pas.
 *
 * La table est un fichier produit par la migration de données et relu par un
 * humain. Chaque ligne porte la date et l'auteur de sa validation ; une ligne
 * sans validation est ignorée, parce qu'une correspondance non relue vaut une
 * correspondance devinée.
 *
 * Une ambiguïté annule la table entière. C'est volontairement brutal : deux
 * lignes qui donnent deux `patient_id` au même numéro CSSA, ou le même
 * `patient_id` à deux numéros, ouvrent la porte au fait de montrer les droits
 * de santé de quelqu'un d'autre. Une table refusée arrête le rapprochement ;
 * une table ambiguë le fait mentir.
 */
final class HealthOSIdentityMap
{
    /** @var array<string,string> numéro CSSA => patient_id HealthOS */
    private array $pairs = [];

    /** @var list<string> */
    private array $problems = [];

    private bool $usable = false;

    private string $tenant = '';

    public function __construct(private array $config, ?string $path = null)
    {
        $this->load($path ?? $this->defaultPath());
    }

    private function defaultPath(): string
    {
        $configured = (string) (($this->config['healthos_bridge']['identity_map_path'] ?? '') ?: '');
        return $configured !== '' ? $configured : __DIR__ . '/../../data/healthos_identity_map.json';
    }

    /** La table est-elle exploitable — présente, lisible, sans ambiguïté ? */
    public function isUsable(): bool
    {
        return $this->usable;
    }

    /** Le tenant pilote déclaré par la table. */
    public function tenant(): string
    {
        return $this->tenant;
    }

    /** @return list<string> Ce qui a été refusé, et pourquoi. */
    public function problems(): array
    {
        return $this->problems;
    }

    /** @return array<string,string> numéro CSSA => patient_id HealthOS */
    public function pairs(): array
    {
        return $this->usable ? $this->pairs : [];
    }

    /**
     * L'identifiant HealthOS d'un numéro CSSA, ou `null`.
     *
     * `null` n'est pas une erreur : c'est le cas normal d'un adhérent qui n'a
     * pas encore été rapproché. L'appelant ne doit rien en déduire et surtout
     * pas fabriquer un identifiant.
     */
    public function patientIdFor(string $cssaNumber): ?string
    {
        if (!$this->usable) {
            return null;
        }
        $key = strtoupper(trim($cssaNumber));
        return $this->pairs[$key] ?? null;
    }

    private function load(string $path): void
    {
        if (!is_file($path) || !is_readable($path)) {
            $this->problems[] = 'Table de correspondance absente ou illisible : ' . $path;
            return;
        }

        $decoded = json_decode((string) file_get_contents($path), true);
        if (!is_array($decoded)) {
            $this->problems[] = 'Table de correspondance illisible : JSON invalide.';
            return;
        }

        $this->tenant = trim((string) ($decoded['tenant'] ?? ''));
        if ($this->tenant === '') {
            $this->problems[] = 'Table de correspondance sans tenant pilote déclaré.';
            return;
        }

        $expectedTenant = trim((string) ($this->config['healthos_bridge']['pilot_tenant'] ?? ''));
        if ($expectedTenant !== '' && $expectedTenant !== $this->tenant) {
            $this->problems[] = sprintf(
                'Table de correspondance du tenant « %s » alors que le pilote configuré est « %s ».',
                $this->tenant,
                $expectedTenant
            );
            return;
        }

        $entries = $decoded['entries'] ?? null;
        if (!is_array($entries)) {
            $this->problems[] = 'Table de correspondance sans liste `entries`.';
            return;
        }

        $seenPatients = [];
        foreach ($entries as $index => $entry) {
            if (!is_array($entry)) {
                $this->problems[] = sprintf('Entrée %s : format inattendu.', (string) $index);
                continue;
            }
            $cssa = strtoupper(trim((string) ($entry['cssa_number'] ?? '')));
            $patientId = trim((string) ($entry['healthos_patient_id'] ?? ''));
            $validatedAt = trim((string) ($entry['validated_at'] ?? ''));
            $validatedBy = trim((string) ($entry['validated_by'] ?? ''));

            if ($cssa === '' || $patientId === '') {
                $this->problems[] = sprintf('Entrée %s : numéro CSSA ou patient_id vide.', (string) $index);
                continue;
            }
            if ($validatedAt === '' || $validatedBy === '') {
                $this->problems[] = sprintf('Entrée %s (%s) : correspondance non validée, ignorée.', (string) $index, $cssa);
                continue;
            }
            if (isset($this->pairs[$cssa]) && $this->pairs[$cssa] !== $patientId) {
                $this->problems[] = sprintf('Ambiguïté : %s renvoie vers deux patients HealthOS.', $cssa);
                $this->pairs = [];
                return;
            }
            if (isset($seenPatients[$patientId]) && $seenPatients[$patientId] !== $cssa) {
                $this->problems[] = sprintf('Ambiguïté : le patient HealthOS %s est rapproché de deux numéros CSSA.', $patientId);
                $this->pairs = [];
                return;
            }

            $this->pairs[$cssa] = $patientId;
            $seenPatients[$patientId] = $cssa;
        }

        if ($this->pairs === []) {
            $this->problems[] = 'Table de correspondance sans aucune ligne validée.';
            return;
        }

        $this->usable = true;
    }
}
