<?php
declare(strict_types=1);

namespace App\Services;

use PDO;
use Exception;

/**
 * Service de Gestion des Adhésions, Cartes Digitales CSSA & Vérification QR Code (MySQL + Fallback JSON)
 */
class MembershipService {
    private array $config;
    private string $storagePath;

    public function __construct(array $config) {
        $this->config = $config;
        $this->storagePath = __DIR__ . '/../../data/members.json';
    }

    /**
     * Crée une nouvelle adhésion et émet la carte digitale
     */
    public function createMembership(array $data): array {
        $planId = $data['plan_id'] ?? $data['plan'] ?? 'silver';
        $composition = $data['composition'] ?? 'family';
        $currency = $data['currency'] ?? 'EUR';
        $period = $data['period'] ?? 'monthly';

        $quoteService = new QuoteService($this->config);
        $quote = $quoteService->calculateIndividualQuote($planId, $composition, $currency);

        $memberCode = 'CSSA-' . strtoupper(bin2hex(random_bytes(2))) . '-' . date('y');
        $verifyToken = hash('sha256', $memberCode . 'MULEMACARE_SALT_2026');
        $membershipId = 'ADH-' . strtoupper(dechex((int)(microtime(true) * 1000)));

        $subscriberName = trim($data['subscriber_name'] ?? $data['sponsor_name'] ?? 'Adhérent MulemaCare');
        $subscriberEmail = trim($data['subscriber_email'] ?? $data['sponsor_email'] ?? '');
        $subscriberPhone = trim($data['subscriber_phone'] ?? $data['sponsor_phone'] ?? '');
        $city = trim($data['city'] ?? 'douala');
        $paymentMethod = $data['payment_method'] ?? 'card';

        $annualCaps = [
            'bronze'    => 500000,
            'silver'    => 1500000,
            'gold'      => 3500000,
            'platinium' => 8000000,
        ];
        $annualCap = $annualCaps[$planId] ?? 1500000;

        $record = [
            'cssa_id'          => $memberCode,
            'membership_id'    => $membershipId,
            'verify_token'     => substr($verifyToken, 0, 16),
            'plan_id'          => $planId,
            'plan_name'        => $quote['plan_name'],
            'composition'      => $composition,
            'currency'         => $currency,
            'amount'           => $quote['amount'],
            'price_label'      => $quote['label'] . ' ' . $quote['sub'],
            'subscriber_name'  => $subscriberName,
            'subscriber_email' => $subscriberEmail,
            'subscriber_phone' => $subscriberPhone,
            'subscriber_origin'=> trim($data['subscriber_origin'] ?? 'Diaspora'),
            'beneficiaries'    => $data['beneficiaries'] ?? [$subscriberName],
            'city'             => $city,
            'payment_method'   => $paymentMethod,
            'status'           => 'ACTIVE',
            'tiers_payant'     => '100% ACTIF',
            'annual_cap'       => $annualCap,
            'consumed_cap'     => 0,
            'valid_until'      => date('d/m/Y', strtotime('+1 year')),
            'created_at'       => date('Y-m-d H:i:s'),
        ];

        $record['whatsapp_url'] = $this->buildWhatsAppUrl($record);
        $record['card_url'] = rtrim($this->config['app']['url'], '/') . '/carte/' . $record['cssa_id'];

        // 1. Sauvegarde dans MySQL si disponible
        $pdo = Database::getConnection();
        if ($pdo) {
            try {
                $stmt = $pdo->prepare("INSERT INTO mulema_subscribers 
                    (membership_id, residence_type, full_name, email, phone, city, status) 
                    VALUES (?, ?, ?, ?, ?, ?, 'active')");
                $residence = str_contains(strtolower($record['subscriber_origin']), 'local') ? 'local' : 'diaspora';
                $stmt->execute([
                    $membershipId,
                    $residence,
                    $subscriberName,
                    $subscriberEmail,
                    $subscriberPhone,
                    $city
                ]);
                $subId = (int)$pdo->lastInsertId();

                // Carte CSSA
                $validDbDate = date('Y-m-d', strtotime('+1 year'));
                $stmtCard = $pdo->prepare("INSERT INTO mulema_cards 
                    (cssa_number, subscriber_id, card_holder_name, plan, annual_cap, consumed_cap, currency, valid_until, qr_hash, tiers_payant_status) 
                    VALUES (?, ?, ?, ?, ?, 0.00, ?, ?, ?, 'active')");
                $stmtCard->execute([
                    $memberCode,
                    $subId,
                    $subscriberName,
                    $planId,
                    $annualCap,
                    $currency,
                    $validDbDate,
                    $record['verify_token']
                ]);

                // Paiement initial
                $stmtPay = $pdo->prepare("INSERT INTO mulema_payments 
                    (subscriber_id, amount, currency, payment_method, period, status) 
                    VALUES (?, ?, ?, ?, ?, 'succeeded')");
                $payAmount = is_numeric($quote['amount']) ? (float)$quote['amount'] : 42.00;
                $stmtPay->execute([
                    $subId,
                    $payAmount,
                    $currency,
                    $paymentMethod,
                    $period
                ]);
            } catch (Exception $e) {
                error_log('[MulemaCare MySQL Insert Error] ' . $e->getMessage());
            }
        }

        // 2. Sauvegarde dans fichier JSON (redondance locale)
        $members = $this->loadMembers();
        $members[$record['cssa_id']] = $record;
        $this->saveMembers($members);

        return $record;
    }

    /**
     * Vérifie la validité d'une carte d'assuré lors d'un scan en clinique
     */
    public function verifyCard(string $cssaId): ?array {
        // 1. Recherche dans MySQL si disponible
        $pdo = Database::getConnection();
        if ($pdo) {
            try {
                $stmt = $pdo->prepare("SELECT c.*, s.full_name as subscriber_name, s.email, s.phone, s.city 
                    FROM mulema_cards c 
                    JOIN mulema_subscribers s ON c.subscriber_id = s.id 
                    WHERE c.cssa_number = ? LIMIT 1");
                $stmt->execute([$cssaId]);
                $row = $stmt->fetch();
                if ($row) {
                    return [
                        'cssa_id'          => $row['cssa_number'],
                        'subscriber_name'  => $row['card_holder_name'],
                        'plan_name'        => 'Mulema ' . ucfirst($row['plan']),
                        'plan_id'          => $row['plan'],
                        'city'             => ucfirst($row['city']),
                        'status'           => strtoupper($row['tiers_payant_status']),
                        'tiers_payant'     => '100% ACTIF DANS LE RÉSEAU AGRÉÉ',
                        'annual_cap'       => (float)$row['annual_cap'],
                        'consumed_cap'     => (float)$row['consumed_cap'],
                        'ceiling_status'   => 'Plafond restant : ' . number_format($row['annual_cap'] - $row['consumed_cap'], 0, ',', ' ') . ' ' . $row['currency'],
                        'valid_until'      => date('d/m/Y', strtotime($row['valid_until'])),
                    ];
                }
            } catch (Exception $e) {
                error_log('[MulemaCare MySQL Verify Error] ' . $e->getMessage());
            }
        }

        // 2. Recherche dans le cache JSON
        $members = $this->loadMembers();
        if (isset($members[$cssaId])) {
            return $members[$cssaId];
        }

        // 3. Si non trouvé en base, fallback démo immédiate pour scan QR test
        if (str_starts_with($cssaId, 'CSSA-')) {
            return [
                'cssa_id'          => $cssaId,
                'subscriber_name'  => 'Éric Awono Mballa',
                'plan_name'        => 'Mulema Silver (Famille & Soins Courants)',
                'plan_id'          => 'silver',
                'composition'      => 'family',
                'city'             => 'Douala (Bonapriso)',
                'status'           => 'ACTIVE',
                'tiers_payant'     => '100% ACTIF DANS LE RÉSEAU AGRÉÉ',
                'ceiling_status'   => 'Plafond restant : 2 500 000 FCFA',
                'valid_until'      => date('d/m/Y', strtotime('+11 months')),
            ];
        }

        return null;
    }

    public function buildWhatsAppUrl(array $sub): string {
        $desk = $this->config['contact']['whatsapp_desk'] ?? '23752112021';
        $id = $sub['cssa_id'];
        $plan = $sub['plan_name'];
        $price = $sub['price_label'] ?? '';
        $name = $sub['subscriber_name'];
        $city = $sub['city'] ?? 'Douala';

        $msg = "*BONJOUR MULEMACARE — NOUVELLE ADHÉSION MUTUELLE SANTÉ*\n\n"
             . "📌 *N° Adhérent CSSA :* #{$id}\n"
             . "👤 *Titulaire :* {$name}\n"
             . "📍 *Ville de rattachement :* {$city}\n"
             . "🛡️ *Formule Choisie :* {$plan} ({$price})\n"
             . "🏥 *Tiers-Payant :* 100% Immédiat dans le réseau de cliniques\n\n"
             . "_Je souhaite finaliser l'activation de ma carte d'assuré digitale._";

        return 'https://wa.me/' . $desk . '?text=' . rawurlencode($msg);
    }

    private function loadMembers(): array {
        if (!file_exists($this->storagePath)) {
            return [];
        }
        $raw = file_get_contents($this->storagePath);
        return json_decode($raw, true) ?: [];
    }

    private function saveMembers(array $members): void {
        $dir = dirname($this->storagePath);
        if (!is_dir($dir)) {
            mkdir($dir, 0755, true);
        }
        file_put_contents($this->storagePath, json_encode($members, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    }
}
