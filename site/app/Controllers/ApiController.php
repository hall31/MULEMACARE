<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Services\QuoteService;
use App\Services\MembershipService;
use App\Services\StripePaymentService;
use App\Services\MutuelleOsClient;
use App\Services\AuthService;
use App\Services\AuditService;
use App\Services\SessionService;
use Throwable;

/**
 * Contrôleur API pour Devis, Adhésions, Stripe diaspora, Fast-Check & Admin
 */
class ApiController {
    private array $config;
    private QuoteService $quoteService;
    private MembershipService $memService;
    private StripePaymentService $stripe;
    private MutuelleOsClient $os;
    private AuthService $auth;
    private AuditService $audit;
    private SessionService $session;

    public function __construct() {
        $this->config = require __DIR__ . '/../../config.php';
        $this->quoteService = new QuoteService($this->config);
        $this->memService = new MembershipService($this->config);
        $this->stripe = new StripePaymentService($this->config);
        $this->os = new MutuelleOsClient($this->config);
        $this->auth = new AuthService($this->config);
        $this->session = $this->auth->session();
        $this->audit = new AuditService($this->config);
    }

    private function requireCsrf(): bool {
        $input = $this->input();
        $token = (string) ($input['csrf_token'] ?? $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
        if (!$this->session->validateCsrf($token)) {
            $this->json(['success' => false, 'ok' => false, 'error' => 'csrf_invalid'], 403);
            return false;
        }
        return true;
    }

    private function osServiceToken(): string {
        return (string) ($this->config['mutuelle_os']['service_token'] ?? '');
    }

    private ?array $cachedInput = null;

    private function json(array $payload, int $status = 200): void {
        if (!headers_sent()) {
            http_response_code($status);
            header('Content-Type: application/json; charset=utf-8');
        }
        echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    }

    private function input(): array {
        if ($this->cachedInput !== null) {
            return $this->cachedInput;
        }
        $raw = file_get_contents('php://input');
        $decoded = (!empty($raw) ? json_decode($raw, true) : null);
        $this->cachedInput = is_array($decoded) ? $decoded : ($_POST ?: []);
        return $this->cachedInput;
    }

    /** Devise diaspora Stripe carte ? */
    private function wantsStripeCheckout(array $input): bool {
        $method = $this->memService->normalizePaymentMethod((string) ($input['payment_method'] ?? 'card'));
        $currency = strtoupper((string) ($input['currency'] ?? 'EUR'));
        $diasporaCurrencies = $this->config['stripe']['diaspora_currencies'] ?? ['EUR', 'USD'];
        if ($method !== 'stripe') {
            return false;
        }
        return in_array($currency, $diasporaCurrencies, true);
    }

    /**
     * Calcule ou enregistre un devis en direct (Particuliers ou Entreprises)
     * POST /api/quote
     */
    public function quote(): void {
        $input = $this->input();
        $save = !empty($input['save']) || !empty($input['prospect_email']) || !empty($input['email']);

        if ($save) {
            $quote = $this->quoteService->createQuote($input);
            $this->json([
                'success' => true,
                'quote'   => $quote,
                'message' => 'Votre devis officiel ' . $quote['quote_number'] . ' est prêt.',
            ]);
            return;
        }

        $type = $input['type'] ?? 'individual';

        if ($type === 'corporate') {
            $count = (int) ($input['employee_count'] ?? 10);
            $tier = $input['plan_tier'] ?? 'silver';
            $curr = $input['currency'] ?? 'XAF';
            $res = $this->quoteService->calculateCorporateQuote($count, $tier, $curr);
        } else {
            $planId = $input['plan_id'] ?? 'silver';
            $comp = $input['composition'] ?? 'family';
            $curr = $input['currency'] ?? 'EUR';
            $cycle = $input['cycle'] ?? 'annual';
            $res = $this->quoteService->calculateIndividualQuote($planId, $comp, $curr, $cycle);
        }

        $this->json(['success' => true, 'data' => $res]);
    }

    /**
     * Tunnel zéro friction — devis / adhésion / entreprise en 1 appel.
     * POST /api/express
     * mode=quote|adhere|corporate
     */
    public function express(): void {
        $input = $this->input();
        $mode = strtolower((string) ($input['mode'] ?? 'adhere'));

        if ($mode === 'quote') {
            if (empty($input['type'])) {
                $input['type'] = 'individual';
            }
            // Nom optionnel pour devis anonyme (simulateur)
            if (empty($input['prospect_name']) && empty($input['name'])) {
                $input['prospect_name'] = 'Prospect express';
            }
            if (!empty($input['composition'])) {
                $input['composition'] = $this->quoteService->normalizeComposition((string) $input['composition']);
            }
            $quote = $this->quoteService->createQuote($input);
            $this->json([
                'success' => true,
                'mode' => 'quote',
                'quote' => $quote,
                'next_url' => $quote['subscribe_url'] ?? '',
                'whatsapp_url' => $quote['whatsapp_url'] ?? '',
                'message' => 'Devis ' . $quote['quote_number'] . ' prêt.',
            ]);
            return;
        }

        if ($mode === 'corporate') {
            $company = trim((string) ($input['company_name'] ?? $input['company'] ?? ''));
            $contact = trim((string) ($input['subscriber_name'] ?? $input['prospect_name'] ?? $input['name'] ?? ''));
            $phone = trim((string) ($input['subscriber_phone'] ?? $input['prospect_phone'] ?? $input['phone'] ?? ''));
            if ($company === '' || $contact === '' || $phone === '') {
                $this->json([
                    'success' => false,
                    'error' => 'Entreprise, contact et téléphone WhatsApp requis.',
                ], 400);
                return;
            }
            $input['type'] = 'corporate';
            $input['prospect_name'] = $contact;
            $input['prospect_phone'] = $phone;
            $input['prospect_email'] = trim((string) ($input['subscriber_email'] ?? $input['email'] ?? ''));
            $input['company_name'] = $company;
            $input['employee_count'] = (int) ($input['employee_count'] ?? 10);
            $input['plan_tier'] = $input['plan_tier'] ?? $input['plan_id'] ?? 'silver';
            $input['currency'] = 'XAF';
            $input['payment_method'] = $input['payment_method'] ?? 'whatsapp';

            $quote = $this->quoteService->createQuote($input);
            $contract = $this->memService->createCorporateContract($input, $quote);
            $this->audit->record('public:express', 'corporate_registered', $contract['contract_id'], [
                'quote' => $quote['quote_number'],
                'company' => $company,
            ]);
            $this->json([
                'success' => true,
                'mode' => 'corporate',
                'client_registered' => true,
                'quote' => $quote,
                'contract' => $contract,
                'contract_id' => $contract['contract_id'],
                'quote_number' => $quote['quote_number'],
                'status' => 'PENDING_PAYMENT',
                'whatsapp_url' => $contract['whatsapp_url'],
                'view_url' => $quote['view_url'],
                'open_whatsapp' => true,
                'message' => 'Entreprise enregistrée. Devis + dossier convention créés.',
            ]);
            return;
        }

        // mode=adhere — devis (optionnel) + adhésion en 1 shot
        $name = trim((string) ($input['subscriber_name'] ?? $input['name'] ?? ''));
        $phone = trim((string) ($input['subscriber_phone'] ?? $input['phone'] ?? ''));
        if ($name === '' || $phone === '') {
            $this->json(['success' => false, 'error' => 'Nom et WhatsApp requis pour adhérer.'], 400);
            return;
        }
        if (!empty($input['composition'])) {
            $input['composition'] = $this->quoteService->normalizeComposition((string) $input['composition']);
        }
        $input['payment_method'] = $this->memService->normalizePaymentMethod(
            (string) ($input['payment_method'] ?? 'whatsapp')
        );
        if (empty($input['currency'])) {
            $m = $input['payment_method'];
            $input['currency'] = in_array($m, ['whatsapp', 'orange_money', 'mtn_momo'], true) ? 'XAF' : 'EUR';
        }

        // Sauvegarde devis léger si demandé
        $quote = null;
        if (!empty($input['save_quote']) || empty($input['quote_number'])) {
            $quote = $this->quoteService->createQuote([
                'type' => 'individual',
                'prospect_name' => $name,
                'prospect_phone' => $phone,
                'prospect_email' => $input['subscriber_email'] ?? $input['email'] ?? '',
                'plan_id' => $input['plan_id'] ?? 'silver',
                'composition' => $input['composition'] ?? 'family',
                'currency' => $input['currency'],
                'cycle' => $input['cycle'] ?? 'annual',
                'city' => $input['city'] ?? 'douala',
            ]);
            $input['quote_number'] = $quote['quote_number'];
        }

        // Délègue au flux subscribe existant (enregistrement client + rail)
        $this->cachedInput = $input;
        $this->subscribe();
    }

    /**
     * Adhésion mutuelle — enregistre TOUJOURS le client (PENDING), puis rail paiement.
     *
     * Rails :
     * - stripe (EUR/USD) → Checkout
     * - qonto → instructions IBAN + WhatsApp preuve
     * - whatsapp / orange_money / mtn_momo → client enregistré + deep-link WA (USSD)
     *
     * POST /api/subscribe
     */
    public function subscribe(): void {
        $input = $this->input();

        $name = trim($input['subscriber_name'] ?? $input['name'] ?? '');
        $phone = trim($input['subscriber_phone'] ?? $input['phone'] ?? '');

        if ($name === '' || $phone === '') {
            $this->json([
                'success' => false,
                'error'   => 'Veuillez renseigner votre nom complet et votre numéro WhatsApp.',
            ], 400);
            return;
        }

        $method = $this->memService->normalizePaymentMethod((string) ($input['payment_method'] ?? 'whatsapp'));
        $input['payment_method'] = $method;

        // Devise par défaut selon le rail
        if (empty($input['currency'])) {
            $input['currency'] = in_array($method, ['whatsapp', 'orange_money', 'mtn_momo'], true) ? 'XAF' : 'EUR';
        }
        // MoMo / WhatsApp → forcer XAF si l'utilisateur n'a pas choisi EUR diaspora
        if (in_array($method, ['orange_money', 'mtn_momo'], true) && empty($input['force_currency'])) {
            $input['currency'] = 'XAF';
        }

        // 1) Toujours enregistrer le client dans le système
        $membership = $this->memService->createMembership($input);
        $this->audit->record(
            'public:subscribe',
            'client_registered',
            $membership['cssa_id'] ?? null,
            [
                'payment_method' => $method,
                'currency' => $membership['currency'] ?? '',
                'tariff_version' => $membership['tariff_version'] ?? '',
            ]
        );

        // 2a) Stripe diaspora
        if ($this->wantsStripeCheckout($input)) {
            if (!$this->stripe->isEnabled()) {
                // Fallback : client déjà enregistré → WhatsApp
                $this->json([
                    'success' => true,
                    'client_registered' => true,
                    'requires_payment' => true,
                    'next_step' => 'open_whatsapp',
                    'cssa_id' => $membership['cssa_id'],
                    'nss_id' => $membership['nss_id'] ?? '',
                    'nss_display' => $membership['nss_display'] ?? '',
                    'status' => $membership['status'],
                    'whatsapp_url' => $membership['whatsapp_url'],
                    'price_label' => $membership['price_label'],
                    'plan_name' => $membership['plan_name'],
                    'message' => 'Client enregistré. Stripe indisponible — finalisez via WhatsApp.',
                ], 200);
                return;
            }

            try {
                $appUrl = rtrim((string) ($this->config['app']['url'] ?? 'https://mulemacare.com'), '/');
                $success = $appUrl . '/adhesion?paid=1&cssa=' . rawurlencode($membership['cssa_id']);
                $cancel = $appUrl . '/adhesion?canceled=1&cssa=' . rawurlencode($membership['cssa_id']);
                $session = $this->stripe->createSubscriptionCheckout($membership, $success, $cancel);
                $this->memService->attachStripeCheckout($membership['cssa_id'], $session['id']);

                $this->json([
                    'success'            => true,
                    'client_registered'  => true,
                    'requires_payment'   => true,
                    'next_step'          => 'stripe_checkout',
                    'checkout_url'       => $session['url'],
                    'checkout_session_id'=> $session['id'],
                    'cssa_id'            => $membership['cssa_id'],
                    'nss_id'             => $membership['nss_id'] ?? '',
                    'nss_display'        => $membership['nss_display'] ?? '',
                    'status'             => 'PENDING_PAYMENT',
                    'plan_name'          => $membership['plan_name'],
                    'price_label'        => $membership['price_label'],
                    'tariff_version'     => $membership['tariff_version'] ?? '',
                    'whatsapp_url'       => $membership['whatsapp_url'],
                    'message'            => 'Client enregistré. Redirection Stripe Checkout.',
                ]);
                return;
            } catch (Throwable $e) {
                error_log('[MulemaCare Stripe] checkout failed: ' . $e->getMessage());
                $this->json([
                    'success' => true,
                    'client_registered' => true,
                    'requires_payment' => true,
                    'next_step' => 'open_whatsapp',
                    'cssa_id' => $membership['cssa_id'],
                    'whatsapp_url' => $membership['whatsapp_url'],
                    'status' => $membership['status'],
                    'error_stripe' => 'checkout_failed',
                    'message' => 'Client enregistré. Checkout Stripe échoué — continuez sur WhatsApp.',
                ], 200);
                return;
            }
        }

        // 2b) Qonto / WhatsApp / MoMo — client enregistré, activation HITL
        $payload = [
            'success' => true,
            'client_registered' => true,
            'requires_payment' => true,
            'next_step' => $membership['next_step'] ?? 'open_whatsapp',
            'cssa_id' => $membership['cssa_id'],
            'nss_id' => $membership['nss_id'] ?? '',
            'nss_display' => $membership['nss_display'] ?? '',
            'plan_name' => $membership['plan_name'],
            'price_label' => $membership['price_label'],
            'amount_due' => $membership['amount_due'] ?? $membership['amount'],
            'amount_due_label' => $membership['amount_due_label'] ?? '',
            'tariff_version' => $membership['tariff_version'] ?? '',
            'payment_method' => $method,
            'payment_channel' => $membership['payment_channel'] ?? $method,
            'card_url' => $membership['card_url'],
            'portal_url' => $membership['portal_url'],
            'whatsapp_url' => $membership['whatsapp_url'],
            'momo_ussd' => $membership['momo_ussd'] ?? [],
            'status' => $membership['status'],
            'membership' => $membership,
            'message' => 'Client enregistré dans le système (PENDING). Finalisez le paiement puis confirmation desk.',
        ];
        if ($method === 'qonto') {
            $payload['qonto'] = $membership['qonto'] ?? $this->memService->buildQontoInstructions($membership);
            $payload['message'] = 'Client enregistré. Effectuez le virement Qonto avec le libellé CSSA, puis envoyez la preuve WhatsApp.';
        }
        if (in_array($method, ['orange_money', 'mtn_momo', 'whatsapp'], true)) {
            $payload['open_whatsapp'] = true;
            $payload['message'] = 'Client enregistré. Ouvrez WhatsApp pour transmettre CSSA + preuve de paiement MoMo.';
        }
        $this->json($payload);
    }

    /**
     * Confirme paiement manuel (Qonto / WhatsApp / MoMo) — session OPS + CSRF.
     * POST /api/admin/payments/confirm
     */
    public function confirmManualPayment(): void {
        $this->session->start();
        if (!$this->session->isOps()) {
            $this->json(['success' => false, 'error' => 'auth_required'], 401);
            return;
        }
        if (!$this->requireCsrf()) {
            return;
        }
        $input = $this->input();
        $cssaId = strtoupper(trim((string) ($input['cssa_id'] ?? '')));
        if ($cssaId === '') {
            $this->json(['success' => false, 'error' => 'cssa_id requis'], 400);
            return;
        }
        $activated = $this->memService->activateFromManualPayment([
            'cssa_id' => $cssaId,
            'channel' => (string) ($input['channel'] ?? 'whatsapp'),
            'amount_received' => isset($input['amount_received']) ? (float) $input['amount_received'] : null,
            'payment_ref' => (string) ($input['payment_ref'] ?? $input['momo_ref'] ?? ''),
            'actor' => 'ops:' . ($this->session->opsEmail() ?? 'unknown'),
        ]);
        if ($activated === null) {
            $this->json(['success' => false, 'error' => 'not_found_or_invalid_status'], 404);
            return;
        }
        $this->audit->record(
            'ops:' . ($this->session->opsEmail() ?? 'unknown'),
            'payment_confirm_manual',
            $cssaId,
            [
                'channel' => $input['channel'] ?? '',
                'payment_ref' => $input['payment_ref'] ?? $input['momo_ref'] ?? '',
            ]
        );
        $this->json([
            'success' => true,
            'member' => [
                'cssa_id' => $activated['cssa_id'],
                'status' => $activated['status'],
                'paid_at' => $activated['paid_at'] ?? null,
            ],
            'message' => 'Paiement confirmé — carte ACTIVE.',
        ]);
    }

    /**
     * Crée uniquement une session Stripe pour un cssa_id PENDING (retry paiement).
     * POST /api/checkout
     */
    public function checkout(): void {
        $input = $this->input();
        $cssaId = strtoupper(trim((string) ($input['cssa_id'] ?? '')));
        if ($cssaId === '') {
            $this->json(['success' => false, 'error' => 'cssa_id requis.'], 400);
            return;
        }
        $member = $this->memService->getMemberByQuery($cssaId);
        if (!$member) {
            $this->json(['success' => false, 'error' => 'Adhérent introuvable.'], 404);
            return;
        }
        if (strtoupper((string) ($member['status'] ?? '')) === 'ACTIVE') {
            $this->json([
                'success' => true,
                'already_active' => true,
                'portal_url' => $member['portal_url'] ?? ('/espace-adherent?adh=' . $cssaId),
            ]);
            return;
        }
        if (!$this->stripe->isEnabled()) {
            $this->json(['success' => false, 'error' => 'Stripe non configuré.'], 503);
            return;
        }

        try {
            $appUrl = rtrim((string) ($this->config['app']['url'] ?? 'https://mulemacare.com'), '/');
            $session = $this->stripe->createSubscriptionCheckout(
                $member,
                $appUrl . '/adhesion?paid=1&cssa=' . rawurlencode($cssaId),
                $appUrl . '/adhesion?canceled=1&cssa=' . rawurlencode($cssaId)
            );
            $this->memService->attachStripeCheckout($cssaId, $session['id']);
            $this->json([
                'success' => true,
                'checkout_url' => $session['url'],
                'checkout_session_id' => $session['id'],
            ]);
        } catch (Throwable $e) {
            error_log('[MulemaCare Stripe] retry checkout: ' . $e->getMessage());
            $this->json(['success' => false, 'error' => 'Checkout Stripe échoué.'], 502);
        }
    }

    /**
     * Fast-Check API pour les cliniques et pharmacies partenaires
     * GET /api/verify-card/{code}
     */
    public function verifyCard(string $code): void {
        $card = $this->memService->verifyCard($code);

        if (!$card) {
            $this->json([
                'valid' => false,
                'error' => 'Numéro CSSA introuvable ou non conventionné.',
            ], 404);
            return;
        }

        if (($card['status'] ?? '') !== 'ACTIVE' || ($card['valid'] ?? true) === false) {
            $this->json([
                'valid' => false,
                'card'  => $card,
                'error' => 'Carte en attente de paiement Stripe — tiers-payant inactif.',
            ], 402);
            return;
        }

        $this->json(['valid' => true, 'card' => $card]);
    }

    /**
     * Recherche d'un adhérent pour l'Espace Adhérent self-service
     * GET /api/adherent/lookup?q=...
     */
    public function lookupAdherent(): void {
        $this->session->start();
        if (!$this->session->isMember() && !$this->session->isOps()) {
            $this->json(['success' => false, 'error' => 'auth_required'], 401);
            return;
        }
        $q = trim($_GET['q'] ?? '');
        if ($this->session->isMember()) {
            $own = $this->session->memberCssa();
            if (strtoupper($q) !== strtoupper((string) $own)) {
                $this->json(['success' => false, 'error' => 'forbidden'], 403);
                return;
            }
            $q = (string) $own;
        }
        $member = $this->memService->getMemberByQuery($q);
        if ($member) {
            $member['subscriber_email'] = AuthService::maskEmail($member['subscriber_email'] ?? null);
            $member['subscriber_phone'] = AuthService::maskPhone($member['subscriber_phone'] ?? null);
            $this->json(['success' => true, 'member' => $member]);
            return;
        }
        $this->json(['success' => false, 'error' => 'Aucun compte trouvé avec cet identifiant.'], 404);
    }

    /**
     * Enregistrement d'une prise en charge tiers-payant par une clinique
     * POST /api/claim
     */
    public function createClaim(): void {
        $input = $this->input();
        $cssaId = trim($input['cssa_id'] ?? '');
        if ($cssaId === '') {
            $this->json(['success' => false, 'error' => 'N° CSSA obligatoire.'], 400);
            return;
        }

        $card = $this->memService->verifyCard($cssaId);
        if (!$card || ($card['status'] ?? '') !== 'ACTIVE') {
            $this->json(['success' => false, 'error' => 'Carte inactive — paiement Stripe requis.'], 402);
            return;
        }

        $claim = $this->memService->createClaim($input);
        $this->json([
            'success' => true,
            'claim'   => $claim,
            'message' => 'Bon de prise en charge ' . $claim['claim_ref'] . ' émis avec succès (0 F avancé par le patient).',
        ]);
    }

    /**
     * Modification du statut d'une carte (Espace Admin) — session OPS + CSRF
     * POST /api/admin/toggle-status
     */
    public function toggleMemberStatus(): void {
        $this->session->start();
        if (!$this->session->isOps()) {
            $this->json(['success' => false, 'error' => 'auth_required'], 401);
            return;
        }
        if (!$this->requireCsrf()) {
            return;
        }
        $input = $this->input();
        $cssaId = trim($input['cssa_id'] ?? '');
        $status = trim($input['status'] ?? 'ACTIVE');

        if ($cssaId === '') {
            $this->json(['success' => false, 'error' => 'N° CSSA requis.'], 400);
            return;
        }

        $updated = $this->memService->updateMemberStatus($cssaId, $status);
        $this->audit->record(
            'ops:' . ($this->session->opsEmail() ?? 'unknown'),
            'toggle_status',
            $cssaId,
            ['status' => strtoupper($status)]
        );
        $this->json([
            'success' => $updated,
            'status'  => strtoupper($status),
            'message' => 'Statut mis à jour pour ' . $cssaId,
        ]);
    }

    /**
     * Webhook Stripe signé — ACTIVE uniquement après paiement confirmé.
     * POST /api/webhook  (alias /api/stripe/webhook)
     */
    public function webhook(): void {
        $payload = (string) file_get_contents('php://input');
        $sig = (string) ($_SERVER['HTTP_STRIPE_SIGNATURE'] ?? '');
        $result = $this->processStripeWebhook($payload, $sig);
        $this->json($result['body'], $result['status']);
    }

    /**
     * Traite un événement Stripe (testable hors serveur HTTP).
     *
     * @return array{status:int,body:array<string,mixed>}
     */
    public function processStripeWebhook(string $payload, string $sig): array {
        if ($sig === '' || !$this->stripe->isEnabled()) {
            return [
                'status' => 200,
                'body' => ['received' => true, 'handled' => false, 'timestamp' => time()],
            ];
        }

        try {
            $event = $this->stripe->constructEvent($payload, $sig);
        } catch (Throwable $e) {
            error_log('[MulemaCare Stripe webhook] ' . $e->getMessage());
            return [
                'status' => 400,
                'body' => ['received' => false, 'error' => 'invalid_signature'],
            ];
        }

        $type = (string) ($event['type'] ?? '');
        $object = $event['data']['object'] ?? [];
        $handled = false;

        if ($type === 'checkout.session.completed') {
            $cssa = (string) ($object['metadata']['cssa_id'] ?? $object['client_reference_id'] ?? '');
            $activated = $this->memService->activateFromStripePayment([
                'cssa_id' => $cssa,
                'checkout_session_id' => (string) ($object['id'] ?? ''),
                'subscription_id' => (string) ($object['subscription'] ?? ''),
                'customer_id' => (string) ($object['customer'] ?? ''),
                'amount_total' => (int) ($object['amount_total'] ?? 0),
                'currency' => (string) ($object['currency'] ?? ''),
            ]);
            $handled = $activated !== null;
        } elseif ($type === 'invoice.paid') {
            $subId = (string) ($object['subscription'] ?? '');
            $metaCssa = (string) ($object['subscription_details']['metadata']['cssa_id'] ?? '');
            if ($metaCssa !== '') {
                $handled = $this->memService->activateFromStripePayment([
                    'cssa_id' => $metaCssa,
                    'subscription_id' => $subId,
                    'customer_id' => (string) ($object['customer'] ?? ''),
                ]) !== null;
            }
        } elseif (in_array($type, ['customer.subscription.deleted', 'customer.subscription.paused'], true)) {
            $subId = (string) ($object['id'] ?? '');
            $handled = $subId !== '' && $this->memService->suspendFromStripe($subId);
        }

        return [
            'status' => 200,
            'body' => [
                'received' => true,
                'handled' => $handled,
                'type' => $type,
                'timestamp' => time(),
            ],
        ];
    }

    /** Proxy ActionCenter list — session OPS + service token serveur (jamais de JWT client). */
    public function osProposals(): void {
        $this->session->start();
        if (!$this->session->isOps()) {
            $this->json(['ok' => false, 'error' => 'auth_required', 'proposals' => []], 401);
            return;
        }
        $token = $this->osServiceToken();
        $status = $_GET['status'] ?? 'pending';
        if (!$this->os->isEnabled()) {
            $this->json(['ok' => false, 'error' => 'Mutuelle OS disabled', 'proposals' => []], 503);
            return;
        }
        if ($token === '') {
            $this->json(['ok' => false, 'error' => 'OS service token missing', 'proposals' => []], 503);
            return;
        }
        $data = $this->os->listProposals($token, is_string($status) ? $status : 'pending');
        if ($data === null) {
            $this->json(['ok' => false, 'error' => 'OS unreachable', 'proposals' => []], 502);
            return;
        }
        $this->json(['ok' => true] + $data);
    }

    public function osDecideProposal(string $id): void {
        $this->session->start();
        if (!$this->session->isOps()) {
            $this->json(['ok' => false, 'error' => 'auth_required'], 401);
            return;
        }
        if (!$this->requireCsrf()) {
            return;
        }
        $token = $this->osServiceToken();
        $input = $this->input();
        if (!$this->os->isEnabled()) {
            $this->json(['ok' => false, 'error' => 'Mutuelle OS disabled'], 503);
            return;
        }
        if ($token === '') {
            $this->json(['ok' => false, 'error' => 'OS service token missing'], 503);
            return;
        }
        $decision = (string) ($input['decision'] ?? '');
        $data = $this->os->decideProposal(
            $token,
            $id,
            $decision,
            isset($input['note']) ? (string) $input['note'] : null
        );
        if ($data === null) {
            $this->json(['ok' => false, 'error' => 'OS decide failed'], 502);
            return;
        }
        $this->audit->record(
            'ops:' . ($this->session->opsEmail() ?? 'unknown'),
            'hitl_decide',
            null,
            ['proposal_id' => $id, 'decision' => $decision]
        );
        $this->json($data);
    }
}
