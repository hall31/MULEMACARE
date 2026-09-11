<?php
declare(strict_types=1);

/**
 * WhatsApp / Qonto : client enregistré PENDING → confirm HITL → ACTIVE
 * Usage: php site/tests/test_whatsapp_payment_hitl.php
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
use App\Services\TariffCatalog;
use App\Services\QuoteService;

$tmp = sys_get_temp_dir() . '/mulemacare_wa_test_' . bin2hex(random_bytes(4));
mkdir($tmp, 0775, true);
mkdir($tmp . '/tariffs', 0775, true);

$config = require $root . '/config.php';
$config['data_dir'] = $tmp;
$config['qonto']['iban'] = 'FR7612345678901234567890123';
$config['qonto']['bic'] = 'QNTOFRP1XXX';

// Copie catalogue pour data_dir isolé
$src = $root . '/data/tariffs/v2026-08-30.json';
if (is_file($src)) {
    copy($src, $tmp . '/tariffs/v2026-08-30.json');
    file_put_contents($tmp . '/tariffs/active.json', json_encode(['active_version' => '2026-08-30']));
}

$catalog = new TariffCatalog($config);
assert($catalog->version() !== '', 'tariff version');

$quote = new QuoteService($config);
$q = $quote->calculateIndividualQuote('silver', 'family', 'XAF', 'annual');
assert(($q['tariff_version'] ?? '') !== '', 'quote has tariff_version');
assert((float) $q['annual_amount'] > 0, 'annual amount');

$mem = new MembershipService($config);

// WhatsApp — enregistre client
$wa = $mem->createMembership([
    'subscriber_name' => 'Awa WhatsApp',
    'subscriber_phone' => '+237600000001',
    'subscriber_email' => 'awa.wa@mulemacare.test',
    'plan_id' => 'silver',
    'composition' => 'solo',
    'currency' => 'XAF',
    'cycle' => 'annual',
    'payment_method' => 'whatsapp',
    'city' => 'douala',
    'subscriber_country' => 'Cameroun',
]);

assert($wa['status'] === 'PENDING_PAYMENT', 'WA pending');
assert(($wa['client_registered'] ?? false) === true, 'client_registered');
assert(str_contains((string) $wa['whatsapp_url'], 'wa.me'), 'wa url');
assert(str_contains((string) $wa['whatsapp_url'], rawurlencode($wa['cssa_id'])) || str_contains(urldecode($wa['whatsapp_url']), $wa['cssa_id']), 'cssa in wa');
assert(($wa['tariff_version'] ?? '') !== '', 'membership tariff_version');
assert(!empty($wa['momo_ussd']['orange']) || !empty($wa['momo_ussd']['mtn']), 'ussd present');

$pending = $mem->listPendingPayments(10);
assert(count($pending) >= 1, 'pending list');

$activated = $mem->activateFromManualPayment([
    'cssa_id' => $wa['cssa_id'],
    'channel' => 'whatsapp',
    'payment_ref' => 'MOMO-TEST-1',
    'amount_received' => (float) $wa['amount_due'],
    'actor' => 'ops:test',
]);
assert($activated !== null && $activated['status'] === 'ACTIVE', 'WA → ACTIVE');

// Idempotent
$again = $mem->activateFromManualPayment(['cssa_id' => $wa['cssa_id'], 'channel' => 'whatsapp']);
assert($again !== null && $again['status'] === 'ACTIVE', 'idempotent ACTIVE');

// Qonto
$qo = $mem->createMembership([
    'subscriber_name' => 'Jean Qonto',
    'subscriber_phone' => '+33600000002',
    'subscriber_email' => 'jean.qonto@mulemacare.test',
    'plan_id' => 'gold',
    'composition' => 'couple',
    'currency' => 'EUR',
    'cycle' => 'annual',
    'payment_method' => 'qonto',
    'subscriber_country' => 'France',
]);
assert($qo['status'] === 'PENDING_PAYMENT', 'qonto pending');
assert(($qo['qonto']['reference'] ?? '') === $qo['cssa_id'], 'qonto ref = cssa');
assert(str_contains((string) ($qo['qonto']['iban_masked'] ?? ''), 'FR76'), 'iban masked');

$actQ = $mem->activateFromManualPayment([
    'cssa_id' => $qo['cssa_id'],
    'channel' => 'qonto',
    'payment_ref' => 'VIR-QONTO-1',
    'actor' => 'ops:test',
]);
assert($actQ !== null && $actQ['status'] === 'ACTIVE', 'qonto → ACTIVE');

// Normalize methods
assert($mem->normalizePaymentMethod('card') === 'stripe');
assert($mem->normalizePaymentMethod('wa') === 'whatsapp');
assert($mem->normalizePaymentMethod('virement') === 'qonto');

echo "OK test_whatsapp_payment_hitl\n";
exit(0);
