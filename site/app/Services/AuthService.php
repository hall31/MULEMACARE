<?php
declare(strict_types=1);

namespace App\Services;

/**
 * Auth adhérent (OTP) + ops (Argon2id + TOTP).
 */
final class AuthService
{
    private array $config;
    private array $auth;
    private string $dataDir;
    private MembershipService $members;
    private SessionService $session;
    private AuditService $audit;

    public function __construct(array $config, ?MembershipService $members = null, ?SessionService $session = null, ?AuditService $audit = null)
    {
        $this->config = $config;
        $this->auth = $config['auth'] ?? [];
        $this->dataDir = rtrim((string) ($config['data_dir'] ?: (__DIR__ . '/../../data')), '/');
        if (!is_dir($this->dataDir)) {
            mkdir($this->dataDir, 0775, true);
        }
        $this->members = $members ?? new MembershipService($config);
        $this->session = $session ?? new SessionService($config);
        $this->audit = $audit ?? new AuditService($config);
    }

    public function session(): SessionService
    {
        return $this->session;
    }

    public function memberAuthRequired(): bool
    {
        return ($this->auth['member_required'] ?? true) === true;
    }

    public function isDebug(): bool
    {
        return ($this->auth['debug'] ?? false) === true;
    }

    /** Anti-enumeration : toujours ok. */
    public function requestAdherentOtp(string $identifier): array
    {
        $ip = (string) ($_SERVER['REMOTE_ADDR'] ?? 'cli');
        if (!$this->allowRate('adh_req:' . $ip, (int) ($this->auth['otp_max_per_hour'] ?? 5), 3600)) {
            $this->audit->record('anon', 'adh_otp_rate_limited', null, ['ip' => $ip]);
            return ['ok' => true, 'message' => 'Si un compte correspond, un code a été envoyé.', 'locked' => true];
        }

        $member = $this->members->getMemberByQuery(trim($identifier));
        $generic = ['ok' => true, 'message' => 'Si un compte correspond, un code a été envoyé.'];
        if ($member === null) {
            return $generic;
        }

        $code = (string) random_int(100000, 999999);
        $ttl = (int) ($this->auth['otp_ttl'] ?? 600);
        $challenges = $this->loadJson('auth_challenges.json');
        $id = bin2hex(random_bytes(8));
        $challenges[$id] = [
            'id' => $id,
            'cssa_id' => $member['cssa_id'],
            'email_hash' => hash('sha256', strtolower((string) ($member['subscriber_email'] ?? ''))),
            'code_hash' => password_hash($code, PASSWORD_DEFAULT),
            'expires_at' => time() + $ttl,
            'used' => false,
            'created_at' => time(),
        ];
        // purge expired
        foreach ($challenges as $k => $c) {
            if (($c['expires_at'] ?? 0) < time() || !empty($c['used'])) {
                unset($challenges[$k]);
            }
        }
        $this->saveJson('auth_challenges.json', $challenges);

        // Delivery: log hashed only; debug returns code for tests
        error_log('[MulemaCare Auth] OTP issued for cssa=' . ($member['cssa_id'] ?? '') . ' (email channel)');
        $this->audit->record('system', 'adh_otp_issued', (string) $member['cssa_id']);

        $out = $generic + ['challenge_id' => $id];
        if ($this->isDebug()) {
            $out['dev_code'] = $code;
        }
        return $out;
    }

    public function verifyAdherentOtp(string $challengeId, string $code): array
    {
        $challenges = $this->loadJson('auth_challenges.json');
        $c = $challenges[$challengeId] ?? null;
        if ($c === null || !empty($c['used']) || ($c['expires_at'] ?? 0) < time()) {
            return ['ok' => false, 'error' => 'invalid_or_expired', 'status' => 401];
        }
        if (!password_verify($code, (string) $c['code_hash'])) {
            $this->audit->record('anon', 'adh_otp_fail', $c['cssa_id'] ?? null);
            return ['ok' => false, 'error' => 'invalid_code', 'status' => 401];
        }
        $challenges[$challengeId]['used'] = true;
        $this->saveJson('auth_challenges.json', $challenges);
        $this->session->loginMember((string) $c['cssa_id']);
        $this->audit->record('member:' . $c['cssa_id'], 'adh_login', (string) $c['cssa_id']);
        return ['ok' => true, 'cssa_id' => $c['cssa_id'], 'csrf' => $this->session->csrfToken()];
    }

    public function seedAdmin(string $email, string $password, string $role = 'ADMIN'): array
    {
        $users = $this->loadJson('ops_users.json');
        $email = strtolower(trim($email));
        foreach ($users as $u) {
            if (strtolower((string) ($u['email'] ?? '')) === $email) {
                return ['ok' => false, 'error' => 'exists'];
            }
        }
        $id = 'ops_' . bin2hex(random_bytes(4));
        $secret = TotpService::generateSecret();
        $users[$id] = [
            'id' => $id,
            'email' => $email,
            'password_hash' => password_hash($password, PASSWORD_ARGON2ID),
            'role' => strtoupper($role) === 'ADMIN' ? 'ADMIN' : 'OPS',
            'totp_secret' => $secret,
            'totp_enrolled' => false,
            'failed_logins' => 0,
            'locked_until' => 0,
            'created_at' => gmdate('c'),
        ];
        $this->saveJson('ops_users.json', $users);
        $this->audit->record('cli', 'ops_seed', null, ['email' => $email, 'role' => $role]);
        return [
            'ok' => true,
            'id' => $id,
            'email' => $email,
            'totp_secret' => $secret,
            'otpauth' => TotpService::provisioningUri($secret, $email),
        ];
    }

    public function loginOpsPassword(string $email, string $password): array
    {
        $ip = (string) ($_SERVER['REMOTE_ADDR'] ?? 'cli');
        if (!$this->allowRate('ops_login:' . $ip, 20, 900)) {
            return ['ok' => false, 'error' => 'locked', 'status' => 429];
        }
        $user = $this->findOpsByEmail($email);
        if ($user === null) {
            return ['ok' => false, 'error' => 'invalid_credentials', 'status' => 401];
        }
        if (($user['locked_until'] ?? 0) > time()) {
            return ['ok' => false, 'error' => 'locked', 'status' => 429];
        }
        if (!password_verify($password, (string) $user['password_hash'])) {
            $this->bumpFail($user['id']);
            $this->audit->record('anon', 'ops_login_fail', null, ['email' => strtolower($email)]);
            return ['ok' => false, 'error' => 'invalid_credentials', 'status' => 401];
        }
        $this->clearFail($user['id']);
        $enrolled = !empty($user['totp_enrolled']);
        $this->session->loginOps($user, false);
        if (!$enrolled) {
            $this->session->setTotpPending((string) $user['totp_secret']);
            return [
                'ok' => true,
                'needs_totp_enroll' => true,
                'otpauth' => TotpService::provisioningUri((string) $user['totp_secret'], (string) $user['email']),
                'totp_secret' => $this->isDebug() ? $user['totp_secret'] : null,
                'csrf' => $this->session->csrfToken(),
            ];
        }
        return [
            'ok' => true,
            'needs_totp' => true,
            'csrf' => $this->session->csrfToken(),
        ];
    }

    public function verifyOpsTotp(string $code, bool $enroll = false): array
    {
        $this->session->start();
        $uid = (string) ($_SESSION['ops_user_id'] ?? '');
        if ($uid === '') {
            return ['ok' => false, 'error' => 'no_session', 'status' => 401];
        }
        $users = $this->loadJson('ops_users.json');
        $user = $users[$uid] ?? null;
        if ($user === null) {
            return ['ok' => false, 'error' => 'no_user', 'status' => 401];
        }
        $secret = (string) ($user['totp_secret'] ?? '');
        if (!TotpService::verify($secret, $code)) {
            $this->audit->record('ops:' . $uid, 'ops_totp_fail');
            return ['ok' => false, 'error' => 'invalid_totp', 'status' => 401];
        }
        if ($enroll || empty($user['totp_enrolled'])) {
            $users[$uid]['totp_enrolled'] = true;
            $this->saveJson('ops_users.json', $users);
        }
        $this->session->markTotpOk();
        $this->audit->record('ops:' . ($user['email'] ?? $uid), 'ops_login_ok');
        return ['ok' => true, 'role' => $user['role'], 'csrf' => $this->session->csrfToken()];
    }

    public function requireMemberOrRedirect(): bool
    {
        if (!$this->memberAuthRequired()) {
            return true;
        }
        if ($this->session->isMember()) {
            return true;
        }
        if (!headers_sent()) {
            header('Location: /login/adherent', true, 302);
        }
        return false;
    }

    public function requireOpsOrRedirect(): bool
    {
        if ($this->session->isOps()) {
            return true;
        }
        if ($this->session->needsTotp()) {
            if (!headers_sent()) {
                header('Location: /login/admin?step=totp', true, 302);
            }
            return false;
        }
        if (!headers_sent()) {
            header('Location: /login/admin', true, 302);
        }
        return false;
    }

    public function sendSecurityHeaders(): void
    {
        if (headers_sent()) {
            return;
        }
        header('X-Frame-Options: DENY');
        header('X-Content-Type-Options: nosniff');
        header('Referrer-Policy: no-referrer');
        header('Cache-Control: no-store, no-cache, must-revalidate');
        header("Content-Security-Policy: default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline' https://unpkg.com; frame-ancestors 'none'");
    }

    public static function maskEmail(?string $email): string
    {
        $email = (string) $email;
        if ($email === '' || !str_contains($email, '@')) {
            return '—';
        }
        [$u, $d] = explode('@', $email, 2);
        $u = substr($u, 0, 1) . '***';
        return $u . '@' . $d;
    }

    public static function maskPhone(?string $phone): string
    {
        $digits = preg_replace('/\D+/', '', (string) $phone) ?? '';
        if (strlen($digits) < 4) {
            return '—';
        }
        return str_repeat('*', max(0, strlen($digits) - 4)) . substr($digits, -4);
    }

    private function findOpsByEmail(string $email): ?array
    {
        $email = strtolower(trim($email));
        foreach ($this->loadJson('ops_users.json') as $u) {
            if (strtolower((string) ($u['email'] ?? '')) === $email) {
                return $u;
            }
        }
        return null;
    }

    private function bumpFail(string $id): void
    {
        $users = $this->loadJson('ops_users.json');
        if (!isset($users[$id])) {
            return;
        }
        $users[$id]['failed_logins'] = (int) ($users[$id]['failed_logins'] ?? 0) + 1;
        if ($users[$id]['failed_logins'] >= 5) {
            $users[$id]['locked_until'] = time() + 900;
            $users[$id]['failed_logins'] = 0;
        }
        $this->saveJson('ops_users.json', $users);
    }

    private function clearFail(string $id): void
    {
        $users = $this->loadJson('ops_users.json');
        if (!isset($users[$id])) {
            return;
        }
        $users[$id]['failed_logins'] = 0;
        $users[$id]['locked_until'] = 0;
        $this->saveJson('ops_users.json', $users);
    }

    private function allowRate(string $key, int $max, int $windowSec): bool
    {
        $rates = $this->loadJson('rate_limits.json');
        $now = time();
        $bucket = $rates[$key] ?? ['count' => 0, 'reset' => $now + $windowSec];
        if (($bucket['reset'] ?? 0) < $now) {
            $bucket = ['count' => 0, 'reset' => $now + $windowSec];
        }
        $bucket['count'] = (int) $bucket['count'] + 1;
        $rates[$key] = $bucket;
        $this->saveJson('rate_limits.json', $rates);
        return $bucket['count'] <= $max;
    }

    /** @return array<string,mixed> */
    private function loadJson(string $file): array
    {
        $path = $this->dataDir . '/' . $file;
        if (!is_file($path)) {
            return [];
        }
        $j = json_decode((string) file_get_contents($path), true);
        return is_array($j) ? $j : [];
    }

    /** @param array<string,mixed> $data */
    private function saveJson(string $file, array $data): void
    {
        $path = $this->dataDir . '/' . $file;
        file_put_contents($path, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE), LOCK_EX);
    }
}
