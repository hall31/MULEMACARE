<?php
declare(strict_types=1);

/**
 * CSSA (carte) ≠ formule Bronze/Silver ; NSS-MC = identité.
 * Usage: php site/tests/test_nss_identity.php
 */

$root = dirname(__DIR__);
spl_autoload_register(function (string $class) use ($root): void {
    $prefix = 'App\\';
    if (!str_starts_with($class, $prefix)) {
        return;
    }
    $file = $root . '/app/' . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';
    if (is_file($file)) {
        require $file;
    }
});

use App\Services\MembershipService;
use App\Services\NssService;

$tmp = sys_get_temp_dir() . '/mulemacare_nss_' . bin2hex(random_bytes(4));
mkdir($tmp, 0775, true);

$compact = NssService::compactNss(8, 120, 1234);
assert($compact === '81200000000123417', 'checksum must match Python NSS-MC');
assert(NssService::validateNss('NSS-8-120-00000001234-17'), 'display validates');
assert(NssService::normalizeCountry('Cameroon')['iso3n'] === 120, 'CM iso');
assert(NssService::cssaContainsFormula('CSSA-26-A7F3K2B1') === false, 'entropy cssa clean');
assert(NssService::cssaContainsFormula('CSSA-SILVER-26') === true, 'formula in cssa forbidden');

$config = require $root . '/config.php';
$config['data_dir'] = $tmp;
$mem = new MembershipService($config);
$member = $mem->createMembership([
    'plan_id' => 'silver',
    'composition' => 'family',
    'currency' => 'EUR',
    'subscriber_name' => 'Awa Diop',
    'subscriber_email' => 'awa.nss@mulemacare.example',
    'subscriber_country' => 'Sénégal',
    'payment_method' => 'card',
]);

assert(str_starts_with($member['cssa_id'], 'CSSA-' . date('y') . '-'), 'cssa year prefix');
assert(!str_contains(strtolower($member['cssa_id']), 'silver'), 'cssa is not the formula');
assert($member['plan_id'] === 'silver', 'formule stays on plan_id');
assert($member['card_kind'] === 'cssa', 'card layer');
assert($member['coverage_kind'] === 'formule', 'coverage layer');
assert($member['country_iso3n'] === '686', 'senegal iso');
assert(NssService::validateNss($member['nss_display']), 'nss valid');
assert($member['nss_id'] !== $member['cssa_id'], 'identity ≠ card');

$byNss = $mem->getMemberByQuery($member['nss_display']);
assert(($byNss['cssa_id'] ?? '') === $member['cssa_id'], 'lookup by NSS');

$byCssa = $mem->getMemberByQuery($member['cssa_id']);
assert(($byCssa['nss_id'] ?? '') === $member['nss_id'], 'lookup by CSSA');

fwrite(STDOUT, "PASS nss_identity cssa={$member['cssa_id']} nss={$member['nss_display']} plan={$member['plan_id']}\n");
