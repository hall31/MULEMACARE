<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Services\QuoteService;
use App\Services\MembershipService;

/**
 * Contrôleur API pour Devis Automatisés, Adhésions, Fast-Check Clinique & Gestion Adhérents
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
     * Calcule ou enregistre un devis en direct (Particuliers ou Entreprises)
     * POST /api/quote
     */
    public function quote(): void {
        if (!headers_sent()) {
            header('Content-Type: application/json; charset=utf-8');
        }
        $raw = file_get_contents('php://input');
        $input = (!empty($raw) ? json_decode($raw, true) : null) ?? $_POST;

        $save = !empty($input['save']) || !empty($input['prospect_email']) || !empty($input['email']);

        if ($save) {
            $quote = $this->quoteService->createQuote($input);
            echo json_encode([
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

        $name = trim($input['subscriber_name'] ?? $input['name'] ?? '');
        $phone = trim($input['subscriber_phone'] ?? $input['phone'] ?? '');

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
            'portal_url'   => $membership['portal_url'],
            'whatsapp_url' => $membership['whatsapp_url'],
            'membership'   => $membership,
            'message'      => 'Félicitations ! Votre adhésion est validée et votre carte CSSA est active.',
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

        if ($card) {
            echo json_encode([
                'valid' => true,
                'card'  => $card,
            ]);
        } else {
            if (!headers_sent()) {
                http_response_code(404);
            }
            echo json_encode([
                'valid' => false,
                'error' => 'Numéro CSSA introuvable ou non conventionné.',
            ]);
        }
    }

    /**
     * Recherche d'un adhérent pour l'Espace Adhérent self-service
     * GET /api/adherent/lookup?q=...
     */
    public function lookupAdherent(): void {
        if (!headers_sent()) {
            header('Content-Type: application/json; charset=utf-8');
        }
        $q = trim($_GET['q'] ?? '');
        $member = $this->memService->getMemberByQuery($q);

        if ($member) {
            echo json_encode([
                'success' => true,
                'member'  => $member,
            ]);
        } else {
            if (!headers_sent()) {
                http_response_code(404);
            }
            echo json_encode([
                'success' => false,
                'error'   => 'Aucun compte trouvé avec cet identifiant.',
            ]);
        }
    }

    /**
     * Enregistrement d'une prise en charge tiers-payant par une clinique
     * POST /api/claim
     */
    public function createClaim(): void {
        if (!headers_sent()) {
            header('Content-Type: application/json; charset=utf-8');
        }
        $raw = file_get_contents('php://input');
        $input = (!empty($raw) ? json_decode($raw, true) : null) ?? $_POST;

        $cssaId = trim($input['cssa_id'] ?? '');
        if (empty($cssaId)) {
            if (!headers_sent()) http_response_code(400);
            echo json_encode(['success' => false, 'error' => 'N° CSSA obligatoire.']);
            return;
        }

        $claim = $this->memService->createClaim($input);
        echo json_encode([
            'success' => true,
            'claim'   => $claim,
            'message' => 'Bon de prise en charge ' . $claim['claim_ref'] . ' émis avec succès (0 F avancé par le patient).',
        ]);
    }

    /**
     * Modification du statut d'une carte (Espace Admin)
     * POST /api/admin/toggle-status
     */
    public function toggleMemberStatus(): void {
        if (!headers_sent()) {
            header('Content-Type: application/json; charset=utf-8');
        }
        $raw = file_get_contents('php://input');
        $input = (!empty($raw) ? json_decode($raw, true) : null) ?? $_POST;

        $cssaId = trim($input['cssa_id'] ?? '');
        $status = trim($input['status'] ?? 'ACTIVE');

        if (empty($cssaId)) {
            if (!headers_sent()) http_response_code(400);
            echo json_encode(['success' => false, 'error' => 'N° CSSA requis.']);
            return;
        }

        $updated = $this->memService->updateMemberStatus($cssaId, $status);
        echo json_encode([
            'success' => $updated,
            'status'  => strtoupper($status),
            'message' => 'Statut mis à jour pour ' . $cssaId,
        ]);
    }

    /**
     * Webhook pour notifications de paiement automatisées (Stripe / MoMo)
     * POST /api/webhook
     */
    public function webhook(): void {
        if (!headers_sent()) {
            header('Content-Type: application/json; charset=utf-8');
        }
        echo json_encode(['received' => true, 'timestamp' => time()]);
    }
}
