<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Services\AuthService;
use App\Services\AuditService;
use App\Services\MembershipService;
use App\Services\MutuelleOsClient;
use App\Services\SessionService;

/**
 * Auth adhérent / admin + logout.
 */
class AuthController
{
    private array $config;
    private AuthService $auth;
    private SessionService $session;

    public function __construct()
    {
        $this->config = require __DIR__ . '/../../config.php';
        $this->auth = new AuthService($this->config);
        $this->session = $this->auth->session();
    }

    private function json(array $payload, int $status = 200): void
    {
        if (!headers_sent()) {
            http_response_code($status);
            header('Content-Type: application/json; charset=utf-8');
        }
        echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    }

    private function input(): array
    {
        $raw = file_get_contents('php://input');
        $decoded = (!empty($raw) ? json_decode($raw, true) : null);
        return is_array($decoded) ? $decoded : ($_POST ?: []);
    }

    public function requestAdherent(): void
    {
        $this->auth->sendSecurityHeaders();
        $input = $this->input();
        $id = trim((string) ($input['identifier'] ?? $input['email'] ?? $input['cssa_id'] ?? ''));
        if ($id === '') {
            $this->json(['ok' => false, 'error' => 'identifier_required'], 400);
            return;
        }
        $this->json($this->auth->requestAdherentOtp($id));
    }

    public function verifyAdherent(): void
    {
        $this->auth->sendSecurityHeaders();
        $input = $this->input();
        $cid = trim((string) ($input['challenge_id'] ?? ''));
        $code = trim((string) ($input['code'] ?? ''));
        $res = $this->auth->verifyAdherentOtp($cid, $code);
        $this->json($res, (int) ($res['status'] ?? 200));
    }

    public function loginAdmin(): void
    {
        $this->auth->sendSecurityHeaders();
        $input = $this->input();
        $email = trim((string) ($input['email'] ?? ''));
        $password = (string) ($input['password'] ?? '');
        if ($email === '' || $password === '') {
            $this->json(['ok' => false, 'error' => 'credentials_required'], 400);
            return;
        }
        $res = $this->auth->loginOpsPassword($email, $password);
        $this->json($res, (int) ($res['status'] ?? 200));
    }

    public function verifyAdminTotp(): void
    {
        $this->auth->sendSecurityHeaders();
        $input = $this->input();
        $code = trim((string) ($input['code'] ?? ''));
        $enroll = !empty($input['enroll']);
        $res = $this->auth->verifyOpsTotp($code, $enroll);
        $this->json($res, (int) ($res['status'] ?? 200));
    }

    public function logout(): void
    {
        $this->auth->sendSecurityHeaders();
        $role = $this->session->snapshot()['role'] ?? '';
        $this->session->logout();
        $redirect = str_contains((string) $role, 'OPS') || $role === 'ADMIN' ? '/login/admin' : '/login/adherent';
        if (($this->input()['_json'] ?? false) || str_contains($_SERVER['HTTP_ACCEPT'] ?? '', 'application/json')) {
            $this->json(['ok' => true, 'redirect' => $redirect]);
            return;
        }
        if (!headers_sent()) {
            header('Location: ' . $redirect, true, 302);
        }
    }

    public function csrf(): void
    {
        $this->session->start();
        $this->json(['ok' => true, 'csrf' => $this->session->csrfToken()]);
    }
}
