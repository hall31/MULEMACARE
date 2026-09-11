<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Services\AuthService;
use App\Services\AuditService;
use App\Services\MembershipService;
use App\Services\MutuelleOsClient;
use App\Services\SessionService;

/**
 * APIs hub adhérent / admin / MCare proxy (session PHP).
 */
class HubApiController
{
    private array $config;
    private AuthService $auth;
    private SessionService $session;
    private MembershipService $mem;
    private MutuelleOsClient $os;
    private AuditService $audit;
    private ?array $cachedInput = null;

    public function __construct()
    {
        $this->config = require __DIR__ . '/../../config.php';
        $this->auth = new AuthService($this->config);
        $this->session = $this->auth->session();
        $this->mem = new MembershipService($this->config);
        $this->os = new MutuelleOsClient($this->config);
        $this->audit = new AuditService($this->config);
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
        if ($this->cachedInput !== null) {
            return $this->cachedInput;
        }
        $raw = file_get_contents('php://input');
        $decoded = (!empty($raw) ? json_decode($raw, true) : null);
        $this->cachedInput = is_array($decoded) ? $decoded : ($_POST ?: []);
        return $this->cachedInput;
    }

    private function requireCsrf(): bool
    {
        $token = (string) ($this->input()['csrf_token'] ?? $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
        if (!$this->session->validateCsrf($token)) {
            $this->json(['ok' => false, 'error' => 'csrf_invalid'], 403);
            return false;
        }
        return true;
    }

    private function publicMember(array $m): array
    {
        return [
            'cssa_id' => $m['cssa_id'] ?? '',
            'nss_id' => $m['nss_id'] ?? '',
            'nss_display' => $m['nss_display'] ?? '',
            'card_kind' => $m['card_kind'] ?? 'cssa',
            'coverage_kind' => $m['coverage_kind'] ?? 'formule',
            'membership_id' => $m['membership_id'] ?? '',
            'subscriber_name' => $m['subscriber_name'] ?? '',
            'subscriber_email' => AuthService::maskEmail($m['subscriber_email'] ?? null),
            'subscriber_phone' => AuthService::maskPhone($m['subscriber_phone'] ?? null),
            'subscriber_country' => $m['subscriber_country'] ?? '',
            'city' => $m['city'] ?? '',
            'plan_id' => $m['plan_id'] ?? 'silver',
            'plan_name' => $m['plan_name'] ?? '',
            'composition' => $m['composition'] ?? '',
            'status' => $m['status'] ?? 'PENDING_PAYMENT',
            'annual_cap' => (int) ($m['annual_cap'] ?? 0),
            'consumed_cap' => (int) ($m['consumed_cap'] ?? 0),
            'remaining_cap' => (int) ($m['remaining_cap'] ?? 0),
            'currency' => $m['currency'] ?? 'EUR',
            'beneficiaries' => $m['beneficiaries'] ?? [],
            'valid_until' => $m['valid_until'] ?? ($m['valid_until_label'] ?? ''),
            'carence_general_until' => $m['carence_general_until'] ?? '',
            'carence_maternity_until' => $m['carence_maternity_until'] ?? '',
        ];
    }

    /** GET /api/me */
    public function me(): void
    {
        $this->session->start();
        if (!$this->session->isMember()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        $cssa = $this->session->memberCssa();
        $m = $cssa ? $this->mem->getMemberByQuery($cssa) : null;
        if ($m === null) {
            $this->json(['ok' => false, 'error' => 'membership_missing'], 404);
            return;
        }
        $this->json([
            'ok' => true,
            'member' => $this->publicMember($m),
            'csrf' => $this->session->csrfToken(),
            'mcare' => [
                'enabled' => ($this->config['mcare']['enabled'] ?? false) === true,
                'skus' => $this->config['mcare']['skus'] ?? [],
            ],
        ]);
    }

    /** GET /api/me/claims */
    public function myClaims(): void
    {
        $this->session->start();
        if (!$this->session->isMember()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        $cssa = (string) $this->session->memberCssa();
        $this->json(['ok' => true, 'claims' => $this->mem->listClaims(100, $cssa)]);
    }

    /** POST /api/me/claims — déclaration membre → PENDING_REVIEW */
    public function declareClaim(): void
    {
        $this->session->start();
        if (!$this->session->isMember()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        if (!$this->requireCsrf()) {
            return;
        }
        $cssa = (string) $this->session->memberCssa();
        $m = $this->mem->getMemberByQuery($cssa);
        if ($m === null || ($m['status'] ?? '') !== 'ACTIVE') {
            $this->json(['ok' => false, 'error' => 'active_required'], 402);
            return;
        }
        $in = $this->input();
        $claim = $this->mem->createClaim([
            'cssa_id' => $cssa,
            'clinic_name' => $in['clinic_name'] ?? 'Déclaration adhérent',
            'act_type' => $in['act_type'] ?? 'consultation',
            'amount_invoiced' => (int) ($in['amount_invoiced'] ?? 0),
            'status' => 'PENDING_REVIEW',
            'source' => 'member',
            'beneficiary' => (string) ($in['beneficiary'] ?? ''),
            'notes' => (string) ($in['notes'] ?? ''),
        ]);
        $this->audit->record('member:' . $cssa, 'claim_declare', $cssa, ['ref' => $claim['claim_ref']]);
        $this->json([
            'ok' => true,
            'claim' => $claim,
            'message' => 'Déclaration enregistrée — revue humaine / HITL requise.',
        ]);
    }

    /** GET /api/me/coverage */
    public function myCoverage(): void
    {
        $this->session->start();
        if (!$this->session->isMember()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        $cssa = (string) $this->session->memberCssa();
        $m = $this->mem->getMemberByQuery($cssa);
        if ($m === null) {
            $this->json(['ok' => false, 'error' => 'membership_missing'], 404);
            return;
        }
        $planId = (string) ($m['plan_id'] ?? 'silver');
        $plan = $this->config['plans'][$planId] ?? [];
        $this->json([
            'ok' => true,
            'plan_id' => $planId,
            'plan' => $plan,
            'caps' => [
                'annual' => (int) ($m['annual_cap'] ?? 0),
                'consumed' => (int) ($m['consumed_cap'] ?? 0),
                'remaining' => (int) ($m['remaining_cap'] ?? 0),
            ],
        ]);
    }

    /** @return list<array<string,mixed>> */
    private function flattenNetwork(): array
    {
        $clinics = $this->config['clinics'] ?? [];
        $out = [];
        foreach ($clinics as $bucket) {
            if (!is_array($bucket)) {
                continue;
            }
            $city = (string) ($bucket['city'] ?? '');
            $country = (string) ($bucket['country'] ?? '');
            foreach ($bucket['partners'] ?? [] as $p) {
                if (!is_array($p)) {
                    continue;
                }
                $type = (string) ($p['type'] ?? 'clinic');
                $kind = str_contains(strtolower($type), 'pharmac') ? 'pharmacy' : 'clinic';
                $out[] = [
                    'name' => (string) ($p['name'] ?? ''),
                    'city' => $city,
                    'country' => $country,
                    'district' => (string) ($p['district'] ?? ''),
                    'type' => $type,
                    'kind' => $kind,
                    'services' => (string) ($p['services'] ?? ''),
                    'tiers_payant' => true,
                ];
            }
        }
        return $out;
    }

    /** GET /api/me/network */
    public function myNetwork(): void
    {
        $this->session->start();
        if (!$this->session->isMember() && !$this->session->isOps()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        $q = strtolower(trim((string) ($_GET['q'] ?? '')));
        $type = strtolower(trim((string) ($_GET['type'] ?? 'all')));
        $out = [];
        foreach ($this->flattenNetwork() as $row) {
            if ($type !== 'all' && ($row['kind'] ?? '') !== $type && !str_contains(strtolower((string) $row['type']), $type)) {
                continue;
            }
            $hay = strtolower($row['name'] . ' ' . $row['city'] . ' ' . $row['district']);
            if ($q !== '' && !str_contains($hay, $q)) {
                continue;
            }
            $out[] = $row;
        }
        $this->json(['ok' => true, 'network' => $out]);
    }

    /** GET /api/admin/hub */
    public function adminHub(): void
    {
        $this->session->start();
        if (!$this->session->isOps()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        $stats = $this->mem->getDashboardStats();
        $members = array_map(fn($m) => $this->publicMember($m), $this->mem->listMembers(80));
        $claims = $this->mem->listClaims(80);
        $pendingClaims = array_values(array_filter($claims, static fn($c) => ($c['status'] ?? '') === 'PENDING_REVIEW'));
        $pendingPayments = $this->mem->listPendingPayments(80);
        $this->json([
            'ok' => true,
            'stats' => $stats,
            'members' => $members,
            'claims' => $claims,
            'pending_claims' => count($pendingClaims),
            'pending_payments' => $pendingPayments,
            'pending_payments_count' => count($pendingPayments),
            'plans' => $this->config['plans'] ?? [],
            'tariff_version' => (new \App\Services\TariffCatalog($this->config))->version(),
            'network' => $this->flattenNetwork(),
            'audit' => $this->audit->tail(40),
            'ops_email' => $this->session->opsEmail(),
            'csrf' => $this->session->csrfToken(),
        ]);
    }

    /** POST /api/admin/claims/{ref}/decide — HITL local + optional OS proposal */
    public function decideClaim(string $ref): void
    {
        $this->session->start();
        if (!$this->session->isOps()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        if (!$this->requireCsrf()) {
            return;
        }
        $in = $this->input();
        $decision = strtolower((string) ($in['decision'] ?? ''));
        $map = [
            'approved' => 'APPROVED',
            'approve' => 'APPROVED',
            'rejected' => 'REJECTED',
            'reject' => 'REJECTED',
            'info' => 'INFO_REQUESTED',
        ];
        if (!isset($map[$decision])) {
            $this->json(['ok' => false, 'error' => 'invalid_decision'], 400);
            return;
        }
        $updated = $this->mem->updateClaimStatus($ref, $map[$decision]);
        if ($updated === null) {
            $this->json(['ok' => false, 'error' => 'not_found'], 404);
            return;
        }
        $this->audit->record(
            'ops:' . ($this->session->opsEmail() ?? 'ops'),
            'claim_decide',
            $updated['cssa_id'] ?? null,
            ['ref' => $ref, 'decision' => $map[$decision]]
        );
        // Best-effort mirror OS ActionCenter
        $token = (string) ($this->config['mutuelle_os']['service_token'] ?? '');
        if ($this->os->isEnabled() && $token !== '') {
            $this->os->createProposal($token, [
                'agent_name' => 'AdminHub',
                'action_type' => 'claim_' . strtolower($map[$decision]),
                'cssa_id' => $updated['cssa_id'] ?? '',
                'summary' => 'Claim ' . $ref . ' → ' . $map[$decision],
                'payload' => $updated,
            ]);
        }
        $this->json(['ok' => true, 'claim' => $updated]);
    }

    /** POST /api/mcare/chat */
    public function mcareChat(): void
    {
        $this->session->start();
        if (!$this->session->isMember()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        if (!$this->requireCsrf()) {
            return;
        }
        if (($this->config['mcare']['enabled'] ?? false) !== true) {
            $this->json(['ok' => false, 'error' => 'mcare_disabled'], 503);
            return;
        }
        $cssa = (string) $this->session->memberCssa();
        $m = $this->mem->getMemberByQuery($cssa);
        if ($m === null || ($m['status'] ?? '') !== 'ACTIVE') {
            $this->json(['ok' => false, 'error' => 'active_required'], 402);
            return;
        }
        $in = $this->input();
        $message = trim((string) ($in['message'] ?? ''));
        if ($message === '') {
            $this->json(['ok' => false, 'error' => 'message_required'], 400);
            return;
        }
        $token = (string) ($this->config['mutuelle_os']['service_token'] ?? '');
        if ($this->os->isEnabled() && $token !== '') {
            $data = $this->os->mcareConversation($token, [
                'cssa_id' => $cssa,
                'beneficiary_name' => (string) ($in['beneficiary_name'] ?? ''),
                'message' => $message,
            ]);
            if (is_array($data)) {
                $this->json(['ok' => true] + $data);
                return;
            }
        }
        // Fallback local déterministe si OS off
        $this->json([
            'ok' => true,
            'conversation_id' => 'local-' . bin2hex(random_bytes(4)),
            'reply' => 'MCare (mode local) : pour la couverture, le réseau et la carte CSSA, posez votre question. En cas de symptômes, transmettez à un médecin humain — tags IA / Hypothèses non validées.',
            'tags' => ['IA', 'Hypothèses non validées'],
            'intent' => 'general',
            'source' => 'php_fallback',
        ]);
    }

    /** POST /api/mcare/transmit */
    public function mcareTransmit(): void
    {
        $this->session->start();
        if (!$this->session->isMember()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        if (!$this->requireCsrf()) {
            return;
        }
        $in = $this->input();
        $cid = (string) ($in['conversation_id'] ?? '');
        $token = (string) ($this->config['mutuelle_os']['service_token'] ?? '');
        if ($this->os->isEnabled() && $token !== '' && $cid !== '') {
            $data = $this->os->mcareTransmit($token, $cid);
            if (is_array($data)) {
                $this->audit->record('member:' . $this->session->memberCssa(), 'mcare_transmit', $this->session->memberCssa(), ['conversation_id' => $cid]);
                $this->json(['ok' => true] + $data);
                return;
            }
        }
        $this->audit->record('member:' . $this->session->memberCssa(), 'mcare_transmit_local', $this->session->memberCssa());
        $this->json([
            'ok' => true,
            'proposal_id' => 'local-hitl',
            'message' => 'Transmission enregistrée pour revue humaine (WhatsApp desk / Lisacare).',
        ]);
    }
}
