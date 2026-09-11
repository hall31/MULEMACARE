<?php
declare(strict_types=1);

/**
 * Seed premier ADMIN ops.
 * Usage:
 *   MULEMACARE_DATA_DIR=./data ADMIN_EMAIL=ops@mulemacare.com ADMIN_PASSWORD='…' php site/tools/seed_admin.php
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

$email = (string) (getenv('ADMIN_EMAIL') ?: '');
$password = (string) (getenv('ADMIN_PASSWORD') ?: '');
if ($email === '' || $password === '' || strlen($password) < 12) {
    fwrite(STDERR, "Set ADMIN_EMAIL and ADMIN_PASSWORD (>=12 chars).\n");
    exit(1);
}

$config = require $root . '/config.php';
$auth = new AuthService($config);
$res = $auth->seedAdmin($email, $password, 'ADMIN');
if (!($res['ok'] ?? false)) {
    fwrite(STDERR, 'Seed failed: ' . ($res['error'] ?? 'unknown') . "\n");
    exit(1);
}

echo "ADMIN seeded: {$res['email']}\n";
echo "TOTP secret: {$res['totp_secret']}\n";
echo "otpauth: {$res['otpauth']}\n";
echo "Enroll in authenticator then login at /login/admin\n";
