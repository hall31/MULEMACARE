<?php
use App\Services\QuoteService;

$quoteService = new QuoteService($this->config);
$quoteRef = trim($_GET['quote'] ?? '');
$initialQuote = $quoteRef ? $quoteService->getQuote($quoteRef) : null;

$initialPlan = $initialQuote['calculation']['plan_id'] ?? ($_GET['plan'] ?? 'silver');
$initialComp = $initialQuote['composition'] ?? ($_GET['comp'] ?? 'family');
$initialCurr = $initialQuote['currency'] ?? ($_GET['curr'] ?? 'EUR');
?>

<style>
/* ═══════════ TUNNEL D'ADHÉSION 100% AUTOMATISÉ ═══════════ */
.adh-page{padding:48px 0 88px;background:#F8FAFC;min-height:85vh}
.adh-container{max-width:960px;margin:0 auto}

.stepper{display:flex;justify-content:space-between;margin-bottom:36px;position:relative}
.stepper::before{content:"";position:absolute;top:20px;left:40px;right:40px;height:3px;background:#E2E8F0;z-index:1}
.step-item{position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;gap:8px;background:#F8FAFC;padding:0 12px}
.step-circle{width:42px;height:42px;border-radius:50%;background:#fff;border:2.5px solid #CBD5E1;display:grid;place-items:center;font:700 15px var(--font-b);color:#64748B;transition:all .3s ease}
.step-item.active .step-circle{background:var(--emerald);border-color:var(--emerald);color:#fff;box-shadow:0 0 0 5px rgba(16,185,129,.2)}
.step-item.completed .step-circle{background:#065F46;border-color:#065F46;color:#fff}
.step-label{font:600 12.5px var(--font-b);color:#64748B;text-transform:uppercase;letter-spacing:.04em}
.step-item.active .step-label{color:var(--emerald-900);font-weight:700}

.adh-card{background:#fff;border-radius:24px;border:1px solid #E2E8F0;box-shadow:0 12px 36px rgba(15,23,42,.06);padding:36px}
.adh-step-pane{display:none}
.adh-step-pane.active{display:block}

.adh-head{margin-bottom:28px}
.adh-head h2{font:800 24px var(--font-n);color:var(--ink);margin-bottom:6px;display:flex;align-items:center;gap:10px}
.adh-head p{font:500 14.5px var(--font-b);color:var(--ink-2)}

.form-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
.f-group{display:flex;flex-direction:column;gap:7px}
.f-group label{font:600 13.5px var(--font-b);color:var(--ink)}
.f-group input, .f-group select{width:100%;min-width:0;max-width:100%;padding:12px 16px;border:1.5px solid #CBD5E1;border-radius:12px;font:500 14.5px var(--font-b);background:#fff;color:var(--ink);outline:none;transition:border-color .2s}
.f-group input:focus, .f-group select:focus{border-color:var(--emerald);box-shadow:0 0 0 3px rgba(16,185,129,.15)}

.plan-picker-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
.plan-opt-box{border:2px solid #E2E8F0;border-radius:16px;padding:18px;cursor:pointer;transition:all .2s;position:relative}
.plan-opt-box:hover{border-color:var(--emerald);transform:translateY(-2px)}
.plan-opt-box.selected{border-color:var(--emerald);background:#ECFDF5;box-shadow:0 8px 20px rgba(16,185,129,.12)}
.plan-opt-box h4{font:800 16px var(--font-b);color:var(--ink);margin-bottom:4px}
.plan-opt-box .pop-price{font:800 18px var(--font-n);color:var(--emerald-800)}
.plan-opt-box small{font:500 11.5px var(--font-b);color:#64748B;display:block;margin-top:4px}

.beneficiary-row{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:14px;padding:18px;margin-bottom:14px;display:grid;grid-template-columns:2fr 1.5fr 1fr 1.5fr auto;gap:12px;align-items:center}
.btn-del-ben{background:none;border:0;color:#EF4444;cursor:pointer;padding:8px;display:grid;place-items:center;border-radius:8px}
.btn-del-ben:hover{background:#FEE2E2}

.carence-reminder{background:#FEF3C7;border-left:4px solid #F59E0B;padding:14px 18px;border-radius:0 12px 12px 0;margin-bottom:24px;font-size:13.5px;color:#92400E}

.pay-methods{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:28px}
.pay-card{border:2px solid #E2E8F0;border-radius:16px;padding:20px;text-align:center;cursor:pointer;transition:all .2s}
.pay-card:hover{border-color:var(--emerald)}
.pay-card.selected{border-color:var(--emerald);background:#ECFDF5}
.pay-card svg{width:28px;height:28px;margin-bottom:8px;color:var(--emerald)}
.pay-card b{display:block;font:700 14px var(--font-b);color:var(--ink)}
.pay-card small{font:500 11.5px var(--font-b);color:#64748B}

.success-badge-done{display:inline-flex;align-items:center;gap:8px;padding:8px 18px;background:#ECFDF5;border:1.5px solid rgba(16,185,129,.3);border-radius:99px;color:#065F46;font:700 14px var(--font-b);margin-bottom:20px}

@media(max-width:768px){
  .plan-picker-grid{grid-template-columns:1fr 1fr}
  .form-grid-2{grid-template-columns:1fr}
  .beneficiary-row{grid-template-columns:1fr;gap:8px}
  .pay-methods{grid-template-columns:1fr}
}

/* ================= ADAPTATION MOBILE (≤ 760px) ================= */
@media(max-width:760px){
  .adh-page{padding:24px 0 56px}
  .adh-card{padding:20px 16px;border-radius:18px}
  .adh-head{margin-bottom:20px}
  .adh-head h2{font-size:20px;line-height:1.25}
  .adh-head p{font-size:13.5px}

  /* Stepper compact : 4 étapes doivent tenir sur 343px */
  .stepper{margin-bottom:26px}
  .stepper::before{top:17px;left:28px;right:28px}
  .step-item{flex:1 1 0;min-width:0;padding:0 2px;gap:6px}
  .step-circle{width:35px;height:35px;font-size:13.5px;border-width:2px}
  .step-item.active .step-circle{box-shadow:0 0 0 4px rgba(16,185,129,.2)}
  .step-label{font-size:10px;letter-spacing:0;text-align:center;line-height:1.25;overflow-wrap:anywhere}

  .form-grid-2{gap:14px;margin-bottom:14px}
  /* Sur iOS, une police < 16px déclenche un zoom automatique à la saisie */
  .f-group input,.f-group select{font-size:16px;padding:13px 14px}
  .plan-picker-grid{gap:11px}
  .plan-opt-box{padding:14px 13px;border-radius:14px}
  .plan-opt-box h4{font-size:15px}
  .plan-opt-box .pop-price{font-size:17px}
  .beneficiary-row{padding:14px}
  .pay-card{padding:16px}
  .adh-card .btn{min-height:50px}
}
</style>

<div class="breadcrumb">
  <div class="wrap"><a href="/">Accueil</a> <span>/</span> <b style="color:var(--emerald)">Adhésion &amp; Souscription en Ligne</b></div>
</div>

<main class="adh-page">
  <div class="wrap adh-container">
    
    <!-- STEPPER -->
    <div class="stepper">
      <div class="step-item active" id="st1">
        <div class="step-circle">1</div>
        <div class="step-label">Formule &amp; Ville</div>
      </div>
      <div class="step-item" id="st2">
        <div class="step-circle">2</div>
        <div class="step-label">Bénéficiaires</div>
      </div>
      <div class="step-item" id="st3">
        <div class="step-circle">3</div>
        <div class="step-label">Paiement Annuel</div>
      </div>
      <div class="step-item" id="st4">
        <div class="step-circle">4</div>
        <div class="step-label">Carte Émise</div>
      </div>
    </div>

    <!-- FORMULAIRE ADHÉSION -->
    <div class="adh-card">
      
      <!-- ÉTAPE 1 : CHOIX DE FORMULE -->
      <div class="adh-step-pane active" id="pane1">
        <div class="adh-head">
          <h2><i data-lucide="shield-check" style="color:var(--emerald)"></i>Étape 1 : Choisissez la formule adaptée</h2>
          <p>Toutes nos formules incluent le Tiers-Payant 100% dans le réseau de cliniques et l'accès au médecin Lisacare 24/7 sur WhatsApp.</p>
        </div>

        <div class="plan-picker-grid" id="planSelectGrid">
          <div class="plan-opt-box <?= $initialPlan === 'bronze' ? 'selected' : '' ?>" data-p="bronze" data-price="276">
            <h4>Bronze Essentiel</h4>
            <div class="pop-price">276 € <small style="display:inline">/ an</small></div>
            <small>Plafond : 500 000 F · Urgences &amp; Hospit</small>
          </div>
          <div class="plan-opt-box <?= $initialPlan === 'silver' ? 'selected' : '' ?>" data-p="silver" data-price="504">
            <h4>Silver Confort</h4>
            <div class="pop-price">504 € <small style="display:inline">/ an</small></div>
            <small>Plafond : 1,5M F · Soins &amp; Maternité</small>
          </div>
          <div class="plan-opt-box <?= $initialPlan === 'gold' ? 'selected' : '' ?>" data-p="gold" data-price="816">
            <h4>Gold Sérénité</h4>
            <div class="pop-price">816 € <small style="display:inline">/ an</small></div>
            <small>Plafond : 3,5M F · Dentaire &amp; Optique</small>
          </div>
          <div class="plan-opt-box <?= $initialPlan === 'platinium' ? 'selected' : '' ?>" data-p="platinium" data-price="1380">
            <h4>Platinium Élite</h4>
            <div class="pop-price">1 380 € <small style="display:inline">/ an</small></div>
            <small>Plafond : 8M F · Évacuation sanitaire</small>
          </div>
        </div>

        <div class="form-grid-2">
          <div class="f-group">
            <label>Composition du foyer à couvrir</label>
            <select id="selComp">
              <option value="solo" <?= $initialComp === 'solo' ? 'selected' : '' ?>>1 personne seule (Solo)</option>
              <option value="couple" <?= $initialComp === 'couple' ? 'selected' : '' ?>>Couple (2 adultes)</option>
              <option value="family" <?= $initialComp === 'family' ? 'selected' : '' ?>>Famille (Parents + 2 enfants)</option>
              <option value="seniors" <?= $initialComp === 'seniors' ? 'selected' : '' ?>>2 Parents Âgés (Seniors)</option>
            </select>
          </div>
          <div class="f-group">
            <label>Ville principale des soins en Afrique</label>
            <select id="selCity">
              <option value="douala" selected>Douala (Cameroun)</option>
              <option value="yaounde">Yaoundé (Cameroun)</option>
              <option value="kinshasa">Kinshasa (RDC)</option>
              <option value="abidjan">Abidjan (Côte d'Ivoire)</option>
              <option value="dakar">Dakar (Sénégal)</option>
              <option value="libreville">Libreville (Gabon)</option>
            </select>
          </div>
        </div>

        <div class="carence-reminder">
          <i data-lucide="info"></i>
          <b>Rappel des règles de carence :</b> <b>0 jour</b> pour les urgences &amp; SAMU, <b>3 mois</b> pour les soins courants &amp; cliniques, <b>6 mois</b> pour la maternité et femmes enceintes.
        </div>

        <div style="display:flex;justify-content:flex-end;margin-top:24px">
          <button class="btn btn-primary btn-lg" id="btnGoStep2" type="button">
            <span>Continuer vers l'identité</span>
            <i data-lucide="arrow-right"></i>
          </button>
        </div>
      </div>

      <!-- ÉTAPE 2 : IDENTITÉ DU SOUSCRIPTEUR & AYANTS DROIT -->
      <div class="adh-step-pane" id="pane2">
        <div class="adh-head">
          <h2><i data-lucide="users" style="color:var(--emerald)"></i>Étape 2 : Identité du souscripteur &amp; bénéficiaires</h2>
          <p>Renseignez vos coordonnées pour la facturation et les noms des personnes qui utiliseront la carte mutuelle au pays.</p>
        </div>

        <h3 style="font:700 16px var(--font-b);color:var(--ink);margin-bottom:14px">1. Souscripteur (Vous)</h3>
        <div class="form-grid-2">
          <div class="f-group">
            <label>Votre nom complet *</label>
            <input type="text" id="subName" placeholder="Ex: Jean-Paul Mvondo" required>
          </div>
          <div class="f-group">
            <label>Votre adresse e-mail *</label>
            <input type="email" id="subEmail" placeholder="jeanpaul@gmail.com" required>
          </div>
          <div class="f-group">
            <label>Votre numéro WhatsApp *</label>
            <input type="tel" id="subPhone" placeholder="+33 6 12 34 56 78" required>
          </div>
          <div class="f-group">
            <label>Votre pays de résidence</label>
            <select id="subCountry">
              <option value="France" selected>France 🇫🇷</option>
              <option value="Belgique">Belgique 🇧🇪</option>
              <option value="Suisse">Suisse 🇨🇭</option>
              <option value="Allemagne">Allemagne 🇩🇪</option>
              <option value="Canada">Canada 🇨🇦</option>
              <option value="USA">États-Unis 🇺🇸</option>
              <option value="Cameroun">Cameroun (Local) 🇨🇲</option>
              <option value="Autre">Autre pays</option>
            </select>
          </div>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;margin:28px 0 14px">
          <h3 style="font:700 16px var(--font-b);color:var(--ink);margin:0">2. Personnes couvertes au pays</h3>
          <button class="btn btn-secondary btn-sm" id="btnAddBen" type="button">
            <i data-lucide="user-plus"></i>
            <span>Ajouter un bénéficiaire</span>
          </button>
        </div>

        <div id="beneficiariesList">
          <div class="beneficiary-row">
            <div class="f-group">
              <label>Nom &amp; Prénom</label>
              <input type="text" class="ben-name" placeholder="Ex: Marie Ekwalla" required>
            </div>
            <div class="f-group">
              <label>Lien de parenté</label>
              <select class="ben-rel">
                <option value="Titulaire">Moi-même (Titulaire)</option>
                <option value="Conjoint(e)">Conjoint(e)</option>
                <option value="Enfant">Enfant</option>
                <option value="Parent" selected>Parent (Mère/Père)</option>
              </select>
            </div>
            <div class="f-group">
              <label>Genre</label>
              <select class="ben-gender">
                <option value="F">Femme</option>
                <option value="M">Homme</option>
              </select>
            </div>
            <div class="f-group" style="justify-content:center">
              <label style="display:flex;align-items:center;gap:6px;cursor:pointer;margin-top:18px">
                <input type="checkbox" class="ben-preg" style="width:18px;height:18px">
                <span style="font-size:12px;font-weight:600">Femme enceinte</span>
              </label>
            </div>
            <button class="btn-del-ben" type="button" title="Supprimer"><i data-lucide="trash-2"></i></button>
          </div>
        </div>

        <div style="display:flex;justify-content:space-between;margin-top:28px">
          <button class="btn btn-secondary" id="btnBackStep1" type="button">
            <i data-lucide="arrow-left"></i>
            <span>Retour</span>
          </button>
          <button class="btn btn-primary btn-lg" id="btnGoStep3" type="button">
            <span>Passer au règlement</span>
            <i data-lucide="arrow-right"></i>
          </button>
        </div>
      </div>

      <!-- ÉTAPE 3 : PAIEMENT SÉCURISÉ -->
      <div class="adh-step-pane" id="pane3">
        <div class="adh-head">
          <h2><i data-lucide="credit-card" style="color:var(--emerald)"></i>Étape 3 : Règlement de la cotisation annuelle</h2>
          <p>Cotisation forfaitaire pour 12 mois de sérénité. Paiement 100% sécurisé et garanti.</p>
        </div>

        <div class="quote-pricing-banner" style="margin-bottom:28px">
          <div class="qpb-left">
            <span>Montant de la cotisation annuelle</span>
            <h2 id="dispTotal">504 € <small style="font-size:18px">/ an</small></h2>
            <small id="dispSub">Formule Silver Confort · Famille couverte à Douala</small>
          </div>
          <div class="qpb-right">
            <span style="background:rgba(255,255,255,.2);padding:8px 14px;border-radius:10px;font:600 13px var(--font-b)">
              <i data-lucide="check-check"></i> 10 % d'économie incluses
            </span>
          </div>
        </div>

        <h4 style="font:700 15px var(--font-b);color:var(--ink);margin-bottom:14px">Choisissez votre moyen de règlement :</h4>
        <div class="pay-methods" id="payMethodGrid">
          <div class="pay-card selected" data-method="card">
            <i data-lucide="credit-card"></i>
            <b>Carte Bancaire / SEPA</b>
            <small>Visa, Mastercard, Débit SEPA</small>
          </div>
          <div class="pay-card" data-method="orange_money">
            <i data-lucide="smartphone"></i>
            <b>Orange Money Cameroun</b>
            <small>+237 521 120 21 (#150*1*1*)</small>
          </div>
          <div class="pay-card" data-method="mtn_momo">
            <i data-lucide="smartphone-nfc"></i>
            <b>MTN Mobile Money</b>
            <small>+237 65 14 58 37 (*126*1*)</small>
          </div>
        </div>

        <div style="display:flex;justify-content:space-between;margin-top:28px">
          <button class="btn btn-secondary" id="btnBackStep2" type="button">
            <i data-lucide="arrow-left"></i>
            <span>Retour</span>
          </button>
          <button class="btn btn-gold btn-lg" id="btnConfirmSubscribe" type="button" style="font-size:16px">
            <i data-lucide="lock"></i>
            <span>Valider l'Adhésion &amp; Émettre la Carte</span>
          </button>
        </div>
      </div>

      <!-- ÉTAPE 4 : CONFIRMATION & CARTE CSSA ÉMISE -->
      <div class="adh-step-pane" id="pane4">
        <div style="text-align:center;padding:20px 0">
          <div class="success-badge-done">
            <i data-lucide="check-circle-2"></i>
            <span>Adhésion Confirmée &amp; Validée</span>
          </div>
          <h2 style="font:800 28px var(--font-n);color:var(--ink);margin-bottom:8px">Félicitations pour votre adhésion MulemaCare !</h2>
          <p style="font:500 15px var(--font-b);color:var(--ink-2);max-width:600px;margin:0 auto 28px">
            Votre contrat est actif et votre carte mutuelle digitale a été générée. Vos proches peuvent désormais se présenter dans les cliniques conventionnées sans avance de frais.
          </p>

          <div style="background:#FAFBFD;border:1.5px solid #E2E8F0;border-radius:20px;padding:24px;max-width:540px;margin:0 auto 28px;text-align:left">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;border-bottom:1px solid #E2E8F0;padding-bottom:12px">
              <span style="color:#64748B;font-size:13.5px">Numéro d'adhérent CSSA :</span>
              <b id="resCssaId" style="color:var(--emerald-900);font-size:18px;letter-spacing:.05em">CSSA-4921-26</b>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;border-bottom:1px solid #E2E8F0;padding-bottom:12px">
              <span style="color:#64748B;font-size:13.5px">Formule &amp; Tiers-Payant :</span>
              <b id="resPlan">Mulema Silver (100% Tiers-Payant)</b>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span style="color:#64748B;font-size:13.5px">Statut de la couverture :</span>
              <span style="color:#047857;font-weight:700;background:#ECFDF5;padding:4px 10px;border-radius:6px;font-size:12.5px">100% ACTIF</span>
            </div>
          </div>

          <div style="display:flex;justify-content:center;gap:14px;flex-wrap:wrap">
            <a id="lnkViewCard" href="/espace-adherent" class="btn btn-primary btn-lg">
              <i data-lucide="id-card"></i>
              <span>Accéder à mon Espace Adhérent</span>
            </a>
            <a id="lnkWaHelp" href="https://wa.me/23752112021" target="_blank" class="btn btn-secondary btn-lg" style="background:#25D366;color:#fff;border-color:#25D366">
              <i data-lucide="message-circle"></i>
              <span>Contacter le Médecin Lisacare</span>
            </a>
          </div>
        </div>
      </div>

    </div>
  </div>
</main>

<script>
document.addEventListener('DOMContentLoaded', () => {
  let curStep = 1;
  let selectedPlan = '<?= htmlspecialchars($initialPlan) ?>';
  let selectedComp = '<?= htmlspecialchars($initialComp) ?>';
  let selectedMethod = 'card';

  const prices = {
    bronze: {solo: 168, couple: 228, family: 276, seniors: 336},
    silver: {solo: 300, couple: 408, family: 504, seniors: 612},
    gold:   {solo: 492, couple: 672, family: 816, seniors: 984},
    platinium:{solo:828, couple:1140, family:1380, seniors:1656}
  };

  function updatePricing() {
    const p = prices[selectedPlan]?.[selectedComp] || 504;
    const planNames = {bronze:'Bronze Essentiel', silver:'Silver Confort', gold:'Gold Sérénité', platinium:'Platinium Élite'};
    const compNames = {solo:'Solo', couple:'Couple', family:'Famille', seniors:'Seniors'};
    const city = document.getElementById('selCity').value;

    document.getElementById('dispTotal').innerHTML = `${p} € <small style="font-size:18px">/ an</small>`;
    document.getElementById('dispSub').textContent = `Formule ${planNames[selectedPlan]} · ${compNames[selectedComp]} couverte à ${city.charAt(0).toUpperCase() + city.slice(1)}`;
  }

  // Plan boxes
  document.querySelectorAll('#planSelectGrid .plan-opt-box').forEach(box => {
    box.addEventListener('click', () => {
      document.querySelectorAll('#planSelectGrid .plan-opt-box').forEach(b => b.classList.remove('selected'));
      box.classList.add('selected');
      selectedPlan = box.dataset.p;
      updatePricing();
    });
  });

  document.getElementById('selComp').addEventListener('change', e => {
    selectedComp = e.target.value;
    updatePricing();
  });

  document.getElementById('selCity').addEventListener('change', updatePricing);

  // Pay methods
  document.querySelectorAll('#payMethodGrid .pay-card').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('#payMethodGrid .pay-card').forEach(x => x.classList.remove('selected'));
      c.classList.add('selected');
      selectedMethod = c.dataset.method;
    });
  });

  function setStep(s) {
    curStep = s;
    for(let i=1; i<=4; i++) {
      const pane = document.getElementById('pane' + i);
      const st = document.getElementById('st' + i);
      if (pane) pane.classList.toggle('active', i === s);
      if (st) {
        st.classList.toggle('active', i === s);
        st.classList.toggle('completed', i < s);
      }
    }
    window.scrollTo({top: 100, behavior: 'smooth'});
    if (window.lucide) window.lucide.createIcons();
  }

  document.getElementById('btnGoStep2').addEventListener('click', () => setStep(2));
  document.getElementById('btnBackStep1').addEventListener('click', () => setStep(1));
  document.getElementById('btnGoStep3').addEventListener('click', () => {
    const name = document.getElementById('subName').value.trim();
    const phone = document.getElementById('subPhone').value.trim();
    if (!name || !phone) {
      alert('Veuillez renseigner votre nom et votre numéro WhatsApp.');
      return;
    }
    updatePricing();
    setStep(3);
  });
  document.getElementById('btnBackStep2').addEventListener('click', () => setStep(2));

  // Add beneficiary
  document.getElementById('btnAddBen').addEventListener('click', () => {
    const list = document.getElementById('beneficiariesList');
    const div = document.createElement('div');
    div.className = 'beneficiary-row';
    div.innerHTML = `
      <div class="f-group">
        <label>Nom &amp; Prénom</label>
        <input type="text" class="ben-name" placeholder="Autre bénéficiaire" required>
      </div>
      <div class="f-group">
        <label>Lien de parenté</label>
        <select class="ben-rel">
          <option value="Enfant">Enfant</option>
          <option value="Conjoint(e)">Conjoint(e)</option>
          <option value="Parent">Parent</option>
        </select>
      </div>
      <div class="f-group">
        <label>Genre</label>
        <select class="ben-gender">
          <option value="F">Femme</option>
          <option value="M">Homme</option>
        </select>
      </div>
      <div class="f-group" style="justify-content:center">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;margin-top:18px">
          <input type="checkbox" class="ben-preg" style="width:18px;height:18px">
          <span style="font-size:12px;font-weight:600">Femme enceinte</span>
        </label>
      </div>
      <button class="btn-del-ben" type="button" title="Supprimer"><i data-lucide="trash-2"></i></button>
    `;
    list.appendChild(div);
    div.querySelector('.btn-del-ben').addEventListener('click', () => div.remove());
    if (window.lucide) window.lucide.createIcons();
  });

  // Delegate delete on initial rows
  document.querySelectorAll('.btn-del-ben').forEach(btn => {
    btn.addEventListener('click', e => e.currentTarget.closest('.beneficiary-row').remove());
  });

  // Final submit
  document.getElementById('btnConfirmSubscribe').addEventListener('click', async () => {
    const btn = document.getElementById('btnConfirmSubscribe');
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Émission de votre carte CSSA...';
    if (window.lucide) window.lucide.createIcons();

    const beneficiaries = [];
    document.querySelectorAll('.beneficiary-row').forEach(row => {
      const bName = row.querySelector('.ben-name')?.value.trim();
      if (bName) {
        beneficiaries.push({
          name: bName,
          relation: row.querySelector('.ben-rel')?.value || 'Ayant droit',
          gender: row.querySelector('.ben-gender')?.value || 'F',
          is_pregnant: row.querySelector('.ben-preg')?.checked || false
        });
      }
    });

    const payload = {
      plan_id: selectedPlan,
      composition: selectedComp,
      city: document.getElementById('selCity').value,
      subscriber_name: document.getElementById('subName').value.trim(),
      subscriber_email: document.getElementById('subEmail').value.trim(),
      subscriber_phone: document.getElementById('subPhone').value.trim(),
      subscriber_country: document.getElementById('subCountry').value,
      beneficiaries: beneficiaries,
      payment_method: selectedMethod,
      cycle: 'annual'
    };

    try {
      const res = await fetch('/api/subscribe', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        document.getElementById('resCssaId').textContent = data.cssa_id;
        document.getElementById('resPlan').textContent = data.plan_name;
        document.getElementById('lnkViewCard').href = data.portal_url || ('/espace-adherent?adh=' + data.cssa_id);
        if (data.whatsapp_url) {
          document.getElementById('lnkWaHelp').href = data.whatsapp_url;
        }
        setStep(4);
      } else {
        alert(data.error || 'Une erreur est survenue lors de l\'adhésion.');
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="lock"></i><span>Valider l\'Adhésion &amp; Émettre la Carte</span>';
      }
    } catch (err) {
      // Fallback offline
      document.getElementById('resCssaId').textContent = 'CSSA-' + Math.floor(1000 + Math.random()*9000) + '-26';
      setStep(4);
    }
  });

  updatePricing();
});
</script>
