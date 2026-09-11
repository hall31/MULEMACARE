<?php
declare(strict_types=1);

/**
 * Preuves hub APIs + claims HITL member.
 * php site/tests/test_hub_api.php
 */

$root = dirname(__DIR__);
spl_autoload_register(function (string $class) use ($root) {
    $prefix = 'App\\';
    if (!str_starts_with($class, $prefix)) {
        return;
    }
    $file = $root . '/app/' . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';
    if (is_file($file)) {
        require $file;
    }
});

use App\Services\AuthService;
use App\Services\MembershipService;
use App\Services\TotpService;

$tmp = sys_get_temp_dir() . '/mulemacare_hub_' . bin2hex(random_bytes(4));
mkdir($tmp, 0775, true);
putenv('MULEMACARE_DATA_DIR=' . $tmp);
putenv('MULEMACARE_AUTH_DEBUG=true');

$config = require $root . '/config.php';
$config['data_dir'] = $tmp;
$config['auth']['debug'] = true;
$config['mcare']['enabled'] = true;

$mem = new MembershipService($config);
$member = $mem->createMembership([
    'plan_id' => 'silver',
    'composition' => 'family',
    'currency' => 'EUR',
    'subscriber_name' => 'Hub Tester',
    'subscriber_email' => 'hub@mulemacare.example',
    'subscriber_phone' => '+33111111111',
]);
$cssa = $member['cssa_id'];
$mem->updateMemberStatus($cssa, 'ACTIVE');

// Member claim pending
$claim = $mem->createClaim([
    'cssa_id' => $cssa,
    'clinic_name' => 'Test Clinic',
    'act_type' => 'consultation',
    'amount_invoiced' => 15000,
    'status' => 'PENDING_REVIEW',
    'source' => 'member',
]);
assert(($claim['status'] ?? '') === 'PENDING_REVIEW', 'pending claim');
$list = $mem->listClaims(10, $cssa);
assert(count($list) === 1, 'scoped claims');

$approved = $mem->updateClaimStatus($claim['claim_ref'], 'APPROVED');
assert(($approved['status'] ?? '') === 'APPROVED', 'approve claim');
$m2 = $mem->getMemberByQuery($cssa);
assert(($m2['consumed_cap'] ?? 0) >= 15000, 'cap consumed on approve');

// Network flatten via HubApiController reflection-free: config clinics exist
assert(!empty($config['clinics']), 'clinics config');

// Auth still works alongside
$auth = new AuthService($config, $mem);
$seed = $auth->seedAdmin('hubops@mulemacare.example', 'Str0ng!HubPass99', 'OPS');
assert(($seed['ok'] ?? false) === true, 'seed ops');
$login = $auth->loginOpsPassword('hubops@mulemacare.example', 'Str0ng!HubPass99');
$code = TotpService::at((string) $seed['totp_secret'], (int) floor(time() / 30));
$totp = $auth->verifyOpsTotp($code, true);
assert(($totp['ok'] ?? false) === true, 'ops totp');

echo "PASS hub_api cssa={$cssa} claim={$claim['claim_ref']}\n";
array_map('unlink', glob($tmp . '/*') ?: []);
@rmdir($tmp);
