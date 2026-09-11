<?php
declare(strict_types=1);

/**
 * Zero-friction express: quote + adhere + corporate
 * Usage: php site/tests/test_express_zero_friction.php
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

use App\Services\QuoteService;
use App\Services\MembershipService;

$tmp = sys_get_temp_dir() . '/mulemacare_zf_' . bin2hex(random_bytes(4));
mkdir($tmp . '/tariffs', 0775, true);
$config = require $root . '/config.php';
$config['data_dir'] = $tmp;
$src = $root . '/data/tariffs/v2026-08-30.json';
if (is_file($src)) {
    copy($src, $tmp . '/tariffs/v2026-08-30.json');
    file_put_contents($tmp . '/tariffs/active.json', json_encode(['active_version' => '2026-08-30']));
}

$qs = new QuoteService($config);
assert($qs->normalizeComposition('famille') === 'family');
assert($qs->normalizeComposition('solo') === 'solo');

$q = $qs->createQuote([
    'type' => 'individual',
    'prospect_name' => 'ZF User',
    'prospect_phone' => '+33611111111',
    'plan_id' => 'silver',
    'composition' => 'famille',
    'currency' => 'EUR',
]);
assert(($q['composition'] ?? '') === 'family', 'comp normalized');
assert(str_contains($q['subscribe_url'], 'express=1'), 'express url');
assert(str_contains($q['whatsapp_url'], 'wa.me'), 'wa on quote');

$mem = new MembershipService($config);
$corp = $mem->createCorporateContract([
    'company_name' => 'Startup Test SAS',
    'name' => 'DRH Test',
    'phone' => '+237600000099',
    'email' => 'drh@test.cm',
    'employee_count' => 25,
    'plan_tier' => 'silver',
    'city' => 'douala',
    'payment_method' => 'whatsapp',
]);
assert(($corp['client_registered'] ?? false) === true);
assert($corp['status'] === 'PENDING_PAYMENT');
assert(str_starts_with($corp['contract_id'], 'ENT-'));
assert(!empty($corp['quote_number']));
assert(str_contains($corp['whatsapp_url'], 'wa.me'));

$list = $mem->listCorporateContracts(5);
assert(count($list) >= 1);

$qc = $qs->createQuote([
    'type' => 'corporate',
    'company_name' => 'Autre SA',
    'prospect_name' => 'Boss',
    'prospect_phone' => '+237611',
    'employee_count' => 12,
    'plan_tier' => 'gold',
]);
assert(($qc['type'] ?? '') === 'corporate');
assert(str_contains($qc['subscribe_url'], '/entreprises'), 'corp subscribe');

echo "OK test_express_zero_friction\n";
exit(0);
