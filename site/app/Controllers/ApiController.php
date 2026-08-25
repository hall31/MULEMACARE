<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Services\QuoteService;
use App\Services\MembershipService;

/**
 * Contrôleur API pour Devis en Direct, Adhésions et Fast-Check Clinique
 */
class ApiController {
    private array $config;
    private QuoteService $quoteService;
    private MembershipService $memService;

    public function __construct() {
        $this->config = require __DIR__ . '/../../config.php';
        $this->quoteService = new QuoteService($this->config);
        $this->memService = new MembershipService($this->config);
    }

    /**
     * Calcule le devis en direct (Particuliers ou Entreprises)
     * POST /api/quote
     */
    public function quote(): void {
        if (!headers_sent()) {
            header('Content-Type: application/json; charset=utf-8');
        }
        $raw = file_get_contents('php://input');
        $input = (!empty($raw) ? json_decode($raw, true) : null) ?? $_POST;

        $type = $input['type'] ?? 'individual';

        if ($type === 'corporate') {
            $count = (int) ($input['employee_count'] ?? 10);
            $tier = $input['plan_tier'] ?? 'silver';
            $res = $this->quoteService->calculateCorporateQuote($count, $tier);
        } else {
            $planId = $input['plan_id'] ?? 'silver';
            $comp = $input['composition'] ?? 'family';
            $curr = $input['currency'] ?? 'XAF';
            $res = $this->quoteService->calculateIndividualQuote($planId, $comp, $curr);
        }

        echo json_encode([
            'success' => true,
            'data'    => $res,
        ]);
    }

    /**
     * Traite l'adhésion à la mutuelle et émet la carte digitale
     * POST /api/subscribe
     */
    public function subscribe(): void {
        if (!headers_sent()) {
            header('Content-Type: application/json; charset=utf-8');
        }
        $raw = file_get_contents('php://input');
        $input = (!empty($raw) ? json_decode($raw, true) : null) ?? $_POST;

        $name = trim($input['subscriber_name'] ?? '');
        $phone = trim($input['subscriber_phone'] ?? '');

        if (empty($name) || empty($phone)) {
            if (!headers_sent()) {
                http_response_code(400);
            }
            echo json_encode([
                'success' => false,
                'error'   => 'Veuillez renseigner votre nom complet et votre numéro WhatsApp.'
            ]);
            return;
        }

        $membership = $this->memService->createMembership($input);

        echo json_encode([
            'success'      => true,
            'cssa_id'      => $membership['cssa_id'],
            'plan_name'    => $membership['plan_name'],
            'price_label'  => $membership['price_label'],
            'card_url'     => $membership['card_url'],
            'whatsapp_url' => $membership['whatsapp_url'],
            'message'      => 'Adhésion validée ! Votre carte mutuelle CSSA est active avec tiers-payant immédiat.',
        ]);
    }

    /**
     * Fast-Check API pour les cliniques et pharmacies partenaires
     * GET /api/verify-card/{code}
     */
    public function verifyCard(string $code): void {
        if (!headers_sent()) {
            header('Content-Type: application/json; charset=utf-8');
        }
        $card = $this->memService->verifyCard($code);

        if (!$card) {
            if (!headers_sent()) {
                http_response_code(404);
            }
            echo json_encode([
                'success' => false,
                'error'   => 'Carte d\'assuré introuvable ou inactive.'
            ]);
            return;
        }

        echo json_encode([
            'success' => true,
            'data'    => $card,
        ]);
    }

    /**
     * Webhook de Paiement (Stripe / Orange Money / Wave / MTN)
     * POST /api/webhook
     */
    public function webhook(): void {
        if (!headers_sent()) {
            header('Content-Type: application/json; charset=utf-8');
        }
        echo json_encode(['received' => true, 'status' => 'acknowledged']);
    }
}
