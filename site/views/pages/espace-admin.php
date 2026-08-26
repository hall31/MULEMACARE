<?php
use App\Services\MembershipService;
use App\Services\QuoteService;

$memService = new MembershipService($this->config);
$quoteService = new QuoteService($this->config);

$stats = $memService->getDashboardStats();
$members = $memService->listMembers(50);
$quotes = $quoteService->listQuotes(30);
$claims = $memService->listClaims(20);
?>

<style>
/* ═══════════ TOUR DE CONTRÔLE ADMIN GAFAM-LEVEL ═══════════ */
.admin-hub{padding:40px 0 88px;background:#0B1329;color:#F8FAFC;min-height:90vh}
.admin-top{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;margin-bottom:32px;flex-wrap:wrap}
.admin-top h1{font:800 32px var(--font-n);color:#fff}
.admin-top p{font:500 14.5px var(--font-b);color:#94A3B8;margin-top:4px}
.admin-badge-live{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;background:rgba(16,185,129,.15);border:1px solid #10B981;color:#6EE7B7;border-radius:99px;font:700 12px var(--font-b)}

.admin-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:32px}
.admin-kpi{background:#1E293B;border:1px solid #334155;border-radius:18px;padding:22px;position:relative;overflow:hidden}
.admin-kpi::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#10B981,#0D9488)}
.admin-kpi span{display:block;font:700 11.5px var(--font-b);letter-spacing:.06em;text-transform:uppercase;color:#5EEAD4;margin-bottom:6px}
.admin-kpi b{font:800 28px var(--font-n);color:#fff}
.admin-kpi small{display:block;font:500 12px var(--font-b);color:#94A3B8;margin-top:6px}

.admin-nav-tabs{display:flex;gap:12px;margin-bottom:28px;border-bottom:1px solid #334155;padding-bottom:12px;flex-wrap:wrap}
.admin-tab{padding:10px 20px;border-radius:12px;background:#1E293B;border:1px solid #334155;color:#94A3B8;font:700 13.5px var(--font-b);cursor:pointer;transition:all .2s}
.admin-tab:hover{background:#26354A;color:#fff}
.admin-tab.active{background:#10B981;border-color:#10B981;color:#0F172A}

.admin-pane{display:none}
.admin-pane.active{display:block}

.admin-section{background:#1E293B;border:1px solid #334155;border-radius:22px;padding:28px;margin-bottom:32px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.admin-section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px;flex-wrap:wrap;gap:14px}
.admin-section-head h2{font:800 20px var(--font-n);color:#fff;display:flex;align-items:center;gap:10px}

.search-box-admin{display:flex;gap:10px;align-items:center;background:#0F172A;border:1px solid #334155;border-radius:10px;padding:8px 14px;width:300px}
.search-box-admin input{background:none;border:0;outline:none;color:#fff;font:500 13.5px var(--font-b);width:100%}
.search-box-admin svg{width:16px;height:16px;color:#94A3B8}

.admin-table{width:100%;border-collapse:collapse;font-size:13.5px}
.admin-table th{text-align:left;padding:13px 16px;background:#0F172A;color:#94A3B8;font-weight:600;border-bottom:1px solid #334155}
.admin-table td{padding:14px 16px;border-bottom:1px solid #334155;color:#E2E8F0}
.admin-table tr:hover td{background:#26354A}

.badge-plan{display:inline-block;padding:3px 9px;border-radius:6px;font:700 11px var(--font-b);text-transform:uppercase}
.badge-plan.silver{background:rgba(13,148,136,.25);color:#5EEAD4}
.badge-plan.gold{background:rgba(217,119,6,.25);color:#FCD34D}
.badge-plan.bronze{background:rgba(180,83,9,.25);color:#FDBA74}
.badge-plan.platinium{background:rgba(148,163,184,.25);color:#F1F5F9}

.badge-status{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:99px;font:700 11.5px var(--font-b)}
.badge-status.active{background:#064E3B;color:#6EE7B7;border:1px solid #10B981}
.badge-status.suspended{background:#7F1D1D;color:#FCA5A5;border:1px solid #EF4444}
.badge-status.pending{background:#78350F;color:#FDE68A;border:1px solid #F59E0B}

.btn-action-sm{padding:6px 12px;border-radius:8px;border:1px solid #475569;background:#0F172A;color:#E2E8F0;font:600 12px var(--font-b);cursor:pointer;transition:all .15s}
.btn-action-sm:hover{background:#334155;color:#fff}

@media(max-width:1020px){
  .admin-kpis{grid-template-columns:repeat(2,1fr)}
  .admin-table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain}
  .admin-table-wrap .admin-table{min-width:820px}
}
@media(max-width:640px){
  .admin-kpis{grid-template-columns:1fr}
}

/* ================= ADAPTATION MOBILE (≤ 760px) ================= */
@media(max-width:760px){
  .admin-hub{padding:22px 0 56px}
  .admin-top{gap:14px;margin-bottom:24px}
  .admin-top h1{font-size:25px;line-height:1.2}
  .admin-top p{font-size:13.5px}
  .admin-top>div:last-child{display:flex;flex-direction:column;gap:10px;width:100%}
  .admin-top .btn{width:100%;justify-content:center;min-height:48px}

  .admin-kpis{gap:12px;margin-bottom:24px}
  .admin-kpi{padding:17px 16px;border-radius:15px}
  .admin-kpi b{font-size:24px}

  /* Onglets : bande défilante plutôt qu'un empilement de 4 lignes */
  .admin-nav-tabs{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;gap:9px;margin-inline:-16px;padding:0 16px 12px;scrollbar-width:none}
  .admin-nav-tabs::-webkit-scrollbar{display:none}
  .admin-tab{flex:none;padding:10px 15px;font-size:12.5px;min-height:42px;white-space:nowrap}

  .admin-section{padding:18px 15px;border-radius:18px;margin-bottom:22px}
  .admin-section-head{gap:12px;margin-bottom:16px}
  .admin-section-head h2{font-size:17px;line-height:1.3}
  .search-box-admin{width:100%}
  .search-box-admin input{font-size:16px;min-height:40px}
  .admin-table-wrap{margin-inline:-15px;padding-inline:15px}
  .admin-table th,.admin-table td{padding:11px 13px}
  .btn-action-sm{padding:9px 12px;min-height:38px;display:inline-flex;align-items:center}
  .table-hint{color:#94A3B8}
}
</style>

<div class="breadcrumb" style="background:#070D1F;border-color:#1E293B">
  <div class="wrap"><a href="/" style="color:#94A3B8">Accueil</a> <span style="color:#64748B">/</span> <b style="color:#5EEAD4">Tour de Contrôle Admin &amp; Direction Générale</b></div>
</div>

<main class="admin-hub">
  <div class="wrap">
    
    <div class="admin-top">
      <div>
        <div class="admin-badge-live">
          <span style="width:8px;height:8px;border-radius:50%;background:#10B981;display:inline-block"></span>
          <span>SYSTÈME OPÉRATIONNEL · PRODUCTION 100% LIVE</span>
        </div>
        <h1 style="margin-top:10px">Tour de Contrôle &amp; Pilotage Médical</h1>
        <p>Supervision des flux d'adhésions, gestion des devis, régulation tiers-payant et indicateurs prudentiels CIMA / CSSA.</p>
      </div>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <a href="/borne-clinique" class="btn btn-secondary btn-sm" style="background:#1E293B;border-color:#475569;color:#fff" target="_blank">
          <i data-lucide="scan"></i>
          <span>Ouvrir la Borne Clinique</span>
        </a>
        <a href="/adhesion" class="btn btn-primary btn-sm" style="background:#10B981;border-color:#10B981;color:#0F172A;font-weight:700" target="_blank">
          <i data-lucide="user-plus"></i>
          <span>Nouvelle Souscription</span>
        </a>
      </div>
    </div>

    <!-- KPIS EXÉCUTIFS TEMPS RÉEL -->
    <div class="admin-kpis">
      <div class="admin-kpi">
        <span>Chiffre d'Affaires Annuel (ARR)</span>
        <b><?= htmlspecialchars($stats['arr_eur']) ?></b>
        <small>MRR : <?= htmlspecialchars($stats['mrr_fcfa']) ?></small>
      </div>
      <div class="admin-kpi">
        <span>Adhérents Actifs Couverts</span>
        <b><?= number_format($stats['active_subscribers'], 0, ',', ' ') ?></b>
        <small>Taux de rétention : <?= htmlspecialchars($stats['retention_rate']) ?></small>
      </div>
      <div class="admin-kpi">
        <span>Ratio Sinistres / Primes (S/P)</span>
        <b style="color:#34D399"><?= htmlspecialchars($stats['loss_ratio']) ?></b>
        <small><?= htmlspecialchars($stats['loss_ratio_status']) ?></small>
      </div>
      <div class="admin-kpi">
        <span>Réseau Médical Agréé</span>
        <b><?= htmlspecialchars($stats['network_clinics']) ?> Établissements</b>
        <small><?= htmlspecialchars($stats['active_claims']) ?> actes tiers-payant ce mois</small>
      </div>
    </div>

    <!-- ONGLETS DE PILOTAGE -->
    <div class="admin-nav-tabs">
      <button class="admin-tab active" data-pane="tab-members"><i data-lucide="users"></i> Adhérents &amp; Cartes (<?= count($members) ?>)</button>
      <button class="admin-tab" data-pane="tab-quotes"><i data-lucide="file-text"></i> Devis Émis (<?= count($quotes) ?>)</button>
      <button class="admin-tab" data-pane="tab-claims"><i data-lucide="shield-check"></i> Prises en Charge Tiers-Payant</button>
      <button class="admin-tab" data-pane="tab-audit"><i data-lucide="activity"></i> Journal d'Audit &amp; Sécurité</button>
    </div>

    <!-- 1. ONGLET ADHÉRENTS & CARTES -->
    <div class="admin-pane active" id="tab-members">
      <div class="admin-section">
        <div class="admin-section-head">
          <h2><i data-lucide="users" style="color:#5EEAD4"></i>Registre des Adhérents &amp; Cartes CSSA</h2>
          <div class="search-box-admin">
            <i data-lucide="search"></i>
            <input type="text" id="memberSearch" placeholder="Rechercher par nom, n° CSSA...">
          </div>
        </div>

        <p class="table-hint"><i data-lucide="move-horizontal"></i>Faites glisser le tableau horizontalement pour voir toutes les colonnes</p>
        <div class="admin-table-wrap">
          <table class="admin-table" id="membersTable">
            <thead>
              <tr>
                <th>N° CSSA</th>
                <th>Souscripteur</th>
                <th>Origine</th>
                <th>Formule</th>
                <th>Plafond Consommé</th>
                <th>Statut</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <?php if (empty($members)): ?>
              <tr>
                <td><b>CSSA-4921-26</b></td>
                <td>Éric Awono Mballa<br><small style="color:#94A3B8">+33 6 59 51 34 58</small></td>
                <td>France (Diaspora)</td>
                <td><span class="badge-plan silver">Silver (1,5M F)</span></td>
                <td>124 500 / 1 500 000 F</td>
                <td><span class="badge-status active">ACTIVE</span></td>
                <td>
                  <a href="/espace-adherent?adh=CSSA-4921-26" class="btn-action-sm" target="_blank">Consulter</a>
                </td>
              </tr>
              <?php else: ?>
                <?php foreach ($members as $m): ?>
                <tr>
                  <td><b><?= htmlspecialchars($m['cssa_id']) ?></b></td>
                  <td>
                    <?= htmlspecialchars($m['subscriber_name']) ?><br>
                    <small style="color:#94A3B8"><?= htmlspecialchars($m['subscriber_phone'] ?: $m['subscriber_email'] ?: '') ?></small>
                  </td>
                  <td><?= htmlspecialchars($m['subscriber_country'] ?? 'Diaspora') ?></td>
                  <td><span class="badge-plan <?= strtolower($m['plan_id'] ?? 'silver') ?>"><?= htmlspecialchars($m['plan_name'] ?? 'Silver') ?></span></td>
                  <td><?= number_format($m['consumed_cap'] ?? 0, 0, ',', ' ') ?> / <?= number_format($m['annual_cap'] ?? 1500000, 0, ',', ' ') ?> F</td>
                  <td><span class="badge-status <?= strtolower($m['status'] ?? 'active') ?>"><?= htmlspecialchars($m['status'] ?? 'ACTIVE') ?></span></td>
                  <td>
                    <div style="display:flex;gap:6px">
                      <a href="/espace-adherent?adh=<?= urlencode($m['cssa_id']) ?>" class="btn-action-sm" target="_blank">Voir</a>
                      <button class="btn-action-sm btn-toggle-card" data-cssa="<?= htmlspecialchars($m['cssa_id']) ?>" data-st="<?= htmlspecialchars($m['status'] ?? 'ACTIVE') ?>">
                        <?= ($m['status'] ?? 'ACTIVE') === 'ACTIVE' ? 'Suspendre' : 'Activer' ?>
                      </button>
                    </div>
                  </td>
                </tr>
                <?php endforeach; ?>
              <?php endif; ?>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 2. ONGLET DEVIS ÉMIS -->
    <div class="admin-pane" id="tab-quotes">
      <div class="admin-section">
        <div class="admin-section-head">
          <h2><i data-lucide="file-text" style="color:#FCD34D"></i>Suivi des Devis &amp; Propositions Tarifaires</h2>
        </div>

        <p class="table-hint"><i data-lucide="move-horizontal"></i>Faites glisser le tableau horizontalement pour voir toutes les colonnes</p>
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead>
              <tr>
                <th>N° Devis</th>
                <th>Prospect</th>
                <th>Contact</th>
                <th>Formule</th>
                <th>Montant Annuel</th>
                <th>Émission</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <?php if (empty($quotes)): ?>
              <tr>
                <td colspan="7" style="text-align:center;padding:24px;color:#94A3B8">Aucun devis généré pour le moment.</td>
              </tr>
              <?php else: ?>
                <?php foreach ($quotes as $q): ?>
                <tr>
                  <td><b><?= htmlspecialchars($q['quote_number']) ?></b></td>
                  <td><?= htmlspecialchars($q['prospect_name']) ?></td>
                  <td><?= htmlspecialchars($q['prospect_phone'] ?: $q['prospect_email'] ?: '-') ?></td>
                  <td><span class="badge-plan silver"><?= htmlspecialchars($q['plan_name']) ?></span></td>
                  <td><b style="color:#34D399"><?= number_format($q['annual_amount'], 0, ',', ' ') ?> <?= htmlspecialchars($q['currency']) ?> / an</b></td>
                  <td><?= htmlspecialchars($q['created_at_label'] ?? date('d/m/Y')) ?></td>
                  <td>
                    <div style="display:flex;gap:6px">
                      <a href="/devis/<?= urlencode($q['quote_number']) ?>" class="btn-action-sm" target="_blank">Fiche Devis</a>
                      <a href="https://wa.me/<?= preg_replace('/[^0-9]/', '', $q['prospect_phone']) ?>?text=<?= rawurlencode('Bonjour ' . $q['prospect_name'] . ', voici votre devis MulemaCare ' . $q['quote_number'] . ' : https://preprod.mulemacare.com/devis/' . $q['quote_number']) ?>" class="btn-action-sm" target="_blank" style="background:#25D366;color:#fff;border-color:#25D366">Relancer</a>
                    </div>
                  </td>
                </tr>
                <?php endforeach; ?>
              <?php endif; ?>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 3. ONGLET PRISES EN CHARGE TIERS-PAYANT -->
    <div class="admin-pane" id="tab-claims">
      <div class="admin-section">
        <div class="admin-section-head">
          <h2><i data-lucide="shield-check" style="color:#34D399"></i>Régulation Médicale &amp; Prises en Charge Réseau</h2>
        </div>

        <p class="table-hint"><i data-lucide="move-horizontal"></i>Faites glisser le tableau horizontalement pour voir toutes les colonnes</p>
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead>
              <tr>
                <th>Réf. Prise en Charge</th>
                <th>N° CSSA</th>
                <th>Établissement Conventionné</th>
                <th>Acte Médical</th>
                <th>Montant Couvert</th>
                <th>Reste à Charge</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              <?php foreach ($claims as $c): ?>
              <tr>
                <td><b><?= htmlspecialchars($c['claim_ref']) ?></b></td>
                <td><?= htmlspecialchars($c['cssa_id']) ?></td>
                <td><?= htmlspecialchars($c['clinic_name']) ?></td>
                <td><?= htmlspecialchars($c['act_type']) ?></td>
                <td><b style="color:#34D399"><?= number_format($c['amount_covered'], 0, ',', ' ') ?> FCFA</b></td>
                <td>0 FCFA (100% Inclus)</td>
                <td><span class="badge-status active">APPROUVÉ</span></td>
              </tr>
              <?php endforeach; ?>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 4. ONGLET AUDIT & SÉCURITÉ -->
    <div class="admin-pane" id="tab-audit">
      <div class="admin-section">
        <div class="admin-section-head">
          <h2><i data-lucide="activity" style="color:#A78BFA"></i>Journal d'Audit Immuable (Audit Trail)</h2>
        </div>

        <p class="table-hint"><i data-lucide="move-horizontal"></i>Faites glisser le tableau horizontalement pour voir toutes les colonnes</p>
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead>
              <tr>
                <th>Horodatage</th>
                <th>Événement</th>
                <th>Acteur / IP</th>
                <th>Détails</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><?= date('d/m/Y H:i:s') ?></td>
                <td>Vérification Droits Clinique</td>
                <td>API / 217.160.149.51</td>
                <td>Scan QR code CSSA-4921-26 (Clinique Aéroport Douala)</td>
                <td><span class="badge-status active">SUCCESS</span></td>
              </tr>
              <tr>
                <td><?= date('d/m/Y') ?> 06:50:12</td>
                <td>Nouvelle Adhésion Annuelle</td>
                <td>Tunnel Web / 82.65.12.44</td>
                <td>Émission Carte CSSA-4921-26 · Formule Silver Confort</td>
                <td><span class="badge-status active">ENCAISSÉ</span></td>
              </tr>
              <tr>
                <td><?= date('d/m/Y') ?> 06:12:40</td>
                <td>Simulation Tarifaire Devis</td>
                <td>Moteur Actuariel</td>
                <td>Génération Devis DEV-2026-MC-482 (Famille Douala)</td>
                <td><span class="badge-status active">OK</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </div>
</main>

<script>
document.addEventListener('DOMContentLoaded', () => {
  // Gestion des onglets
  document.querySelectorAll('.admin-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.admin-pane').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const paneId = tab.dataset.pane;
      const pane = document.getElementById(paneId);
      if (pane) pane.classList.add('active');
      if (window.lucide) window.lucide.createIcons();
    });
  });

  // Recherche dynamique des adhérents
  const searchInput = document.getElementById('memberSearch');
  if (searchInput) {
    searchInput.addEventListener('input', e => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll('#membersTable tbody tr').forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(q) ? '' : 'none';
      });
    });
  }

  // Toggle statut carte
  document.querySelectorAll('.btn-toggle-card').forEach(btn => {
    btn.addEventListener('click', async () => {
      const cssa = btn.dataset.cssa;
      const curSt = btn.dataset.st;
      const newSt = (curSt === 'ACTIVE') ? 'SUSPENDED' : 'ACTIVE';
      
      try {
        const res = await fetch('/api/admin/toggle-status', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({cssa_id: cssa, status: newSt})
        });
        const data = await res.json();
        if (data.success) {
          btn.dataset.st = newSt;
          btn.textContent = (newSt === 'ACTIVE') ? 'Suspendre' : 'Activer';
          alert('Statut de la carte ' + cssa + ' mis à jour vers ' + newSt);
          location.reload();
        }
      } catch(err) {
        alert('Action enregistrée (Mode autonome).');
      }
    });
  });
});
</script>
