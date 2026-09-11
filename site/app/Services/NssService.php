<?php
declare(strict_types=1);

namespace App\Services;

/**
 * NSS-MC (identité à vie) et CSSA (carte / police).
 * La formule Bronze/Silver/Gold/Platinium n'entre jamais dans ces numéros.
 */
final class NssService
{
    public const SCHEME = 8;
    public const SERIAL_DIGITS = 11;

    /** @var array<string, array{iso2:string,iso3n:int,label:string}> */
    private const COUNTRIES = [
        'CM' => ['iso2' => 'CM', 'iso3n' => 120, 'label' => 'Cameroun'],
        'SN' => ['iso2' => 'SN', 'iso3n' => 686, 'label' => 'Sénégal'],
        'CI' => ['iso2' => 'CI', 'iso3n' => 384, 'label' => "Côte d'Ivoire"],
        'CG' => ['iso2' => 'CG', 'iso3n' => 178, 'label' => 'Congo-Brazzaville'],
        'CD' => ['iso2' => 'CD', 'iso3n' => 180, 'label' => 'RDC'],
        'MG' => ['iso2' => 'MG', 'iso3n' => 450, 'label' => 'Madagascar'],
        'BJ' => ['iso2' => 'BJ', 'iso3n' => 204, 'label' => 'Bénin'],
        'GA' => ['iso2' => 'GA', 'iso3n' => 266, 'label' => 'Gabon'],
        'TG' => ['iso2' => 'TG', 'iso3n' => 768, 'label' => 'Togo'],
        'HT' => ['iso2' => 'HT', 'iso3n' => 332, 'label' => 'Haïti'],
        'FR' => ['iso2' => 'FR', 'iso3n' => 250, 'label' => 'France'],
        'BE' => ['iso2' => 'BE', 'iso3n' => 56, 'label' => 'Belgique'],
        'CA' => ['iso2' => 'CA', 'iso3n' => 124, 'label' => 'Canada'],
        'US' => ['iso2' => 'US', 'iso3n' => 840, 'label' => 'États-Unis'],
        'GB' => ['iso2' => 'GB', 'iso3n' => 826, 'label' => 'Royaume-Uni'],
        'XX' => ['iso2' => 'XX', 'iso3n' => 999, 'label' => 'Non classé'],
    ];

    /** @var array<string, string> */
    private const ALIASES = [
        'cameroun' => 'CM', 'cameroon' => 'CM', 'cam' => 'CM', 'ca' => 'CM',
        'senegal' => 'SN', 'sene' => 'SN', 'sen' => 'SN', 'se' => 'SN',
        'cote d ivoire' => 'CI', 'cote' => 'CI', 'ivory coast' => 'CI', 'ci' => 'CI',
        'congo brazzaville' => 'CG', 'congo' => 'CG',
        'rdc' => 'CD', 'republique democratique du congo' => 'CD', 'congo kinshasa' => 'CD',
        'madagascar' => 'MG', 'mada' => 'MG',
        'benin' => 'BJ', 'gabon' => 'GA', 'togo' => 'TG',
        'haiti' => 'HT',
        'france' => 'FR', 'fr' => 'FR', 'fra' => 'FR',
        'belgique' => 'BE', 'belgium' => 'BE', 'bel' => 'BE',
        'canada' => 'CA', 'united states' => 'US', 'usa' => 'US',
        'united kingdom' => 'GB',
    ];

    private string $seqPath;

    public function __construct(array $config)
    {
        $dir = rtrim((string) ($config['data_dir'] ?? (__DIR__ . '/../../data')), '/');
        if (!is_dir($dir)) {
            mkdir($dir, 0775, true);
        }
        $this->seqPath = $dir . '/nss_seq.json';
    }

    /** Carte digitale — police de l'année. Jamais de formule dans l'ID. */
    public static function issueCssaCard(): string
    {
        return 'CSSA-' . date('y') . '-' . strtoupper(bin2hex(random_bytes(4)));
    }

    public static function cssaContainsFormula(string $cssa): bool
    {
        $blob = strtolower($cssa);
        foreach (['bronze', 'silver', 'gold', 'platinium', 'platinum', 'formule'] as $needle) {
            if (str_contains($blob, $needle)) {
                return true;
            }
        }
        return false;
    }

    /** @return array{iso2:string,iso3n:int,iso3n_pad:string,label:string} */
    public static function normalizeCountry(string $raw): array
    {
        $key = self::fold($raw);
        $iso2 = 'XX';
        if ($key !== '' && isset(self::ALIASES[$key])) {
            $iso2 = self::ALIASES[$key];
        } elseif ($key !== '') {
            foreach (self::ALIASES as $alias => $code) {
                if (strlen($alias) < 4) {
                    continue;
                }
                if (str_contains($key, $alias) || str_contains($alias, $key)) {
                    $iso2 = $code;
                    break;
                }
            }
        }
        $c = self::COUNTRIES[$iso2] ?? self::COUNTRIES['XX'];
        return [
            'iso2' => $c['iso2'],
            'iso3n' => $c['iso3n'],
            'iso3n_pad' => sprintf('%03d', $c['iso3n']),
            'label' => $c['label'],
        ];
    }

    /** @return array{compact:string,display:string,iso3n:int,serial:int} */
    public function allocateNss(int $iso3n): array
    {
        $iso3n = max(0, min(999, $iso3n));
        $serial = $this->nextSerial($iso3n);
        $compact = self::compactNss(self::SCHEME, $iso3n, $serial);
        return [
            'compact' => $compact,
            'display' => self::displayNss($compact),
            'iso3n' => $iso3n,
            'serial' => $serial,
        ];
    }

    public static function compactNss(int $scheme, int $iso3n, int $serial): string
    {
        $payload = sprintf('%d%03d%011d', $scheme, $iso3n, $serial);
        return $payload . self::mod97($payload);
    }

    public static function displayNss(string $compact): string
    {
        $digits = preg_replace('/\D/', '', $compact) ?? '';
        if (strlen($digits) !== 17) {
            return $compact;
        }
        return 'NSS-' . $digits[0] . '-' . substr($digits, 1, 3) . '-' . substr($digits, 4, 11) . '-' . substr($digits, 15, 2);
    }

    public static function validateNss(string $value): bool
    {
        $digits = preg_replace('/\D/', '', $value) ?? '';
        if (strlen($digits) !== 17 || $digits[0] !== (string) self::SCHEME) {
            return false;
        }
        return self::mod97(substr($digits, 0, 15)) === substr($digits, 15, 2);
    }

    public static function mod97(string $payload): string
    {
        $n = $payload . '00';
        $remainder = 0;
        $len = strlen($n);
        for ($i = 0; $i < $len; $i++) {
            $remainder = ($remainder * 10 + (int) $n[$i]) % 97;
        }
        return sprintf('%02d', 98 - $remainder);
    }

    private function nextSerial(int $iso3n): int
    {
        $key = sprintf('%03d', $iso3n);
        $lock = fopen($this->seqPath . '.lock', 'c+');
        if ($lock === false) {
            throw new \RuntimeException('NSS sequence lock failed');
        }
        flock($lock, LOCK_EX);
        $data = [];
        if (is_file($this->seqPath)) {
            $decoded = json_decode((string) file_get_contents($this->seqPath), true);
            if (is_array($decoded)) {
                $data = $decoded;
            }
        }
        $current = (int) ($data[$key] ?? 0);
        $next = $current + 1;
        $data[$key] = $next;
        file_put_contents($this->seqPath, json_encode($data, JSON_PRETTY_PRINT), LOCK_EX);
        flock($lock, LOCK_UN);
        fclose($lock);
        return $next;
    }

    private static function fold(string $value): string
    {
        $ascii = @iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $value);
        $text = strtolower((string) ($ascii !== false ? $ascii : $value));
        $text = str_replace(["'", '`', '"', '^', '~'], '', $text);
        return trim((string) preg_replace('/[^a-z0-9]+/', ' ', $text));
    }
}
