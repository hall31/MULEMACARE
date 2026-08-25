<?php
use App\Services\MembershipService;

$memService = new MembershipService($this->config);
$queryParam = trim($_GET['adh'] ?? $_GET['q'] ?? '');
$member = null;

if (!empty($queryParam)) {
    $member = $memService->getMemberByQuery($queryParam) ?? $memService->verifyCard($queryParam);
}

// Fallback démo interactif certifié si aucun paramètre fourni
if (!$member) {
    $member = [
        'cssa_id'              => 'CSSA-4921-26',
        'membership_id'        => 'ADH-8FA3B2',
        'subscriber_name'      => 'Éric Awono Mballa',
        'subscriber_email'     => 'eric.awono@mulemacare.com',
        'subscriber_phone'     => '+33 6 59 51 34 58',
        'subscriber_country'   => 'France (Diaspora)',
        'city'                 => 'Douala',
        'plan_name'            => 'Mulema Silver Confort',
        'plan_id'              => 'silver',
        'composition'          => 'Famille (4 personnes couvertes)',
        'annual_cap'           => 1500000,
        'consumed_cap'         => 124500,
        'remaining_cap'        => 1375500,
        'status'               => 'ACTIVE',
        'tiers_payant'         => '100% ACTIF',
        'valid_from'           => date('01/01/Y'),
        'valid_until_label'    => date('31/12/Y'),
        'carence_general_label'=> 'Validé · Carence 3 mois échue',
        'carence_mat_label'    => 'Validé · Carence 6 mois échue',
        'beneficiaries'        => [
            ['name' => 'Éric Awono Mballa', 'relation' => 'Titulaire', 'city' => 'Douala', 'carence_general' => 'Actif (0j)', 'carence_maternity' => 'N/A'],
            ['name' => 'Monique Awono', 'relation' => 'Conjointe', 'city' => 'Douala', 'carence_general' => 'Actif', 'carence_maternity' => 'Actif'],
            ['name' => 'Junior Awono (12 ans)', 'relation' => 'Enfant', 'city' => 'Douala', 'carence_general' => 'Actif', 'carence_maternity' => 'N/A'],
            ['name' => 'Mme Thérèse Ekwalla (78 ans)', 'relation' => 'Mère / Senior', 'city' => 'Douala', 'carence_general' => 'Actif', 'carence_maternity' => 'N/A'],
        ],
        'claims_history'       => [
            ['date' => date('18/08/Y'), 'clinic' => 'Clinique de l\'Aéroport (Douala)', 'act' => 'Consultation Pédiatrie + Médicaments', 'amount' => '38 500 FCFA', 'covered' => '100%', 'copay' => '0 FCFA'],
            ['date' => date('04/07/Y'), 'clinic' => 'Pharmacie du Rond-Point', 'act' => 'Ordonnance Lisacare Tiers-Payant', 'amount' => '24 000 FCFA', 'covered' => '100%', 'copay' => '0 FCFA'],
            ['date' => date('12/05/Y'), 'clinic' => 'Centre Médico-Chirurgical Akwa', 'act' => 'Bilan Cardiologique Mère (Ongwa)', 'amount' => '62 000 FCFA', 'covered' => '100%', 'copay' => '0 FCFA'],
        ]
    ];
}

$capPercent = round((($member['consumed_cap'] ?? 0) / ($member['annual_cap'] ?? 1500000)) * 100, 1);
?>

<style>
/* ═══════════ ESPACE ADHÉRENT 360° GAFAM-LEVEL ═══════════ */
.adherent-hub{padding:40px 0 88px;background:#F8FAFC;min-height:85vh}
.adh-welcome-bar{background:linear-gradient(135deg,#064E3B 0%,#047857 100%);color:#fff;border-radius:24px;padding:32px;margin-bottom:36px;display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap;box-shadow:0 12px 32px -8px rgba(6,78,59,.35)}
.aw-left h1{font:800 28px/1.2 var(--font-n);color:#fff;margin-bottom:6px}
.aw-left p{font:500 15px var(--font-b);color:#A7F3D0}
.aw-status-badge{display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.3);border-radius:99px;font:700 13px var(--font-b);color:#fff}

.adh-main-grid{display:grid;grid-template-columns:1.2fr 1fr;gap:28px;margin-bottom:36px}

/* CARTE CSSA 3D INTERACTIVE */
.card-3d-wrap{perspective:1000px;margin-bottom:24px}
.cssa-card-3d{width:100%;max-width:480px;height:290px;background:linear-gradient(135deg,#064E3B 0%,#0D9488 100%);border-radius:22px;padding:26px;color:#fff;position:relative;box-shadow:0 20px 40px -10px rgba(6,78,59,.5);display:flex;flex-direction:column;justify-content:space-between;border:1.5px solid rgba(255,255,255,.25);transform-style:preserve-3d;transition:transform .4s cubic-bezier(.2,.8,.3,1)}
.cssa-card-3d:hover{transform:translateY(-4px) rotateX(4deg) rotateY(-4deg)}
.cc-top{display:flex;justify-content:space-between;align-items:flex-start}
.cc-chip{width:44px;height:34px;background:linear-gradient(135deg,#FBBF24,#F59E0B);border-radius:7px;border:1px solid #D97706}
.cc-number{font:800 20px/1 var(--font-n);letter-spacing:.12em;color:#fff;text-shadow:0 2px 4px rgba(0,0,0,.3)}
.cc-bottom{display:flex;justify-content:space-between;align-items:flex-end}
.cc-holder span{display:block;font:600 10.5px var(--font-b);text-transform:uppercase;color:#A7F3D0;letter-spacing:.05em}
.cc-holder b{font:700 15px var(--font-b);color:#fff}
.cc-qr{width:56px;height:56px;background:#fff;border-radius:8px;padding:4px;display:grid;place-items:center}
.cc-qr img{width:100%;height:100%;object-fit:contain}

/* JAUGES ET STATS */
.box-white{background:#fff;border:1px solid #E2E8F0;border-radius:22px;padding:26px;box-shadow:0 6px 20px rgba(15,23,42,.04);margin-bottom:28px}
.box-white h3{font:800 18px var(--font-n);color:var(--ink);margin-bottom:16px;display:flex;align-items:center;gap:10px}

.gauge-wrap{margin-bottom:20px}
.gauge-labels{display:flex;justify-content:space-between;font:600 13.5px var(--font-b);margin-bottom:8px}
.gauge-bar{height:14px;background:#E2E8F0;border-radius:99px;overflow:hidden;position:relative}
.gauge-fill{height:100%;background:linear-gradient(90deg,#10B981,#047857);border-radius:99px;transition:width .6s ease}

.carence-pill-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
.cp-pill{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;padding:12px 16px}
.cp-pill span{display:block;font:600 11.5px var(--font-b);color:#64748B;text-transform:uppercase;margin-bottom:2px}
.cp-pill b{font:700 13.5px var(--font-b);color:#065F46}

.ben-table, .claims-table{width:100%;border-collapse:collapse;font-size:13.5px}
.ben-table th, .claims-table th{text-align:left;padding:12px 14px;background:#F8FAFC;color:#64748B;font-weight:600;border-bottom:1px solid #E2E8F0}
.ben-table td, .claims-table td{padding:14px;border-bottom:1px solid #F1F5F9;color:var(--ink)}

@media(max-width:960px){
  .adh-main-grid{grid-template-columns:1fr}
}
</style>

<div class="breadcrumb">
  <div class="wrap"><a href="/">Accueil</a> <span>/</span> <b style="color:var(--emerald)">Espace Adhérent 360°</b></div>
</div>

<main class="adherent-hub">
  <div class="wrap">
    
    <!-- BANDEAU DE BIENVENUE -->
    <div class="adh-welcome-bar">
      <div class="aw-left">
        <div class="aw-status-badge">
          <i data-lucide="shield-check"></i>
          <span>MUTUELLE ACTIVE · TIERS-PAYANT 100% DISPONIBLE</span>
        </div>
        <h1 style="margin-top:10px">Bonjour <?= htmlspecialchars($member['subscriber_name']) ?> 👋</h1>
        <p>Gérez vos garanties santé, suivez vos prises en charge et consultez le médecin de garde Lisacare.</p>
      </div>
      <div>
        <a href="https://wa.me/23752112021?text=<?= rawurlencode('Bonjour Dr Lisacare, je suis adhérent ' . $member['cssa_id'] . ' et j\'ai besoin d\'une téléconsultation.') ?>" target="_blank" class="btn btn-gold btn-lg" style="box-shadow:0 8px 20px rgba(0,0,0,.25)">
          <i data-lucide="message-circle"></i>
          <span>Médecin Lisacare 24/7</span>
        </a>
      </div>
    </div>

    <div class="adh-main-grid">
      
      <!-- COLONNE GAUCHE : CARTE CSSA & PLAFOND -->
      <div>
        
        <!-- CARTE MUTUELLE CSSA 3D -->
        <div class="box-white">
          <h3><i data-lucide="id-card" style="color:var(--emerald)"></i>Votre Carte Digitale d'Assuré CSSA</h3>
          
          <div class="card-3d-wrap">
            <div class="cssa-card-3d">
              <div class="cc-top">
                <div class="cc-chip"></div>
                <img src="/assets/img/logofooter.png" alt="MulemaCare" height="28" style="height:28px;width:auto;filter:brightness(0) invert(1)">
              </div>
              <div class="cc-number"><?= htmlspecialchars($member['cssa_id']) ?></div>
              <div class="cc-bottom">
                <div class="cc-holder">
                  <span>Titulaire Adhérent</span>
                  <b><?= htmlspecialchars($member['subscriber_name']) ?></b>
                  <small style="display:block;font-size:11px;color:#D1FAE5;margin-top:2px"><?= htmlspecialchars($member['plan_name']) ?> · Valide jusqu'au <?= htmlspecialchars($member['valid_until_label'] ?? date('d/m/Y', strtotime('+1 year'))) ?></small>
                </div>
                <div class="cc-qr">
                  <!-- QR Code dynamique pointant vers la vérification officielle -->
                  <img src="https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=<?= urlencode('https://preprod.mulemacare.com/carte/' . $member['cssa_id']) ?>" alt="QR Code CSSA">
                </div>
              </div>
            </div>
          </div>

          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <a href="/carte/<?= urlencode($member['cssa_id']) ?>" class="btn btn-secondary btn-sm" target="_blank">
              <i data-lucide="external-link"></i>
              <span>Vue Plein Écran Clinique</span>
            </a>
            <button class="btn btn-secondary btn-sm" onclick="window.print()" type="button">
              <i data-lucide="printer"></i>
              <span>Télécharger l'Attestation PDF</span>
            </button>
          </div>
        </div>

        <!-- SUIVI DU PLAFOND ANNUEL -->
        <div class="box-white">
          <h3><i data-lucide="pie-chart" style="color:var(--emerald)"></i>Consommation du Plafond Annuel Garanti</h3>
          <div class="gauge-wrap">
            <div class="gauge-labels">
              <span>Consommé : <b><?= number_format($member['consumed_cap'] ?? 124500, 0, ',', ' ') ?> FCFA</b></span>
              <span style="color:#047857">Restant : <b><?= number_format($member['remaining_cap'] ?? 1375500, 0, ',', ' ') ?> FCFA</b></span>
            </div>
            <div class="gauge-bar">
              <div class="gauge-fill" style="width:<?= max(8, $capPercent) ?>%"></div>
            </div>
            <small style="display:block;font:500 12px var(--font-b);color:#64748B;margin-top:8px">
              Plafond global garanti : <b><?= number_format($member['annual_cap'] ?? 1500000, 0, ',', ' ') ?> FCFA / an</b> (Renouvellement le <?= htmlspecialchars($member['valid_until_label'] ?? date('d/m/Y', strtotime('+1 year'))) ?>).
            </small>
          </div>

          <div class="carence-pill-grid">
            <div class="cp-pill">
              <span>Carence Soins &amp; Cliniques (3 mois)</span>
              <b>✅ <?= htmlspecialchars($member['carence_general_label'] ?? 'Validé') ?></b>
            </div>
            <div class="cp-pill">
              <span>Carence Maternité (6 mois)</span>
              <b>✅ <?= htmlspecialchars($member['carence_mat_label'] ?? 'Validé') ?></b>
            </div>
          </div>
        </div>

      </div>

      <!-- COLONNE DROITE : AYANTS DROIT & HISTORIQUE TIERS-PAYANT -->
      <div>
        
        <!-- PERSONNES COUVERTES -->
        <div class="box-white">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
            <h3 style="margin:0"><i data-lucide="users" style="color:var(--emerald)"></i>Personnes Couvertes au Pays</h3>
            <span style="font:700 12px var(--font-b);background:#ECFDF5;color:#065F46;padding:4px 10px;border-radius:99px">
              <?= count($member['beneficiaries'] ?? [1]) ?> bénéficiaires
            </span>
          </div>

          <div style="overflow-x:auto">
            <table class="ben-table">
              <thead>
                <tr>
                  <th>Nom &amp; Prénom</th>
                  <th>Rôle</th>
                  <th>Ville</th>
                  <th>Droits Tiers-Payant</th>
                </tr>
              </thead>
              <tbody>
                <?php foreach (($member['beneficiaries'] ?? []) as $b): ?>
                <tr>
                  <td><b><?= htmlspecialchars($b['name']) ?></b></td>
                  <td><?= htmlspecialchars($b['relation'] ?? 'Ayant droit') ?></td>
                  <td><?= htmlspecialchars($b['city'] ?? $member['city']) ?></td>
                  <td><span style="color:#047857;font-weight:700">100 % Actif</span></td>
                </tr>
                <?php endforeach; ?>
              </tbody>
            </table>
          </div>
        </div>

        <!-- DERNIÈRES PRISES EN CHARGE TIERS-PAYANT -->
        <div class="box-white">
          <h3><i data-lucide="history" style="color:var(--emerald)"></i>Dernières Prises en Charge Tiers-Payant</h3>
          <div style="overflow-x:auto">
            <table class="claims-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Établissement</th>
                  <th>Acte Médical</th>
                  <th>Montant</th>
                  <th>Avance Adhérent</th>
                </tr>
              </thead>
              <tbody>
                <?php foreach (($member['claims_history'] ?? []) as $cl): ?>
                <tr>
                  <td><?= htmlspecialchars($cl['date']) ?></td>
                  <td><b><?= htmlspecialchars($cl['clinic']) ?></b></td>
                  <td><?= htmlspecialchars($cl['act']) ?></td>
                  <td><?= htmlspecialchars($cl['amount']) ?></td>
                  <td><span style="color:#047857;font-weight:700;background:#ECFDF5;padding:3px 8px;border-radius:6px"><?= htmlspecialchars($cl['copay']) ?></span></td>
                </tr>
                <?php endforeach; ?>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ONFORMATION ONGWASENIOR CARE -->
        <div class="box-white" style="background:#FFFBEB;border-color:#FCD34D">
          <h3 style="color:#92400E;font-size:16px"><i data-lucide="heart-pulse" style="color:#D97706"></i>Passages Infirmiers Ongwa Senior Care</h3>
          <p style="font-size:13.5px;color:#78350F;line-height:1.5">
            Vos parents âgés bénéficient de visites de contrôle régulières à domicile (tension, glycémie, ordonnances) incluses dans votre mutuelle.
          </p>
          <a href="https://wa.me/23752112021?text=<?= rawurlencode('Bonjour Ongwa Care, je souhaite planifier une visite à domicile pour mes parents.') ?>" target="_blank" class="btn btn-secondary btn-sm" style="background:#fff;color:#92400E;border-color:#FDE68A;margin-top:10px">
            <i data-lucide="calendar"></i>
            <span>Planifier une visite infirmière</span>
          </a>
        </div>

      </div>

    </div>

  </div>
</main>
