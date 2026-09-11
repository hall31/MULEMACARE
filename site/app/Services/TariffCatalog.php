<?php
declare(strict_types=1);

namespace App\Services;

/**
 * Catalogue tarifaire versionné (JSON) avec fallback config.php.
 */
final class TariffCatalog
{
    private array $config;
    private array $catalog;
    private string $version;

    public function __construct(array $config)
    {
        $this->config = $config;
        [$this->catalog, $this->version] = $this->load();
    }

    public function version(): string
    {
        return $this->version;
    }

    public function annualDiscountPct(): float
    {
        $pct = $this->catalog['annual_discount_pct']
            ?? ($this->config['tariffs']['annual_discount_pct'] ?? 10);
        return max(0.0, min(50.0, (float) $pct));
    }

    /** @return array<string,mixed> */
    public function plans(): array
    {
        $plans = $this->catalog['plans'] ?? null;
        if (is_array($plans) && $plans !== []) {
            return $plans;
        }
        return is_array($this->config['plans'] ?? null) ? $this->config['plans'] : [];
    }

    /** @return array<string,mixed> */
    public function plan(string $planId): array
    {
        $plans = $this->plans();
        return $plans[$planId] ?? $plans['silver'] ?? [];
    }

    /** @return array{0:array,1:string} */
    private function load(): array
    {
        $dataDir = rtrim((string) ($this->config['data_dir'] ?? (__DIR__ . '/../../data')), '/');
        $tariffDir = $dataDir . '/tariffs';
        $activeVersion = (string) (
            getenv('TARIFF_ACTIVE_VERSION')
            ?: ($this->config['tariffs']['active_version'] ?? '')
        );

        if ($activeVersion === '' && is_file($tariffDir . '/active.json')) {
            $meta = json_decode((string) file_get_contents($tariffDir . '/active.json'), true);
            if (is_array($meta) && !empty($meta['active_version'])) {
                $activeVersion = (string) $meta['active_version'];
            }
        }
        if ($activeVersion === '') {
            $activeVersion = '2026-08-30';
        }

        $path = $tariffDir . '/v' . $activeVersion . '.json';
        if (is_file($path)) {
            $decoded = json_decode((string) file_get_contents($path), true);
            if (is_array($decoded) && !empty($decoded['plans'])) {
                return [$decoded, (string) ($decoded['version'] ?? $activeVersion)];
            }
        }

        return [
            [
                'version' => $activeVersion,
                'annual_discount_pct' => (float) ($this->config['tariffs']['annual_discount_pct'] ?? 10),
                'plans' => $this->config['plans'] ?? [],
            ],
            $activeVersion,
        ];
    }
}
