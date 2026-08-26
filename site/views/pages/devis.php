<?php
use App\Services\QuoteService;

$quoteService = new QuoteService($this->config);
$quoteId = $quoteId ?? ($_GET['id'] ?? '');
$quote = $quoteService->getQuote($quoteId);

if (!$quote) {
    // Devis démo par défaut si aucun trouvé
    $quote = $quoteService->createQuote([
        'prospect_name'  => 'Prospect Démo MulemaCare',
        'prospect_email' => 'contact@mulemacare.com',
        'prospect_phone' => '+33 6 59 51 34 58',
        'plan_id'        => 'silver',
        'composition'    => 'family',
        'currency'       => 'EUR',
        'cycle'          => 'annual',
    ]);
}

$calc = $quote['calculation'] ?? [];
$isAnnual = ($quote['cycle'] ?? 'annual') === 'annual';
?>

<style>
/* ═══════════ FICHE OFFICIELLE DE DEVIS ═══════════ */
.quote-page{padding:48px 0 80px;background:#F8FAFC}
.quote-card{background:#fff;border-radius:24px;border:1px solid #E2E8F0;box-shadow:0 12px 36px rgba(15,23,42,.06);padding:40px;max-width:920px;margin:0 auto;position:relative}
.quote-badge-top{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;background:#ECFDF5;border:1px solid rgba(16,185,129,.3);color:#065F46;border-radius:99px;font:700 12px var(--font-b);text-transform:uppercase;letter-spacing:.05em;margin-bottom:20px}
.quote-head{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;border-bottom:1.5px solid #E2E8F0;padding-bottom:28px;margin-bottom:28px;flex-wrap:wrap}
.quote-title h1{font:800 28px/1.2 var(--font-n);color:var(--ink);margin-bottom:6px}
.quote-title p{font:500 14.5px var(--font-b);color:var(--ink-2)}
.quote-meta-box{background:#F1F5F9;border-radius:14px;padding:16px 20px;text-align:right}
.quote-meta-box b{display:block;font:800 17px var(--font-n);color:var(--ink);letter-spacing:.02em}
.quote-meta-box span{font:500 12.5px var(--font-b);color:#64748B}

.quote-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:32px}
.quote-box{background:#FAFBFD;border:1px solid #E2E8F0;border-radius:16px;padding:22px}
.quote-box h3{font:700 15px var(--font-b);color:var(--ink);margin-bottom:12px;display:flex;align-items:center;gap:8px}
.quote-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px dashed #E2E8F0;font-size:14px}
.quote-row:last-child{border-bottom:0}
.quote-row span{color:#64748B}
.quote-row b{color:var(--ink);font-weight:600}

.quote-pricing-banner{background:linear-gradient(135deg,#064E3B 0%,#047857 100%);color:#fff;border-radius:18px;padding:28px;margin-bottom:32px;display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap}
.qpb-left span{display:block;font:600 13px var(--font-b);color:#A7F3D0;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.qpb-left h2{font:800 32px/1 var(--font-n);color:#fff}
.qpb-left small{display:block;font:500 13px var(--font-b);color:#D1FAE5;margin-top:6px}
.qpb-right{display:flex;gap:12px}

.quote-carence-box{background:#FFFBEB;border:1.5px solid #FCD34D;border-radius:16px;padding:20px 24px;margin-bottom:32px}
.quote-carence-box h4{font:700 14.5px var(--font-b);color:#92400E;display:flex;align-items:center;gap:8px;margin-bottom:10px}
.quote-carence-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;font-size:13px}
.qc-item{background:#fff;border-radius:10px;padding:10px 14px;border:1px solid #FDE68A}
.qc-item b{display:block;color:#78350F;margin-bottom:2px}
.qc-item span{color:#92400E;font-size:12px}

.quote-actions{display:flex;justify-content:space-between;align-items:center;gap:16px;padding-top:20px;border-top:1.5px solid #E2E8F0;flex-wrap:wrap}
.quote-actions-left{display:flex;gap:12px}

@media print {
  header.site, footer.site, .quote-actions, .breadcrumb{display:none !important}
  .quote-page{padding:0;background:#fff}
  .quote-card{border:0;box-shadow:none;padding:0;max-width:100%}
}
@media(max-width:768px){
  .quote-grid{grid-template-columns:1fr}
  .quote-carence-grid{grid-template-columns:1fr}
  .quote-meta-box{text-align:left}
}

/* ================= ADAPTATION MOBILE (≤ 760px) ================= */
@media(max-width:760px){
  .quote-page{padding:24px 0 56px}
  .quote-card{padding:20px 16px;border-radius:18px}
  .quote-head{gap:16px;padding-bottom:20px;margin-bottom:20px}
  .quote-title h1{font-size:22px}
  .quote-title p{font-size:13.5px}
  .quote-meta-box{width:100%;padding:14px 16px}
  .quote-grid{gap:14px;margin-bottom:22px}
  .quote-box{padding:17px 15px}
  .quote-row{flex-direction:column;align-items:flex-start;gap:2px;font-size:13.5px}

  .quote-pricing-banner{padding:20px 17px;gap:16px;margin-bottom:22px;border-radius:16px}
  .qpb-left h2{font-size:27px}
  .qpb-right{width:100%;flex-direction:column;gap:10px}
  .qpb-right .btn{width:100%;justify-content:center;min-height:50px}

  .quote-carence-box{padding:16px 15px;margin-bottom:22px}

  .quote-actions{flex-direction:column;align-items:stretch;gap:12px}
  .quote-actions-left{flex-direction:column;gap:10px;min-width:0}
  .quote-actions-left .btn{width:100%;justify-content:center;min-height:50px}
  .quote-actions>div:last-child{display:flex;justify-content:center;padding-top:4px}
}
</style>

<div class="breadcrumb">
  <div class="wrap"><a href="/">Accueil</a> <span>/</span> <a href="/#simulateur">Devis</a> <span>/</span> <b style="color:var(--emerald)"><?= htmlspecialchars($quote['quote_number']) ?></b></div>
</div>

<main class="quote-page">
  <div class="wrap">
    <div class="quote-card">
      <div class="quote-badge-top">
        <i data-lucide="file-check-2"></i>
        <span>Devis Officiel MulemaCare · Mutuelle Santé Agréée</span>
      </div>

      <div class="quote-head">
        <div class="quote-title">
          <h1>Proposition Tarifaire &amp; Garanties</h1>
          <p>Offre personnalisée pour la prise en charge de votre santé et celle de vos proches au pays.</p>
        </div>
        <div class="quote-meta-box">
          <b>N° <?= htmlspecialchars($quote['quote_number']) ?></b>
          <span>Émis le <?= htmlspecialchars($quote['created_at_label'] ?? date('d/m/Y')) ?></span>
          <span style="display:block;color:#047857;font-weight:600">Valable jusqu'au <?= htmlspecialchars($quote['valid_until_label'] ?? date('d/m/Y', strtotime('+30 days'))) ?></span>
        </div>
      </div>

      <div class="quote-grid">
        <div class="quote-box">
          <h3><i data-lucide="user-check"></i>Titulaire / Souscripteur</h3>
          <div class="quote-row">
            <span>Nom complet :</span>
            <b><?= htmlspecialchars($quote['prospect_name']) ?></b>
          </div>
          <div class="quote-row">
            <span>Contact :</span>
            <b><?= htmlspecialchars($quote['prospect_phone'] ?: $quote['prospect_email'] ?: 'Non renseigné') ?></b>
          </div>
          <div class="quote-row">
            <span>Ville de soins :</span>
            <b><?= htmlspecialchars(ucfirst($quote['city'] ?? 'Douala')) ?></b>
          </div>
          <div class="quote-row">
            <span>Organisme émetteur :</span>
            <b>MulemaCare CSSA n° 045</b>
          </div>
        </div>

        <div class="quote-box">
          <h3><i data-lucide="shield-check"></i>Formule &amp; Couverture</h3>
          <div class="quote-row">
            <span>Formule choisie :</span>
            <b style="color:var(--emerald-800)"><?= htmlspecialchars($quote['plan_name']) ?></b>
          </div>
          <div class="quote-row">
            <span>Composition :</span>
            <b><?= htmlspecialchars(ucfirst($quote['composition'] ?? 'Famille')) ?></b>
          </div>
          <div class="quote-row">
            <span>Plafond annuel garanti :</span>
            <b><?= htmlspecialchars($calc['ceiling_label'] ?? '1 500 000 FCFA / an') ?></b>
          </div>
          <div class="quote-row">
            <span>Tiers-payant réseau :</span>
            <b style="color:#047857">100 % Sans Avance de Frais</b>
          </div>
        </div>
      </div>

      <div class="quote-carence-box">
        <h4><i data-lucide="clock"></i>Délais de Carence Actuariels &amp; Déclenchement des Prises en Charge</h4>
        <div class="quote-carence-grid">
          <div class="qc-item">
            <b>⚡ Accidents &amp; Urgences :</b>
            <span>0 jour (Immédiat dès l'adhésion)</span>
          </div>
          <div class="qc-item">
            <b>⏳ Soins Courants &amp; Cliniques :</b>
            <span>3 mois (90 jours)</span>
          </div>
          <div class="qc-item">
            <b>🤰 Femmes Enceintes &amp; Maternité :</b>
            <span>6 mois (180 jours)</span>
          </div>
        </div>
      </div>

      <div class="quote-pricing-banner">
        <div class="qpb-left">
          <span>Cotisation Mutuelle Annuelle</span>
          <h2><?= number_format($quote['annual_amount'], 0, ',', ' ') ?> <?= htmlspecialchars($quote['currency']) ?> <small style="display:inline;font-size:18px;font-weight:600">/ an</small></h2>
          <small>Soit l'équivalent de <b><?= number_format($calc['monthly_equivalent'] ?? ($quote['annual_amount']/12), 0, ',', ' ') ?> <?= htmlspecialchars($quote['currency']) ?> / mois</b> (10 % d'économie incluses).</small>
        </div>
        <div class="qpb-right">
          <a href="/adhesion?quote=<?= urlencode($quote['quote_number']) ?>" class="btn btn-gold btn-lg" style="box-shadow:0 8px 20px rgba(0,0,0,.25);font-size:16px">
            <i data-lucide="check-circle-2"></i>
            <span>Souscrire Immédiatement</span>
          </a>
        </div>
      </div>

      <div class="quote-actions">
        <div class="quote-actions-left">
          <button class="btn btn-secondary" onclick="window.print()" type="button">
            <i data-lucide="printer"></i>
            <span>Imprimer / PDF</span>
          </button>
          <a class="btn btn-secondary" href="https://wa.me/23752112021?text=<?= rawurlencode('Bonjour MulemaCare, je souhaite finaliser mon devis ' . $quote['quote_number']) ?>" target="_blank" rel="noopener">
            <i data-lucide="message-circle"></i>
            <span>Partager sur WhatsApp</span>
          </a>
        </div>
        <div>
          <a href="/#simulateur" class="link-arrow">
            <i data-lucide="calculator"></i>
            <span>Recalculer un autre profil</span>
          </a>
        </div>
      </div>
    </div>
  </div>
</main>
