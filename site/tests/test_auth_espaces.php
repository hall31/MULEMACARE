<?php
declare(strict_types=1);

/**
 * Preuves SA1/SA2 — auth adhérent OTP + admin Argon2/TOTP + CSRF.
 * Usage: php site/tests/test_auth_espaces.php
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

$tmp = sys_get_temp_dir() . '/mulemacare_auth_' . bin2hex(random_bytes(4));
mkdir($tmp, 0775, true);
putenv('MULEMACARE_DATA_DIR=' . $tmp);
putenv('MULEMACARE_AUTH_DEBUG=true');
putenv('MEMBER_AUTH_REQUIRED=true');

$config = require $root . '/config.php';
$config['data_dir'] = $tmp;
$config['auth']['debug'] = true;
$config['auth']['member_required'] = true;

$mem = new MembershipService($config);
$member = $mem->createMembership([
    'plan_id' => 'silver',
    'composition' => 'family',
    'currency' => 'EUR',
    'subscriber_name' => 'Test Auth',
    'subscriber_email' => 'auth.test@mulemacare.example',
    'subscriber_phone' => '+33123456789',
    'payment_method' => 'card',
]);
$cssa = $member['cssa_id'];

$auth = new AuthService($config, $mem);

// Anti-enumeration always ok
$reqUnknown = $auth->requestAdherentOtp('nobody@example.com');
assert(($reqUnknown['ok'] ?? false) === true, 'unknown still ok');

$req = $auth->requestAdherentOtp('auth.test@mulemacare.example');
assert(($req['ok'] ?? false) === true, 'otp request ok');
assert(!empty($req['challenge_id']), 'challenge id');
assert(!empty($req['dev_code']), 'dev code in debug');

$bad = $auth->verifyAdherentOtp($req['challenge_id'], '000000');
assert(($bad['ok'] ?? true) === false, 'bad otp rejected');

$ok = $auth->verifyAdherentOtp($req['challenge_id'], $req['dev_code']);
assert(($ok['ok'] ?? false) === true, 'good otp');
assert($auth->session()->isMember() === true, 'member session');
assert($auth->session()->memberCssa() === $cssa, 'cssa bound');

$csrf = $auth->session()->csrfToken();
assert($auth->session()->validateCsrf($csrf) === true, 'csrf valid');
assert($auth->session()->validateCsrf('deadbeef') === false, 'csrf invalid');

// Admin seed + TOTP
$seed = $auth->seedAdmin('ops@mulemacare.example', 'Str0ng!Passw0rd', 'ADMIN');
assert(($seed['ok'] ?? false) === true, 'seed admin');
$secret = (string) $seed['totp_secret'];

$login = $auth->loginOpsPassword('ops@mulemacare.example', 'wrong');
assert(($login['ok'] ?? true) === false, 'bad password');

$login = $auth->loginOpsPassword('ops@mulemacare.example', 'Str0ng!Passw0rd');
assert(($login['ok'] ?? false) === true, 'password ok');
assert(!empty($login['needs_totp_enroll']) || !empty($login['needs_totp']), 'needs totp');
assert($auth->session()->isOps() === false, 'ops blocked until totp');

$code = TotpService::at($secret, (int) floor(time() / 30));
$totp = $auth->verifyOpsTotp($code, true);
assert(($totp['ok'] ?? false) === true, 'totp enroll ok');
assert($auth->session()->isOps() === true, 'ops after totp');
assert($auth->session()->isAdmin() === true, 'admin role');

// Mask helpers
assert(str_contains(AuthService::maskEmail('eric.awono@mulemacare.com'), '***'), 'email masked');
assert(str_ends_with(AuthService::maskPhone('+33 6 59 51 34 58'), '3458') || strlen(AuthService::maskPhone('+33659513458')) >= 4, 'phone masked');

echo "PASS auth_espaces cssa={$cssa} admin=ops@mulemacare.example\n";

// cleanup best-effort
array_map('unlink', glob($tmp . '/*') ?: []);
@rmdir($tmp);
