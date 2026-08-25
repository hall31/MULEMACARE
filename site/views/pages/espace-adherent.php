<style>
/* ================= ESPACE ADHÉRENT (FAMILY HUB) ================= */
.user-hub{padding:48px 0 88px;background:var(--bg)}
.hub-header{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;margin-bottom:36px;flex-wrap:wrap}
.hub-header h1{font-size:clamp(1.8rem,3vw,2.4rem);font-weight:800}
.hub-header p{font-size:15px;color:var(--ink-3);margin-top:4px}
.hub-actions{display:flex;gap:12px;align-items:center}

.hub-grid{display:grid;grid-template-columns:1fr 1.1fr;gap:36px;align-items:start}

.hub-card-box{background:#fff;border:1.5px solid var(--line);border-radius:24px;padding:32px;box-shadow:var(--shadow-1)}
.ben-selector{display:flex;gap:10px;overflow-x:auto;padding-bottom:14px;margin-bottom:24px;scrollbar-width:none}
.ben-selector::-webkit-scrollbar{display:none}
.ben-btn{background:#F1F5F9;border:1.5px solid var(--line);border-radius:12px;padding:10px 16px;display:flex;align-items:center;gap:10px;cursor:pointer;white-space:nowrap;transition:.18s;font:600 13.5px var(--font-b);color:var(--ink-2)}
.ben-btn:hover{border-color:var(--emerald);color:var(--emerald)}
.ben-btn.active{background:var(--emerald-050);border-color:var(--emerald);color:var(--emerald);box-shadow:0 0 0 3px rgba(9,114,104,.1)}
.ben-btn .b-dot{width:8px;height:8px;border-radius:50%;background:#10B981}

.hub-gauge-box{background:var(--bg);border:1.5px solid var(--line);border-radius:18px;padding:20px;margin-top:24px}
.gauge-top{display:flex;justify-content:space-between;font-size:13.5px;color:var(--ink-2);margin-bottom:8px}
.gauge-bar{width:100%;height:10px;border-radius:99px;background:#E2E8F0;overflow:hidden;margin-bottom:8px}
.gauge-fill{height:100%;background:linear-gradient(90deg,var(--emerald),var(--emerald-500));border-radius:99px;width:18%}
.gauge-meta{display:flex;justify-content:space-between;font-size:12px;color:var(--ink-3)}

.hub-claims-box{background:#fff;border:1.5px solid var(--line);border-radius:24px;padding:32px;box-shadow:var(--shadow-1)}
.hub-claims-box h3{font-size:19px;font-weight:700;margin-bottom:20px;display:flex;align-items:center;gap:10px}
.claims-table{width:100%;border-collapse:collapse;font-size:13.5px}
.claims-table th{text-align:left;padding:12px 14px;background:#F8FAFC;color:var(--ink-3);font-weight:600;border-bottom:1.5px solid var(--line)}
.claims-table td{padding:14px;border-bottom:1px solid var(--line-2);color:var(--ink-2)}
.claims-table tr:last-child td{border-bottom:0}
.claim-badge{display:inline-flex;align-items:center;gap:5px;background:#ECFDF5;color:#047857;border-radius:99px;padding:3px 10px;font:600 11.5px var(--font-b)}

.hub-services-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:24px}
.hub-service-card{border:1.5px solid var(--line);border-radius:16px;padding:18px;display:flex;align-items:center;gap:14px;background:#FBFDFC;transition:.18s}
.hub-service-card:hover{border-color:var(--emerald);transform:translateY(-2px);box-shadow:var(--shadow-1)}
.hub-service-card .h-ic{width:42px;height:42px;border-radius:12px;background:var(--emerald-050);color:var(--emerald);display:grid;place-items:center;flex:none}

@media(max-width:960px){
  .hub-grid{grid-template-columns:1fr}
  .hub-services-grid{grid-template-columns:1fr}
}
</style>

<div class="user-hub">
  <div class="wrap">
    <div class="hub-header">
      <div>
        <span class="badge-agr"><i data-lucide="shield-check"></i>Espace Adhérent Sécurisé · N° ADH-98420173</span>
        <h1>Bonjour Éric Awono Mballa</h1>
        <p>Famille rattachée : <b>4 bénéficiaires</b> · Formule <b>Silver (Famille &amp; Soins Courants)</b> · Tiers-payant 100% actif</p>
      </div>
      <div class="hub-actions">
        <button class="btn btn-primary btn-sm" id="btnHubPdf"><i data-lucide="download"></i>Attestation PDF</button>
        <a class="btn btn-ghost btn-sm" href="https://wa.me/23752112021?text=Bonjour%20MulemaCare%2C%20j%27ai%20une%20question%20sur%20mon%20espace%20adh%C3%A9rent." target="_blank" rel="noopener"><i data-lucide="message-circle"></i>Assistance 24/7</a>
      </div>
    </div>

    <div class="hub-grid">
      <!-- Colonne Gauche : Cartes & Jauges -->
      <div class="hub-card-box">
        <h3 style="font-size:18px;font-weight:700;margin-bottom:16px;display:flex;align-items:center;gap:9px">
          <i data-lucide="wallet-cards" style="color:var(--emerald)"></i>Portefeuille Famille (Pass Digital)
        </h3>

        <!-- Sélecteur de bénéficiaire -->
        <div class="ben-selector" id="benSelector">
          <button type="button" class="ben-btn active" data-ben-name="Éric Awono Mballa" data-ben-cssa="CSSA-8842-26" data-ben-rel="Titulaire">
            <span class="b-dot"></span>Éric (Vous)
          </button>
          <button type="button" class="ben-btn" data-ben-name="Marthe Awono" data-ben-cssa="CSSA-8842-27" data-ben-rel="Conjointe">
            <span class="b-dot"></span>Marthe (Épouse)
          </button>
          <button type="button" class="ben-btn" data-ben-name="Junior Awono" data-ben-cssa="CSSA-8842-28" data-ben-rel="Enfant">
            <span class="b-dot"></span>Junior (Fils)
          </button>
          <button type="button" class="ben-btn" data-ben-name="Maman Madeleine Ekwalla" data-ben-cssa="CSSA-8842-29" data-ben-rel="Mère">
            <span class="b-dot"></span>Mme Ekwalla (Mère)
          </button>
        </div>

        <!-- Carte d'assuré dynamique -->
        <div class="member-card static" id="hubMemberCard" data-plan="silver">
          <div class="card-face card-front" id="hubCardFront"></div>
        </div>

        <!-- Jauge Plafond Annuel -->
        <div class="hub-gauge-box">
          <div class="gauge-top">
            <span>Plafond Annuel Hospitalier &amp; Soins</span>
            <b class="num" id="hubCapText">1 260 000 FCFA restants</b>
          </div>
          <div class="gauge-bar"><div class="gauge-fill" id="hubGaugeFill" style="width:16%"></div></div>
          <div class="gauge-meta">
            <span>Consommé : 240 000 FCFA (16 %)</span>
            <span>Plafond Total : 1 500 000 FCFA (2 290 €)</span>
          </div>
        </div>
        <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;padding:9px 12px;font-size:12px;color:#166534;margin-top:12px;display:flex;align-items:center;gap:7px">
          <i data-lucide="shield-check" style="width:15px;height:15px;flex:none"></i>
          <span>Délais de carence échus · Prise en charge 100% active dans le réseau agréé.</span>
        </div>

        <!-- Services d'urgence connectés -->
        <div class="hub-services-grid">
          <a class="hub-service-card" href="https://wa.me/23752112021?text=Urgence%20MulemaCare%20Dr%20Lisacare" target="_blank" rel="noopener">
            <div class="h-ic"><i data-lucide="stethoscope"></i></div>
            <div>
              <b style="font-size:13.5px;display:block">Médecin Lisacare</b>
              <small style="color:var(--ink-3);font-size:12px">Réponse en 4 min 24/7</small>
            </div>
          </a>
          <button type="button" class="hub-service-card" data-info="ongwa" style="border:1.5px solid #FCD34D;background:#FFFDF6">
            <div class="h-ic" style="background:var(--gold-100);color:#92400E"><i data-lucide="heart-pulse"></i></div>
            <div style="text-align:left">
              <b style="font-size:13.5px;display:block">Visite Ongwa Senior</b>
              <small style="color:var(--ink-3);font-size:12px">Planifier un passage</small>
            </div>
          </button>
        </div>
      </div>

      <!-- Colonne Droite : Historique des Prises en Charge -->
      <div class="hub-claims-box">
        <h3><i data-lucide="receipt" style="color:var(--emerald)"></i>Derniers Actes &amp; Prises en Charge Tiers-Payant</h3>
        <p style="font-size:13.5px;color:var(--ink-3);margin-bottom:20px">Toutes les consultations et ordonnances validées en clinique conventionnée sans avance de frais :</p>
        
        <table class="claims-table">
          <thead>
            <tr>
              <th>Date &amp; Bénéficiaire</th>
              <th>Établissement</th>
              <th>Acte</th>
              <th>Couverture</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <b style="display:block">18 Août 2026</b>
                <small style="color:var(--ink-3)">Junior Awono</small>
              </td>
              <td>Clinique de l'Étoile (Bonapriso)</td>
              <td>Pédiatrie &amp; Bilan</td>
              <td><span class="claim-badge"><i data-lucide="check"></i>100% Tiers-payant</span></td>
            </tr>
            <tr>
              <td>
                <b style="display:block">04 Août 2026</b>
                <small style="color:var(--ink-3)">Marthe Awono</small>
              </td>
              <td>Pharmacie du Centre (Akwa)</td>
              <td>Ordonnance Dr Lisacare</td>
              <td><span class="claim-badge"><i data-lucide="check"></i>80% Remboursé</span></td>
            </tr>
            <tr>
              <td>
                <b style="display:block">22 Juillet 2026</b>
                <small style="color:var(--ink-3)">Mme Ekwalla</small>
              </td>
              <td>Visite Domicile Ongwa</td>
              <td>Contrôle Tension &amp; Glycémie</td>
              <td><span class="claim-badge"><i data-lucide="check"></i>0 F Avancé</span></td>
            </tr>
            <tr>
              <td>
                <b style="display:block">12 Juillet 2026</b>
                <small style="color:var(--ink-3)">Éric Awono</small>
              </td>
              <td>Polyclinique Bonanjo</td>
              <td>Consultation Médecine Générale</td>
              <td><span class="claim-badge"><i data-lucide="check"></i>100% Pris en charge</span></td>
            </tr>
          </tbody>
        </table>

        <!-- Téléchargement Attestation de Droit -->
        <div style="background:#F8FAFC;border:1px solid var(--line);border-radius:16px;padding:20px;margin-top:24px;display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap">
          <div>
            <b style="font-size:14px;display:block">Attestation Fiscale Diaspora &amp; Reçu de Cotisation</b>
            <small style="color:var(--ink-3)">Valable pour vos déclarations et justificatifs administratifs</small>
          </div>
          <button class="btn btn-ghost btn-sm" onclick="toast('Téléchargement en cours', 'Votre reçu fiscal 2026 a été généré.', 'success')">
            <i data-lucide="file-text"></i>Reçu Fiscal 2026
          </button>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
/* Mise à jour dynamique de la carte selon le bénéficiaire sélectionné */
const benBtns = $$('#benSelector .ben-btn');
benBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    benBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const name = btn.dataset.benName;
    const no = btn.dataset.benCssa;
    
    if($('#hubCardFront')) {
      $('#hubCardFront').innerHTML = cardFrontHTML({
        name: name,
        no: no,
        plan: 'silver',
        validThru: '12/2028'
      });
      icons();
    }
    toast('Carte actualisée', `Affichage de la carte CSSA pour ${name}.`, 'info');
  });
});

// Initialisation de la carte au chargement
if($('#hubCardFront')) {
  $('#hubCardFront').innerHTML = cardFrontHTML({
    name: 'Éric Awono Mballa',
    no: 'CSSA-8842-26',
    plan: 'silver',
    validThru: '12/2028'
  });
  icons();
}

if($('#btnHubPdf')) {
  $('#btnHubPdf').onclick = () => {
    const activeBtn = $('#benSelector .ben-btn.active') || benBtns[0];
    const m = {
      name: activeBtn.dataset.benName,
      adh: 'ADH-98420173',
      cssa: activeBtn.dataset.benCssa,
      plan: 'silver'
    };
    $('#printArea').innerHTML = `
      <h2>MulemaCare Mutuelle Santé — Attestation de Tiers-Payant</h2>
      <p class="pa-sub">Émise le ${new Date().toLocaleDateString('fr-FR')} · Agrément CSSA n° 045/CSSA/2024 · mulemacare.com</p>
      <div class="member-card static" data-plan="silver"><div class="card-face card-front">${cardFrontHTML(m)}</div></div>
      <div class="pa-meta">
        <div><b>N° d'adhésion :</b> <span class="num">${m.adh}</span></div>
        <div><b>Adhérent :</b> ${esc(m.name)}</div>
        <div><b>Formule :</b> Silver (Famille &amp; Soins Courants)</div>
        <div><b>Urgences 24/7 :</b> <span class="num">+237 521 120 21</span></div>
      </div>`;
    window.print();
  };
}
</script>
