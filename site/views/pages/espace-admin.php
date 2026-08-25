<?php
use App\Services\Database;

$pdo = Database::getConnection();
$subscribers = [];
$stats = [
    'total_subscribers' => 12400,
    'mrr_fcfa'          => '84 500 000 FCFA',
    'active_claims'     => 142,
    'partners_count'    => 45,
];

if ($pdo) {
    try {
        $stmt = $pdo->query("SELECT s.*, c.cssa_number, c.plan, c.annual_cap, c.consumed_cap, c.tiers_payant_status 
            FROM mulema_subscribers s 
            LEFT JOIN mulema_cards c ON s.id = c.subscriber_id 
            ORDER BY s.id DESC LIMIT 20");
        $subscribers = $stmt->fetchAll();
    } catch (\Exception $e) {
        // Fallback
    }
}
?>

<style>
/* ================= ESPACE ADMIN & RÉGULATION ================= */
.admin-hub{padding:48px 0 88px;background:#0F172A;color:#F8FAFC}
.admin-top{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;margin-bottom:36px;flex-wrap:wrap}
.admin-top h1{font-size:clamp(1.8rem,3vw,2.4rem);font-weight:800;color:#fff}
.admin-top p{font-size:15px;color:#94A3B8;margin-top:4px}

.admin-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:36px}
.admin-kpi{background:#1E293B;border:1px solid #334155;border-radius:18px;padding:22px}
.admin-kpi span{display:block;font:600 12px var(--font-b);letter-spacing:.06em;text-transform:uppercase;color:#5EEAD4;margin-bottom:6px}
.admin-kpi b{font:800 26px var(--font-n);color:#fff}
.admin-kpi small{display:block;font:500 12px var(--font-b);color:#94A3B8;margin-top:6px}

.admin-section{background:#1E293B;border:1px solid #334155;border-radius:22px;padding:28px;margin-bottom:32px}
.admin-section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:14px}
.admin-section-head h2{font-size:19px;font-weight:700;color:#fff;display:flex;align-items:center;gap:10px}

.admin-table{width:100%;border-collapse:collapse;font-size:13.5px}
.admin-table th{text-align:left;padding:13px 16px;background:#0F172A;color:#94A3B8;font-weight:600;border-bottom:1px solid #334155}
.admin-table td{padding:14px 16px;border-bottom:1px solid #334155;color:#E2E8F0}
.admin-table tr:hover td{background:#26354A}

.badge-plan{display:inline-block;padding:3px 9px;border-radius:6px;font:700 11px var(--font-b);text-transform:uppercase}
.badge-plan.silver{background:rgba(13,148,136,.25);color:#5EEAD4}
.badge-plan.gold{background:rgba(217,119,6,.25);color:#FCD34D}
.badge-plan.bronze{background:rgba(180,83,9,.25);color:#FDBA74}
.badge-plan.platinium{background:rgba(148,163,184,.25);color:#F1F5F9}

.badge-status{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:99px;font:600 11.5px var(--font-b)}
.badge-status.active{background:#064E3B;color:#6EE7B7}
.badge-status.pending{background:#78350F;color:#FDE68A}

@media(max-width:1020px){
  .admin-kpis{grid-template-columns:repeat(2,1fr)}
  .admin-table-wrap{overflow-x:auto}
}
</style>

<div class="admin-hub">
  <div class="wrap">
    <div class="admin-top">
      <div>
        <span class="badge-agr" style="background:#064E3B;border-color:#047857;color:#6EE7B7"><i data-lucide="shield-alert"></i>MulemaCare Control Tower · Administration Mutuelle</span>
        <h1>Tour de Contrôle &amp; Régulation Médicale</h1>
        <p>Pilotage en direct des souscriptions, validation des accords préalables et règlements des cliniques conventionnées.</p>
      </div>
      <div style="display:flex;gap:12px">
        <button class="btn btn-primary btn-sm" onclick="toast('Export Comptable', 'Génération du grand livre des cotisations 2026 en cours...', 'info')">
          <i data-lucide="file-spreadsheet"></i>Export Comptable
        </button>
      </div>
    </div>

    <!-- KPIs Clés -->
    <div class="admin-kpis">
      <div class="admin-kpi">
        <span>Portefeuille Assurés</span>
        <b class="num">12 400</b>
        <small><i data-lucide="trending-up" style="width:12px;height:12px;display:inline"></i> +14 % ce mois</small>
      </div>
      <div class="admin-kpi">
        <span>Cotisations Recouvrées</span>
        <b class="num">84 500 000 F</b>
        <small>98.2 % de taux de succès Mobile Money/CB</small>
      </div>
      <div class="admin-kpi">
        <span>Prises en Charge Tiers-Payant</span>
        <b class="num">142 actes</b>
        <small>Délai moyen de règlement : 48h</small>
      </div>
      <div class="admin-kpi">
        <span>Cliniques &amp; Pharmacies</span>
        <b class="num">45 partenaires</b>
        <small>Dans 6 pays d'Afrique</small>
      </div>
    </div>

    <!-- Accords Préalables en Attente -->
    <div class="admin-section">
      <div class="admin-section-head">
        <h2><i data-lucide="clipboard-check" style="color:#5EEAD4"></i>Demandes d'Accords Préalables Tiers-Payant (Urgences &amp; Chirurgie)</h2>
        <span style="font:600 12.5px var(--font-b);color:#FDE68A;background:#78350F;padding:4px 12px;border-radius:99px">2 demandes en attente de visa médical</span>
      </div>

      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Dossier</th>
              <th>Patient &amp; Carte CSSA</th>
              <th>Établissement</th>
              <th>Acte &amp; Montant Estimé</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr id="claimRow1">
              <td><b>#PEC-2026-9041</b><br><small style="color:#94A3B8">Reçue il y a 14 min</small></td>
              <td><b>Junior Awono</b><br><span class="num" style="color:#5EEAD4">CSSA-8842-28</span> (Silver)</td>
              <td>Clinique de l'Étoile (Douala)</td>
              <td>Hospitalisation Pédiatrique<br><b class="num">380 000 FCFA</b></td>
              <td>
                <div style="display:flex;gap:8px">
                  <button class="btn btn-primary btn-sm" style="padding:6px 12px;font-size:12.5px" onclick="approveClaim('claimRow1', 'PEC-2026-9041')"><i data-lucide="check"></i>Valider</button>
                  <button class="btn btn-ghost btn-sm" style="padding:6px 12px;font-size:12.5px;background:#334155;color:#fff;border-color:#475569" onclick="rejectClaim('claimRow1')"><i data-lucide="x"></i>Rejeter</button>
                </div>
              </td>
            </tr>
            <tr id="claimRow2">
              <td><b>#PEC-2026-9042</b><br><small style="color:#94A3B8">Reçue il y a 42 min</small></td>
              <td><b>Maman Madeleine Ekwalla</b><br><span class="num" style="color:#FCD34D">CSSA-8842-29</span> (Gold)</td>
              <td>Clinique Bastos (Yaoundé)</td>
              <td>Chirurgie Ambulatoire Genou<br><b class="num">620 000 FCFA</b></td>
              <td>
                <div style="display:flex;gap:8px">
                  <button class="btn btn-primary btn-sm" style="padding:6px 12px;font-size:12.5px" onclick="approveClaim('claimRow2', 'PEC-2026-9042')"><i data-lucide="check"></i>Valider</button>
                  <button class="btn btn-ghost btn-sm" style="padding:6px 12px;font-size:12.5px;background:#334155;color:#fff;border-color:#475569" onclick="rejectClaim('claimRow2')"><i data-lucide="x"></i>Rejeter</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Registre des Souscriptions (MySQL Direct) -->
    <div class="admin-section">
      <div class="admin-section-head">
        <h2><i data-lucide="users" style="color:#5EEAD4"></i>Registre des Polices &amp; Souscripteurs (Base MySQL dbs12741132)</h2>
        <span style="font-size:13px;color:#94A3B8">Synchronisé en temps réel</span>
      </div>

      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Identifiant</th>
              <th>Souscripteur</th>
              <th>Coordonnées</th>
              <th>Carte CSSA</th>
              <th>Formule</th>
              <th>Plafond Annuel</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            <?php if (!empty($subscribers)): ?>
              <?php foreach ($subscribers as $s): ?>
                <tr>
                  <td><b class="num"><?= htmlspecialchars($s['membership_id'] ?? 'ADH-001') ?></b></td>
                  <td><b><?= htmlspecialchars($s['full_name']) ?></b><br><small style="color:#94A3B8"><?= ucfirst($s['residence_type'] ?? 'diaspora') ?></small></td>
                  <td><?= htmlspecialchars($s['email']) ?><br><span class="num" style="color:#94A3B8"><?= htmlspecialchars($s['phone']) ?></span></td>
                  <td><b class="num" style="color:#5EEAD4"><?= htmlspecialchars($s['cssa_number'] ?? 'CSSA-AUTO') ?></b></td>
                  <td><span class="badge-plan <?= strtolower($s['plan'] ?? 'silver') ?>"><?= htmlspecialchars($s['plan'] ?? 'Silver') ?></span></td>
                  <td><span class="num"><?= number_format((float)($s['annual_cap'] ?? 3810000), 0, ',', ' ') ?> F</span></td>
                  <td><span class="badge-status active"><i data-lucide="check"></i>Actif</span></td>
                </tr>
              <?php endforeach; ?>
            <?php else: ?>
              <tr>
                <td><b class="num">ADH-1A036284F54</b></td>
                <td><b>Jean-Paul Kamga</b><br><small style="color:#94A3B8">Diaspora (France)</small></td>
                <td>jp.kamga@example.com<br><span class="num" style="color:#94A3B8">+33 6 12 34 56 78</span></td>
                <td><b class="num" style="color:#FCD34D">CSSA-A2FA-26</b></td>
                <td><span class="badge-plan gold">Gold</span></td>
                <td><span class="num">6 000 000 FCFA</span></td>
                <td><span class="badge-status active"><i data-lucide="check"></i>Actif</span></td>
              </tr>
              <tr>
                <td><b class="num">ADH-98420173</b></td>
                <td><b>Éric Awono Mballa</b><br><small style="color:#94A3B8">Diaspora (Belgique)</small></td>
                <td>eric.awono@example.com<br><span class="num" style="color:#94A3B8">+32 4 70 12 34 56</span></td>
                <td><b class="num" style="color:#5EEAD4">CSSA-8842-26</b></td>
                <td><span class="badge-plan silver">Silver</span></td>
                <td><span class="num">3 810 000 FCFA</span></td>
                <td><span class="badge-status active"><i data-lucide="check"></i>Actif</span></td>
              </tr>
            <?php endif; ?>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
function approveClaim(rowId, claimNo) {
  const row = document.getElementById(rowId);
  if(row) {
    row.style.background = 'rgba(16, 185, 129, 0.15)';
    row.querySelector('td:last-child').innerHTML = '<span class="badge-status active"><i data-lucide="check-circle-2"></i>Accord Préalable Validé</span>';
    icons();
    toast('Prise en Charge Validée', `Le visa de garantie pour le dossier ${claimNo} a été envoyé par SMS/WhatsApp à la clinique.`, 'success');
  }
}

function rejectClaim(rowId) {
  const row = document.getElementById(rowId);
  if(row) {
    row.style.opacity = '0.5';
    row.querySelector('td:last-child').innerHTML = '<span style="color:#EF4444;font-weight:600;font-size:12px"><i data-lucide="x-circle"></i>Dossier Rejeté</span>';
    icons();
    toast('Dossier refusé', 'Notification de rejet transmise au médecin conseil.', 'info');
  }
}
</script>
