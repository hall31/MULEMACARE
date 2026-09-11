<?php
declare(strict_types=1);

namespace App\Services;

use RuntimeException;

/**
 * Client Stripe Checkout (abonnements diaspora EUR/USD) via API REST.
 * Aucune dépendance Composer — curl natif PHP 8.
 *
 * Carte CSSA ACTIVE uniquement après webhook signé (checkout.session.completed).
 */
final class StripePaymentService
{
    private array $stripe;
    private array $app;

    public function __construct(array $config)
    {
        $this->stripe = $config['stripe'] ?? [];
        $this->app = $config['app'] ?? [];
    }

    public function isEnabled(): bool
    {
        return ($this->stripe['enabled'] ?? false) === true
            && !empty($this->stripe['secret_key'])
            && str_starts_with((string) $this->stripe['secret_key'], 'sk_');
    }

    public function publishableKey(): string
    {
        return (string) ($this->stripe['publishable_key'] ?? '');
    }

    /**
     * Crée une session Checkout mode subscription (encaissement rapide diaspora).
     *
     * @param array $membership Record PENDING_PAYMENT (cssa_id, amount, currency, cycle, …)
     * @return array{id:string,url:string,mode:string}
     */
    public function createSubscriptionCheckout(array $membership, string $successUrl, string $cancelUrl): array
    {
        if (!$this->isEnabled()) {
            throw new RuntimeException('Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_ENABLED=true.');
        }

        $currency = strtolower((string) ($membership['currency'] ?? 'eur'));
        if (!in_array($currency, ['eur', 'usd'], true)) {
            throw new RuntimeException('Stripe diaspora checkout accepts EUR or USD only.');
        }

        $cycle = ($membership['cycle'] ?? 'annual') === 'monthly' ? 'monthly' : 'annual';
        $interval = $cycle === 'monthly' ? 'month' : 'year';
        $amountMajor = (float) ($membership['amount'] ?? 0);
        if ($amountMajor <= 0) {
            throw new RuntimeException('Invalid subscription amount for Stripe checkout.');
        }
        $unitAmount = (int) round($amountMajor * 100); // cents

        $planName = (string) ($membership['plan_name'] ?? 'MulemaCare');
        $cssaId = (string) ($membership['cssa_id'] ?? '');
        $email = trim((string) ($membership['subscriber_email'] ?? ''));

        $params = [
            'mode' => 'subscription',
            'success_url' => $successUrl,
            'cancel_url' => $cancelUrl,
            'client_reference_id' => $cssaId,
            'metadata[cssa_id]' => $cssaId,
            'metadata[membership_id]' => (string) ($membership['membership_id'] ?? ''),
            'metadata[plan_id]' => (string) ($membership['plan_id'] ?? ''),
            'metadata[source]' => 'mulemacare_diaspora',
            'subscription_data[metadata][cssa_id]' => $cssaId,
            'line_items[0][quantity]' => '1',
            'line_items[0][price_data][currency]' => $currency,
            'line_items[0][price_data][unit_amount]' => (string) $unitAmount,
            'line_items[0][price_data][recurring][interval]' => $interval,
            'line_items[0][price_data][product_data][name]' => 'MulemaCare — ' . $planName,
            'line_items[0][price_data][product_data][description]' => 'Abonnement mutuelle santé diaspora (' . $cycle . ')',
            'payment_method_types[0]' => 'card',
            'allow_promotion_codes' => 'true',
            'billing_address_collection' => 'auto',
            'locale' => 'fr',
        ];

        if ($email !== '' && filter_var($email, FILTER_VALIDATE_EMAIL)) {
            $params['customer_email'] = $email;
        }

        $session = $this->request('POST', '/v1/checkout/sessions', $params);
        $url = (string) ($session['url'] ?? '');
        $id = (string) ($session['id'] ?? '');
        if ($url === '' || $id === '') {
            throw new RuntimeException('Stripe Checkout session missing url/id.');
        }

        return [
            'id' => $id,
            'url' => $url,
            'mode' => (string) ($session['mode'] ?? 'subscription'),
        ];
    }

    /**
     * Vérifie la signature Stripe-Signature et retourne l'événement décodé.
     *
     * @return array<string,mixed>
     */
    public function constructEvent(string $payload, string $sigHeader): array
    {
        $secret = (string) ($this->stripe['webhook_secret'] ?? '');
        if ($secret === '' || !str_starts_with($secret, 'whsec_')) {
            throw new RuntimeException('STRIPE_WEBHOOK_SECRET missing or invalid.');
        }

        $parts = [];
        foreach (explode(',', $sigHeader) as $item) {
            $kv = explode('=', trim($item), 2);
            if (count($kv) === 2) {
                $parts[$kv[0]][] = $kv[1];
            }
        }
        $timestamp = $parts['t'][0] ?? '';
        $signatures = $parts['v1'] ?? [];
        if ($timestamp === '' || $signatures === []) {
            throw new RuntimeException('Invalid Stripe-Signature header.');
        }

        $tolerance = (int) ($this->stripe['webhook_tolerance_sec'] ?? 300);
        if (abs(time() - (int) $timestamp) > $tolerance) {
            throw new RuntimeException('Stripe webhook timestamp outside tolerance.');
        }

        $signedPayload = $timestamp . '.' . $payload;
        $expected = hash_hmac('sha256', $signedPayload, $secret);
        $valid = false;
        foreach ($signatures as $sig) {
            if (hash_equals($expected, $sig)) {
                $valid = true;
                break;
            }
        }
        if (!$valid) {
            throw new RuntimeException('Stripe webhook signature mismatch.');
        }

        $event = json_decode($payload, true);
        if (!is_array($event) || empty($event['type']) || !is_array($event['data']['object'] ?? null)) {
            throw new RuntimeException('Invalid Stripe event payload.');
        }
        return $event;
    }

    /**
     * @param array<string,string> $formParams
     * @return array<string,mixed>
     */
    private function request(string $method, string $path, array $formParams = []): array
    {
        if (!function_exists('curl_init')) {
            throw new RuntimeException('PHP cURL extension required for Stripe.');
        }

        $curl = curl_init('https://api.stripe.com' . $path);
        if ($curl === false) {
            throw new RuntimeException('Unable to init Stripe HTTP client.');
        }

        $headers = [
            'Authorization: Bearer ' . $this->stripe['secret_key'],
            'Content-Type: application/x-www-form-urlencoded',
            'Stripe-Version: ' . ($this->stripe['api_version'] ?? '2024-11-20.acacia'),
        ];

        curl_setopt_array($curl, [
            CURLOPT_CUSTOMREQUEST => strtoupper($method),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 8,
            CURLOPT_TIMEOUT => 20,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_POSTFIELDS => http_build_query($formParams),
        ]);

        $response = curl_exec($curl);
        $status = (int) curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
        $error = curl_error($curl);
        curl_close($curl);

        if ($response === false) {
            throw new RuntimeException('Stripe HTTP error: ' . $error);
        }

        $decoded = json_decode((string) $response, true);
        if (!is_array($decoded)) {
            throw new RuntimeException('Stripe returned non-JSON body (HTTP ' . $status . ').');
        }
        if ($status < 200 || $status >= 300) {
            $msg = (string) ($decoded['error']['message'] ?? 'HTTP ' . $status);
            throw new RuntimeException('Stripe API error: ' . $msg);
        }
        return $decoded;
    }
}
