<?php
declare(strict_types=1);

namespace App\Services;

/**
 * Client optionnel Mutuelle OS (FastAPI). Désactivé par défaut.
 */
final class MutuelleOsClient
{
    private array $os;

    public function __construct(array $config)
    {
        $this->os = $config['mutuelle_os'] ?? [];
    }

    public function isEnabled(): bool
    {
        return ($this->os['enabled'] ?? false) === true
            && !empty($this->os['base_url']);
    }

    /** Best-effort sync membre après Stripe — n'échoue jamais le parcours PHP. */
    public function syncMemberActive(array $membership, ?string $opsToken = null): bool
    {
        if (!$this->isEnabled()) {
            return false;
        }
        $token = $opsToken ?: (string) ($this->os['service_token'] ?? '');
        if ($token === '') {
            return false;
        }
        $payload = [
            'cssa_id' => $membership['cssa_id'] ?? '',
            'nss_id' => $membership['nss_id'] ?? '',
            'plan_id' => $membership['plan_id'] ?? 'silver',
            'currency' => $membership['currency'] ?? 'EUR',
            'subscriber_name' => $membership['subscriber_name'] ?? '',
            'subscriber_country' => $membership['subscriber_country'] ?? '',
            'stripe_checkout_id' => $membership['stripe_checkout_id'] ?? null,
            'status' => 'ACTIVE',
        ];
        $ok = $this->request('POST', '/api/v1/members', $payload, $token);
        if (!$ok) {
            return false;
        }
        return $this->request('POST', '/api/v1/members/activate-from-stripe', [
            'cssa_id' => $payload['cssa_id'],
            'checkout_session_id' => $membership['stripe_checkout_id'] ?? null,
            'subscription_id' => $membership['stripe_subscription_id'] ?? null,
        ], $token);
    }

    public function listProposals(string $opsToken, ?string $status = 'pending'): ?array
    {
        if (!$this->isEnabled() || $opsToken === '') {
            return null;
        }
        $path = '/api/v1/action-center/proposals';
        if ($status) {
            $path .= '?status_filter=' . rawurlencode($status);
        }
        return $this->requestJson('GET', $path, null, $opsToken);
    }

    public function decideProposal(string $opsToken, string $proposalId, string $decision, ?string $note = null): ?array
    {
        if (!$this->isEnabled()) {
            return null;
        }
        return $this->requestJson(
            'POST',
            '/api/v1/action-center/proposals/' . rawurlencode($proposalId) . '/decide',
            ['decision' => $decision, 'note' => $note],
            $opsToken
        );
    }

    public function createProposal(string $opsToken, array $payload): ?array
    {
        if (!$this->isEnabled() || $opsToken === '') {
            return null;
        }
        return $this->requestJson('POST', '/api/v1/action-center/proposals', $payload, $opsToken);
    }

    public function mcareConversation(string $opsToken, array $payload): ?array
    {
        if (!$this->isEnabled() || $opsToken === '') {
            return null;
        }
        return $this->requestJson('POST', '/api/v1/mcare/conversations', $payload, $opsToken);
    }

    public function mcareTransmit(string $opsToken, string $conversationId): ?array
    {
        if (!$this->isEnabled() || $opsToken === '') {
            return null;
        }
        return $this->requestJson(
            'POST',
            '/api/v1/mcare/conversations/transmit',
            ['conversation_id' => $conversationId],
            $opsToken
        );
    }

    private function request(string $method, string $path, ?array $payload, string $token): bool
    {
        $json = $this->requestJson($method, $path, $payload, $token);
        return is_array($json) && (($json['ok'] ?? false) === true || isset($json['member']));
    }

    private function requestJson(string $method, string $path, ?array $payload, string $token): ?array
    {
        if (!function_exists('curl_init')) {
            return null;
        }
        $base = rtrim((string) $this->os['base_url'], '/');
        $curl = curl_init($base . $path);
        if ($curl === false) {
            return null;
        }
        $headers = [
            'Accept: application/json',
            'Authorization: Bearer ' . $token,
        ];
        $opts = [
            CURLOPT_CUSTOMREQUEST => strtoupper($method),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT_MS => (int) ($this->os['timeout_ms'] ?? 2500),
            CURLOPT_HTTPHEADER => $headers,
        ];
        if ($payload !== null) {
            $body = json_encode($payload, JSON_UNESCAPED_UNICODE);
            $headers[] = 'Content-Type: application/json';
            $opts[CURLOPT_HTTPHEADER] = $headers;
            $opts[CURLOPT_POSTFIELDS] = $body;
        }
        curl_setopt_array($curl, $opts);
        $response = curl_exec($curl);
        $status = (int) curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
        curl_close($curl);
        if ($response === false || $status < 200 || $status >= 300) {
            error_log('[MulemaCare OS] ' . $method . ' ' . $path . ' HTTP ' . $status);
            return null;
        }
        $decoded = json_decode((string) $response, true);
        return is_array($decoded) ? $decoded : null;
    }
}
