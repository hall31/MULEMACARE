<?php
declare(strict_types=1);

namespace App\Services;

use RuntimeException;

/**
 * Client isolé du gateway partenaire HealthOS v1.
 *
 * Il est désactivé par défaut : aucune page ni API historique MulemaCare ne
 * dépend de ce client avant l'activation explicite du feature flag serveur.
 */
final class HealthOSClient
{
    private array $bridge;

    public function __construct(array $config)
    {
        $this->bridge = $config['healthos_bridge'] ?? [];
    }

    public function isEnabled(): bool
    {
        return ($this->bridge['enabled'] ?? false) === true
            && !empty($this->bridge['base_url'])
            && !empty($this->bridge['api_key']);
    }

    /**
     * Retourne les droits HealthOS pour un identifiant patient déjà mappé.
     *
     * Le mapping CSSA -> patient_id HealthOS est volontairement hors de ce
     * client : il doit être validé lors de la migration de données, jamais
     * déduit à partir d'un identifiant public de carte.
     */
    public function eligibility(string $healthosPatientId): ?array
    {
        if (!$this->isEnabled()) {
            return null;
        }

        return $this->request('GET', '/api/v1/partner/members/' . rawurlencode($healthosPatientId) . '/eligibility');
    }

    /** Soumet une demande de préautorisation, toujours revue humainement dans HealthOS. */
    public function requestPreauthorization(array $payload): ?array
    {
        if (!$this->isEnabled()) {
            return null;
        }

        return $this->request('POST', '/api/v1/partner/claims/preauthorize', $payload);
    }

    private function request(string $method, string $path, ?array $payload = null): ?array
    {
        $baseUrl = (string) $this->bridge['base_url'];
        if (!str_starts_with($baseUrl, 'https://')) {
            throw new RuntimeException('HealthOS bridge requires an HTTPS base URL.');
        }
        if (!function_exists('curl_init')) {
            throw new RuntimeException('The HealthOS bridge requires the PHP cURL extension.');
        }

        $apiKey = (string) $this->bridge['api_key'];
        $body = $payload === null ? '' : json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
        $timestamp = (string) time();
        $nonce = bin2hex(random_bytes(16));
        $canonical = implode("\n", [
            $timestamp,
            $nonce,
            strtoupper($method),
            $path,
            hash('sha256', $body),
        ]);
        $signature = hash_hmac('sha256', $canonical, $apiKey);

        $curl = curl_init($baseUrl . $path);
        if ($curl === false) {
            throw new RuntimeException('Unable to initialize HealthOS request.');
        }
        curl_setopt_array($curl, [
            CURLOPT_CUSTOMREQUEST => strtoupper($method),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT_MS => (int) $this->bridge['timeout_ms'],
            CURLOPT_TIMEOUT_MS => (int) $this->bridge['timeout_ms'],
            CURLOPT_HTTPHEADER => [
                'Accept: application/json',
                'Content-Type: application/json',
                'X-API-Key: ' . $apiKey,
                'X-Timestamp: ' . $timestamp,
                'X-Nonce: ' . $nonce,
                'X-Signature: ' . $signature,
            ],
        ]);
        if ($payload !== null) {
            curl_setopt($curl, CURLOPT_POSTFIELDS, $body);
        }

        $response = curl_exec($curl);
        $status = (int) curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
        $error = curl_error($curl);
        curl_close($curl);
        if ($response === false || $status < 200 || $status >= 300) {
            error_log('[MulemaCare HealthOS bridge] request failed: HTTP ' . $status . ' ' . $error);
            return null;
        }

        $decoded = json_decode((string) $response, true);
        if (!is_array($decoded) || ($decoded['success'] ?? false) !== true || !is_array($decoded['data'] ?? null)) {
            error_log('[MulemaCare HealthOS bridge] invalid gateway response.');
            return null;
        }
        return $decoded['data'];
    }
}
