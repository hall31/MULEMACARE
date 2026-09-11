<?php
declare(strict_types=1);

/**
 * Preuve contrôleur : processStripeWebhook ACTIVE la carte.
 * php site/tests/test_api_webhook_controller.php
 */

$root = dirname(__DIR__);
$tmp = sys_get_temp_dir() . '/mulemacare_api_wh_' . bin2hex(random_bytes(4));
mkdir($tmp, 0775, true);

putenv('MULEMACARE_DATA_DIR=' . $tmp);
putenv('STRIPE_ENABLED=true');
putenv('STRIPE_SECRET_KEY=sk_test_controller_proof');
putenv('STRIPE_WEBHOOK_SECRET=whsec_controller_proof');
$_ENV['MULEMACARE_DATA_DIR'] = $tmp;
$_ENV['STRIPE_ENABLED'] = 'true';
$_ENV['STRIPE_SECRET_KEY'] = 'sk_test_controller_proof';
$_ENV['STRIPE_WEBHOOK_SECRET'] = 'whsec_controller_proof';

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

use App\Controllers\ApiController;
use App\Services\MembershipService;

$config = require $root . '/config.php';
$config['data_dir'] = $tmp;
$config['stripe']['enabled'] = true;
$config['stripe']['secret_key'] = 'sk_test_controller_proof';
$config['stripe']['webhook_secret'] = 'whsec_controller_proof';

// Bootstrap membership via service (same data dir as controller config)
$mem = new MembershipService($config);
$member = $mem->createMembership([
    'subscriber_name' => 'Controller Webhook Test',
    'subscriber_phone' => '+33611111111',
    'subscriber_email' => 'controller@mulemacare.test',
    'plan_id' => 'silver',
    'composition' => 'solo',
    'currency' => 'EUR',
    'cycle' => 'annual',
    'payment_method' => 'card',
]);
assert($member['status'] === 'PENDING_PAYMENT');
$checkoutId = 'cs_ctrl_' . bin2hex(random_bytes(4));
$mem->attachStripeCheckout($member['cssa_id'], $checkoutId);

// Rebuild controller AFTER env/config so it picks stripe enabled + data dir
$ctrl = new ApiController();

// Inject same data dir into controller's membership service via reflection
$ref = new ReflectionClass($ctrl);
$propConfig = $ref->getProperty('config');
$propConfig->setAccessible(true);
$propConfig->setValue($ctrl, $config);
$propMem = $ref->getProperty('memService');
$propMem->setAccessible(true);
$propMem->setValue($ctrl, new MembershipService($config));
$propStripe = $ref->getProperty('stripe');
$propStripe->setAccessible(true);
$propStripe->setValue($ctrl, new App\Services\StripePaymentService($config));

$payload = json_encode([
    'id' => 'evt_ctrl',
    'type' => 'checkout.session.completed',
    'data' => [
        'object' => [
            'id' => $checkoutId,
            'client_reference_id' => $member['cssa_id'],
            'metadata' => ['cssa_id' => $member['cssa_id']],
            'subscription' => 'sub_ctrl',
            'customer' => 'cus_ctrl',
            'amount_total' => 1000,
            'currency' => 'eur',
        ],
    ],
], JSON_THROW_ON_ERROR);

$ts = (string) time();
$sig = hash_hmac('sha256', $ts . '.' . $payload, 'whsec_controller_proof');
$header = 't=' . $ts . ',v1=' . $sig;

$result = $ctrl->processStripeWebhook($payload, $header);
assert($result['status'] === 200, 'status ' . $result['status']);
assert($result['body']['handled'] === true, 'not handled');
assert($result['body']['type'] === 'checkout.session.completed');

$after = (new MembershipService($config))->getMemberByQuery($member['cssa_id']);
assert($after !== null && $after['status'] === 'ACTIVE', 'member not ACTIVE');

$bad = $ctrl->processStripeWebhook($payload, 't=' . $ts . ',v1=bad');
assert($bad['status'] === 400);

array_map('unlink', glob($tmp . '/*') ?: []);
rmdir($tmp);

fwrite(STDOUT, "PASS api_webhook_controller cssa={$member['cssa_id']} handled→ACTIVE\n");
exit(0);
