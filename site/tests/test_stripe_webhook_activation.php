<?php
declare(strict_types=1);

/**
 * Preuve goal : membership PENDING_PAYMENT → ACTIVE via événement Stripe signé.
 * Usage: php site/tests/test_stripe_webhook_activation.php
 * Exit 0 = OK
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
use App\Services\StripePaymentService;

$tmp = sys_get_temp_dir() . '/mulemacare_stripe_test_' . bin2hex(random_bytes(4));
mkdir($tmp, 0775, true);

$config = require $root . '/config.php';
$config['data_dir'] = $tmp;
$config['stripe']['enabled'] = true;
$config['stripe']['secret_key'] = 'sk_test_dummy_for_signature_only';
$config['stripe']['webhook_secret'] = 'whsec_test_goal_secret';

$mem = new MembershipService($config);
$stripe = new StripePaymentService($config);

$member = $mem->createMembership([
    'subscriber_name' => 'Test Diaspora Goal',
    'subscriber_phone' => '+33600000000',
    'subscriber_email' => 'goal-test@mulemacare.test',
    'plan_id' => 'silver',
    'composition' => 'family',
    'currency' => 'EUR',
    'cycle' => 'annual',
    'payment_method' => 'card',
    'subscriber_origin' => 'Diaspora',
]);

assert($member['status'] === 'PENDING_PAYMENT', 'expected PENDING_PAYMENT, got ' . $member['status']);
assert(($member['payment_status'] ?? '') === 'unpaid', 'expected unpaid');

$checkoutId = 'cs_test_' . bin2hex(random_bytes(6));
$mem->attachStripeCheckout($member['cssa_id'], $checkoutId);

$payload = json_encode([
    'id' => 'evt_test_goal',
    'type' => 'checkout.session.completed',
    'data' => [
        'object' => [
            'id' => $checkoutId,
            'client_reference_id' => $member['cssa_id'],
            'metadata' => ['cssa_id' => $member['cssa_id']],
            'subscription' => 'sub_test_goal',
            'customer' => 'cus_test_goal',
            'amount_total' => (int) round(((float) $member['amount']) * 100),
            'currency' => 'eur',
        ],
    ],
], JSON_THROW_ON_ERROR);

$ts = (string) time();
$sig = hash_hmac('sha256', $ts . '.' . $payload, 'whsec_test_goal_secret');
$header = 't=' . $ts . ',v1=' . $sig;

$event = $stripe->constructEvent($payload, $header);
assert($event['type'] === 'checkout.session.completed');

$object = $event['data']['object'];
$activated = $mem->activateFromStripePayment([
    'cssa_id' => (string) ($object['metadata']['cssa_id'] ?? ''),
    'checkout_session_id' => (string) ($object['id'] ?? ''),
    'subscription_id' => (string) ($object['subscription'] ?? ''),
    'customer_id' => (string) ($object['customer'] ?? ''),
]);

assert($activated !== null, 'activation returned null');
assert($activated['status'] === 'ACTIVE', 'expected ACTIVE, got ' . $activated['status']);
assert(($activated['payment_status'] ?? '') === 'paid', 'expected paid');
assert(($activated['stripe_subscription_id'] ?? '') === 'sub_test_goal');

$card = $mem->verifyCard($member['cssa_id']);
assert(($card['status'] ?? '') === 'ACTIVE', 'verifyCard should be ACTIVE after pay');

// Signature invalide doit échouer
$threw = false;
try {
    $stripe->constructEvent($payload, 't=' . $ts . ',v1=deadbeef');
} catch (Throwable $e) {
    $threw = true;
}
assert($threw, 'bad signature must throw');

// Cleanup
array_map('unlink', glob($tmp . '/*') ?: []);
rmdir($tmp);

fwrite(STDOUT, "PASS stripe_webhook_activation cssa={$member['cssa_id']} PENDING→ACTIVE\n");
exit(0);
