<?php
declare(strict_types=1);

namespace App\Services;

/**
 * Sessions PHP sécurisées + CSRF synchronizer + timeouts.
 */
final class SessionService
{
    private array $auth;
    private bool $started = false;

    public function __construct(array $config)
    {
        $this->auth = $config['auth'] ?? [];
    }

    public function start(): void
    {
        if ($this->started || session_status() === PHP_SESSION_ACTIVE) {
            $this->started = true;
            $this->enforceTimeouts();
            return;
        }
        $secure = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
            || ((string) ($_SERVER['SERVER_PORT'] ?? '') === '443');
        session_name((string) ($this->auth['session_name'] ?? 'mulemacare_sess'));
        session_set_cookie_params([
            'lifetime' => 0,
            'path' => '/',
            'secure' => $secure,
            'httponly' => true,
            'samesite' => 'Lax',
        ]);
        session_start();
        $this->started = true;
        if (empty($_SESSION['_csrf'])) {
            $_SESSION['_csrf'] = bin2hex(random_bytes(32));
        }
        if (empty($_SESSION['_started_at'])) {
            $_SESSION['_started_at'] = time();
        }
        $_SESSION['_last_seen'] = $_SESSION['_last_seen'] ?? time();
        $this->enforceTimeouts();
    }

    public function enforceTimeouts(): void
    {
        $idle = (int) ($this->auth['idle_timeout'] ?? 1800);
        $abs = (int) ($this->auth['absolute_timeout'] ?? 28800);
        $now = time();
        $last = (int) ($_SESSION['_last_seen'] ?? $now);
        $started = (int) ($_SESSION['_started_at'] ?? $now);
        if (($now - $last) > $idle || ($now - $started) > $abs) {
            $this->logout();
            return;
        }
        $_SESSION['_last_seen'] = $now;
    }

    public function csrfToken(): string
    {
        $this->start();
        return (string) ($_SESSION['_csrf'] ?? '');
    }

    public function validateCsrf(?string $token): bool
    {
        $this->start();
        $expected = (string) ($_SESSION['_csrf'] ?? '');
        return $expected !== '' && is_string($token) && hash_equals($expected, $token);
    }

    public function loginMember(string $cssaId): void
    {
        $this->start();
        session_regenerate_id(true);
        $_SESSION['role'] = 'MEMBER';
        $_SESSION['cssa_id'] = strtoupper(trim($cssaId));
        $_SESSION['_started_at'] = time();
        $_SESSION['_last_seen'] = time();
        unset($_SESSION['ops_user_id'], $_SESSION['ops_role'], $_SESSION['totp_pending']);
    }

    public function loginOps(array $user, bool $totpOk): void
    {
        $this->start();
        session_regenerate_id(true);
        $_SESSION['ops_user_id'] = (string) ($user['id'] ?? '');
        $_SESSION['ops_email'] = (string) ($user['email'] ?? '');
        $_SESSION['ops_role'] = strtoupper((string) ($user['role'] ?? 'OPS'));
        $_SESSION['role'] = $_SESSION['ops_role'];
        $_SESSION['totp_ok'] = $totpOk;
        $_SESSION['_started_at'] = time();
        $_SESSION['_last_seen'] = time();
        unset($_SESSION['cssa_id']);
    }

    public function markTotpOk(): void
    {
        $this->start();
        $_SESSION['totp_ok'] = true;
        unset($_SESSION['totp_pending']);
    }

    public function setTotpPending(string $secret): void
    {
        $this->start();
        $_SESSION['totp_pending'] = $secret;
        $_SESSION['totp_ok'] = false;
    }

    public function logout(): void
    {
        $this->start();
        $_SESSION = [];
        if (ini_get('session.use_cookies')) {
            $p = session_get_cookie_params();
            setcookie(session_name(), '', time() - 42000, $p['path'], $p['domain'] ?? '', (bool) $p['secure'], (bool) $p['httponly']);
        }
        session_destroy();
        $this->started = false;
    }

    public function isMember(): bool
    {
        $this->start();
        return ($_SESSION['role'] ?? '') === 'MEMBER' && !empty($_SESSION['cssa_id']);
    }

    public function memberCssa(): ?string
    {
        return $this->isMember() ? (string) $_SESSION['cssa_id'] : null;
    }

    public function isOps(): bool
    {
        $this->start();
        $role = (string) ($_SESSION['ops_role'] ?? '');
        return in_array($role, ['OPS', 'ADMIN'], true) && !empty($_SESSION['totp_ok']);
    }

    public function isAdmin(): bool
    {
        $this->start();
        return ($_SESSION['ops_role'] ?? '') === 'ADMIN' && !empty($_SESSION['totp_ok']);
    }

    public function opsEmail(): ?string
    {
        $this->start();
        return isset($_SESSION['ops_email']) ? (string) $_SESSION['ops_email'] : null;
    }

    public function needsTotp(): bool
    {
        $this->start();
        return !empty($_SESSION['ops_user_id']) && empty($_SESSION['totp_ok']);
    }

    /** @return array{role?:string,cssa_id?:string,ops_email?:string} */
    public function snapshot(): array
    {
        $this->start();
        return [
            'role' => (string) ($_SESSION['role'] ?? ''),
            'cssa_id' => (string) ($_SESSION['cssa_id'] ?? ''),
            'ops_email' => (string) ($_SESSION['ops_email'] ?? ''),
            'totp_ok' => !empty($_SESSION['totp_ok']),
        ];
    }
}
