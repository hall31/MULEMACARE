<style>
/* ================= PAGE ENTREPRISES & PME (MULEMACARE PRO) ================= */
.pro-hero{position:relative;background:var(--bg);background-image:radial-gradient(rgba(9,114,104,.08) 1px,transparent 1px);background-size:22px 22px;border-bottom:1px solid var(--line);padding:72px 0 84px;overflow:hidden}
.pro-hero-in{position:relative;z-index:1;display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center}
.pro-hero h1{font-size:clamp(2.3rem,4.4vw,3.6rem);font-weight:800;color:var(--ink);margin:20px 0 18px;line-height:1.16}
.pro-hero h1 .hl{background:linear-gradient(transparent 62%,var(--gold-100) 62%);border-radius:3px;padding:0 3px}
.pro-hero-sub{font-size:17px;color:var(--ink-2);line-height:1.6;margin-bottom:30px;max-width:35rem}
.pro-hero-cta{display:flex;gap:14px;flex-wrap:wrap}
.pro-badges{display:flex;gap:18px;flex-wrap:wrap;margin-top:32px;padding-top:24px;border-top:1px solid var(--line)}
.pro-badge{display:flex;align-items:center;gap:8px;font:600 13px var(--font-b);color:var(--ink-2)}
.pro-badge svg{width:16px;height:16px;color:var(--emerald);flex:none}

.pro-hero-visual{position:relative}
.pro-hero-card-frame{position:relative;background:#fff;border:1.5px solid var(--line);border-radius:24px;padding:16px;box-shadow:var(--shadow-2)}
.pro-hero-img-wrap{position:relative;border-radius:18px;overflow:hidden;background:#0F172A;height:340px}
.pro-hero-img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .3s}
.pro-hero-card-frame:hover .pro-hero-img{transform:scale(1.02)}

.pro-float-top{position:absolute;top:28px;right:28px;background:rgba(255,255,255,.94);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:12px;padding:8px 14px;box-shadow:var(--shadow-1);display:flex;align-items:center;gap:8px}
.pro-float-top b{font-size:12.5px;color:var(--ink);font-weight:700}
.pro-float-top .pulse-dot{width:7px;height:7px;border-radius:50%;background:#10B981}

.pro-hero-overlay-card{margin-top:14px;background:var(--emerald-050);border:1px solid var(--emerald-100);border-radius:14px;padding:14px 18px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.pro-hero-overlay-card .pro-ov-left b{display:block;font-size:14.5px;color:var(--emerald-900);font-weight:700}
.pro-hero-overlay-card .pro-ov-left span{font-size:12px;color:var(--emerald);font-weight:500}
.pro-hero-overlay-card .pro-ov-badge{background:var(--emerald);color:#fff;font:700 11px var(--font-b);padding:5px 11px;border-radius:99px;white-space:nowrap}

/* ================= SIMULATEUR B2B ================= */
.pro-calc-sec{background:#fff;padding:88px 0;border-bottom:1px solid var(--line)}
.pro-calc-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:start}
.calc-box{background:var(--bg);border:1.5px solid var(--line);border-radius:22px;padding:32px}
.range-header{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px}
.range-header label{font:700 15px var(--font-b);color:var(--ink)}
.range-header .emp-count{font:800 24px var(--font-n);color:var(--emerald)}
.pro-slider{width:100%;height:8px;border-radius:99px;background:#CBD5E1;outline:none;accent-color:var(--emerald);cursor:pointer;margin-bottom:10px}
.range-scales{display:flex;justify-content:space-between;font:500 12px var(--font-b);color:var(--ink-3);margin-bottom:28px}
.b2b-summary{background:#fff;border:1.5px solid var(--line);border-radius:18px;padding:22px;display:flex;flex-direction:column;gap:12px;margin-bottom:24px}
.b2b-row{display:flex;justify-content:space-between;font-size:14px;color:var(--ink-2)}
.b2b-row strong{color:var(--ink);font-weight:700}
.b2b-total{border-top:1.5px solid var(--line-2);padding-top:14px;display:flex;justify-content:space-between;align-items:baseline}
.b2b-total span{font:700 15px var(--font-b);color:var(--ink)}
.b2b-total b{font:800 28px var(--font-n);color:var(--emerald);letter-spacing:-.02em}

/* ================= PILIERS & AVANTAGES ================= */
.pro-pillars-sec{background:var(--bg);padding:88px 0;border-bottom:1px solid var(--line)}
.pro-pillars-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
.pillar-card{background:#fff;border:1.5px solid var(--line);border-radius:20px;padding:32px 26px;display:flex;flex-direction:column;gap:14px;transition:transform .2s,box-shadow .2s}
.pillar-card:hover{transform:translateY(-4px);box-shadow:var(--shadow-1);border-color:#CBD5E1}
.pillar-ic{width:48px;height:48px;border-radius:14px;background:var(--emerald-050);color:var(--emerald);display:grid;place-items:center}
.pillar-ic svg{width:22px;height:22px}
.pillar-card h3{font-size:18px;font-weight:700}
.pillar-card p{font-size:14px;color:var(--ink-2);line-height:1.55}

/* ================= ÉTAPES DE DÉPLOIEMENT ================= */
.steps-sec{background:#fff;padding:88px 0;border-bottom:1px solid var(--line)}
.steps-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;position:relative}
.step-card{background:var(--bg);border:1.5px solid var(--line);border-radius:18px;padding:26px 22px;position:relative}
.step-num{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:10px;background:var(--emerald);color:#fff;font:800 15px var(--font-n);margin-bottom:14px}
.step-card h3{font-size:16.5px;font-weight:700;margin-bottom:8px;color:var(--ink)}
.step-card p{font-size:13.5px;color:var(--ink-2);line-height:1.5}

/* ================= TÉMOIGNAGES DRH AVEC PHOTOS ================= */
.drh-sec{background:linear-gradient(180deg,#F8FAFC 0%,#EEF8F6 100%);padding:88px 0}
.drh-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:26px}
.drh-card{background:#fff;border:1.5px solid var(--line);border-radius:22px;padding:32px 28px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:var(--shadow-sm);transition:transform .2s}
.drh-card:hover{transform:translateY(-3px);box-shadow:var(--shadow-1)}
.drh-quote{font-size:14.5px;color:var(--ink-2);line-height:1.6;font-style:italic;margin-bottom:24px}
.drh-profile{display:flex;align-items:center;gap:14px}
.drh-avatar{width:52px;height:52px;border-radius:50%;object-fit:cover;border:2px solid var(--emerald)}
.drh-info h4{font-size:15px;font-weight:700;color:var(--ink);margin:0 0 2px}
.drh-info span{font-size:12.5px;color:var(--ink-3);display:block}

@media(max-width:960px){
  .pro-hero-in,.pro-calc-grid{grid-template-columns:1fr}
  .pro-hero-overlay-card{position:static;margin-top:16px;max-width:100%}
  .pro-pillars-grid,.steps-grid,.drh-grid{grid-template-columns:1fr}
}
</style>

<!-- ═══════════ HERO ENTREPRISES ═══════════ -->
<section class="pro-hero">
  <div class="wrap pro-hero-in">
    <div>
      <span class="badge-agr"><i data-lucide="building-2"></i>MulemaCare Pro · Santé Collective PME &amp; Groupes</span>
      <h1>La mutuelle santé d'entreprise clé en main, <span class="hl">100 % déductible</span>.</h1>
      <p class="pro-hero-sub">Offrez le tiers-payant direct en clinique à vos collaborateurs et leurs familles sans aucune avance de frais. Valorisez votre marque employeur, supprimez les notes de frais médicales et réduisez l'absentéisme.</p>
      <div class="pro-hero-cta">
        <a class="btn btn-primary" href="#b2bSimulateur"><i data-lucide="calculator"></i>Estimer le budget équipe</a>
        <a class="btn btn-ghost" href="#proForm"><i data-lucide="send"></i>Demander une convention RH</a>
      </div>
      <div class="pro-badges">
        <span class="pro-badge"><i data-lucide="shield-check"></i>Agrément CSSA n° 045</span>
        <span class="pro-badge"><i data-lucide="receipt"></i>100% Déductible (CGI / OHADA)</span>
        <span class="pro-badge"><i data-lucide="clock"></i>Déploiement sous 48 h</span>
      </div>
    </div>

    <!-- Panneau Flotte Entreprise (Design Iconique Uni) -->
    <div class="pro-hero-visual reveal">
      <div style="background:#0B132B;color:#fff;border-radius:24px;border:1.5px solid rgba(255,255,255,.12);padding:32px;box-shadow:0 24px 48px -12px rgba(6,74,67,.35);position:relative;overflow:hidden">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;padding-bottom:18px;border-bottom:1px solid rgba(255,255,255,.1)">
          <span style="display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);padding:6px 14px;border-radius:99px;font:700 12px var(--font-b);color:#5EEAD4">
            <span class="pulse-dot"></span>Dashboard RH &amp; Santé Collective
          </span>
          <span style="font:600 12px var(--font-b);color:#94A3B8">Agrément CSSA n° 045</span>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:24px">
          <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;display:flex;align-items:flex-start;gap:12px">
            <i data-lucide="receipt" style="width:22px;height:22px;color:#5EEAD4;flex:none;margin-top:2px"></i>
            <div>
              <b style="display:block;font-size:14px;font-weight:700;color:#fff;margin-bottom:2px">100% Déductible</b>
              <span style="font-size:11.5px;color:#94A3B8;line-height:1.4">Conformité CGI / OHADA fiscale</span>
            </div>
          </div>
          <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;display:flex;align-items:flex-start;gap:12px">
            <i data-lucide="shield-check" style="width:22px;height:22px;color:#5EEAD4;flex:none;margin-top:2px"></i>
            <div>
              <b style="display:block;font-size:14px;font-weight:700;color:#fff;margin-bottom:2px">Zéro Avance de Frais</b>
              <span style="font-size:11.5px;color:#94A3B8;line-height:1.4">Tiers-payant direct en clinique</span>
            </div>
          </div>
          <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;display:flex;align-items:flex-start;gap:12px">
            <i data-lucide="sparkles" style="width:22px;height:22px;color:#5EEAD4;flex:none;margin-top:2px"></i>
            <div>
              <b style="display:block;font-size:14px;font-weight:700;color:#fff;margin-bottom:2px">+40% Rétention</b>
              <span style="font-size:11.5px;color:#94A3B8;line-height:1.4">Avantage social attractif pour talents</span>
            </div>
          </div>
          <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;display:flex;align-items:flex-start;gap:12px">
            <i data-lucide="clock" style="width:22px;height:22px;color:#5EEAD4;flex:none;margin-top:2px"></i>
            <div>
              <b style="display:block;font-size:14px;font-weight:700;color:#fff;margin-bottom:2px">Déploiement 48 h</b>
              <span style="font-size:11.5px;color:#94A3B8;line-height:1.4">Onboarding digital sans paperasse</span>
            </div>
          </div>
        </div>
        <div style="background:rgba(9,114,104,.2);border:1px solid rgba(94,234,212,.25);border-radius:14px;padding:14px 18px;display:flex;align-items:center;justify-content:space-between;gap:14px">
          <div>
            <b style="display:block;font-size:13.5px;color:#ECFDF8;font-weight:700">Portail Gestionnaire RH</b>
            <span style="font-size:11.5px;color:#99F6E4">Ajout / retrait de salariés en 1 clic</span>
          </div>
          <a href="#proForm" class="btn btn-sm btn-primary" style="white-space:nowrap;padding:8px 14px;font-size:12px">
            Demander convention
          </a>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ SIMULATEUR B2B ═══════════ -->
<section class="pro-calc-sec" id="b2bSimulateur">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">01</span>
      <div>
        <p class="eyebrow">Simulateur Budget RH</p>
        <h2>Calculez en temps réel le coût pour votre flotte de salariés.</h2>
        <p class="sec-sub">Remise groupe dégressive appliquée automatiquement dès 10 salariés. Tarification transparente sans frais d'adhésion cachés.</p>
      </div>
    </div>
    <div class="pro-calc-grid">
      <div class="calc-box reveal">
        <div class="range-header">
          <label for="empRange">Effectif de salariés à couvrir :</label>
          <span class="emp-count" id="empCountDisplay">30 salariés</span>
        </div>
        <input type="range" class="pro-slider" id="empRange" min="5" max="300" step="1" value="30">
        <div class="range-scales">
          <span>5 (TPE/PME)</span>
          <span>50 (PME moyenne)</span>
          <span>150 (Grande entreprise)</span>
          <span>300+</span>
        </div>
        <div class="b2b-summary">
          <div class="b2b-row"><span>Formule recommandée :</span><strong style="color:var(--emerald)">Silver Pro (Soins courants &amp; Hospitalisation)</strong></div>
          <div class="b2b-row"><span>Plafond annuel par salarié :</span><strong>2 500 000 FCFA (3 810 €)</strong></div>
          <div class="b2b-row"><span>Remise collective appliquée :</span><strong id="b2bDiscountLabel" style="color:#047857"><i data-lucide="badge-percent"></i>20 % de remise</strong></div>
          <div class="b2b-row"><span>Cotisation unitaire par salarié :</span><strong class="num" id="b2bUnitPriceDisplay">24 000 FCFA / mois (≈ 36,50 €)</strong></div>
          <div class="b2b-total">
            <span>Budget Mensuel Total :</span>
            <b class="num" id="b2bTotalDisplay">720 000 FCFA</b>
          </div>
        </div>
        <div style="display:flex;gap:12px;align-items:center;font-size:12.5px;color:var(--ink-3)">
          <i data-lucide="info" style="color:var(--emerald);width:16px;height:16px;flex:none"></i>
          <span>Facturation éligible au paiement mensuel, trimestriel ou annuel avec attestation fiscale fournie.</span>
        </div>
      </div>

      <!-- Formulaire Devis Express -->
      <div class="reveal" id="proForm" style="background:#fff;border:1.5px solid var(--line);border-radius:22px;padding:34px;box-shadow:var(--shadow-1)">
        <h3 style="font-size:21px;font-weight:700;margin-bottom:8px">Demande de Convention &amp; Devis RH</h3>
        <p style="font-size:13.5px;color:var(--ink-3);margin-bottom:22px">Recevez notre proposition personnalisée sous 24h ouvrées.</p>
        <form id="formB2B" style="display:flex;flex-direction:column;gap:14px">
          <div class="field">
            <label for="b2bCompany">Raison Sociale de l'Entreprise *</label>
            <input type="text" id="b2bCompany" required placeholder="Ex. Groupe Afriland, Société Générale, Startup SAS…">
          </div>
          <div class="f-grid2">
            <div class="field">
              <label for="b2bContact">Nom du DRH / Dirigeant *</label>
              <input type="text" id="b2bContact" required placeholder="Ex. Paul Ndombe">
            </div>
            <div class="field">
              <label for="b2bPhone">Téléphone Pro (WhatsApp) *</label>
              <input type="tel" id="b2bPhone" required placeholder="+237 6XX XX XX XX">
            </div>
          </div>
          <div class="field">
            <label for="b2bEmail">Adresse Email Professionnelle *</label>
            <input type="email" id="b2bEmail" required placeholder="drh@entreprise.com">
          </div>
          <div class="field">
            <label for="b2bCity">Ville du Siège / Hub Principal</label>
            <select id="b2bCity">
              <option value="douala">Douala (Cameroun)</option>
              <option value="yaounde">Yaoundé (Cameroun)</option>
              <option value="kinshasa">Kinshasa (RDC)</option>
              <option value="abidjan">Abidjan (Côte d'Ivoire)</option>
              <option value="dakar">Dakar (Sénégal)</option>
              <option value="libreville">Libreville (Gabon)</option>
            </select>
          </div>
          <button type="submit" class="btn btn-primary btn-block" style="margin-top:8px">
            <i data-lucide="send"></i>Envoyer ma demande de convention RH
          </button>
        </form>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ PILIERS ENTREPRISES ═══════════ -->
<section class="pro-pillars-sec">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">02</span>
      <div>
        <p class="eyebrow">Les Avantages Employeur</p>
        <h2>Pourquoi les DRH choisissent MulemaCare Pro.</h2>
        <p class="sec-sub">Une solution moderne qui supprime la gestion papier et les notes de frais médicales imprévues.</p>
      </div>
    </div>
    <div class="pro-pillars-grid">
      <div class="pillar-card reveal">
        <div class="pillar-ic"><i data-lucide="layout-dashboard"></i></div>
        <h3>Espace RH &amp; Gestion des Salariés</h3>
        <p>Ajoutez ou retirez des collaborateurs en 1 clic lors des arrivées/départs. Exportez les relevés de consommation et attestations fiscales en format Excel/PDF.</p>
      </div>
      <div class="pillar-card reveal">
        <div class="pillar-ic" style="background:var(--gold-100);color:#92400E"><i data-lucide="wallet-cards"></i></div>
        <h3>Cartes Digitales &amp; Zéro Note de Frais</h3>
        <p>Vos collaborateurs présentent leur QR Code directement sur leur smartphone à la clinique. Plus besoin d'avances de trésorerie ni de remboursements manuels.</p>
      </div>
      <div class="pillar-card reveal">
        <div class="pillar-ic" style="background:var(--blue-050);color:var(--blue-800)"><i data-lucide="phone-call"></i></div>
        <h3>Télémédecine Lisacare 24/7 Incluse</h3>
        <p>Diminuez l'absentéisme : un médecin de garde qualifié répond en 4 minutes sur WhatsApp pour orienter et conseiller vos équipes sans perte de temps.</p>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ DÉPLOIEMENT EN 4 ÉTAPES ═══════════ -->
<section class="steps-sec">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">03</span>
      <div>
        <p class="eyebrow">Déploiement Express</p>
        <h2>Comment déployer MulemaCare dans votre entreprise.</h2>
        <p class="sec-sub">Un accompagnement dédié de notre équipe pour une mise en service en moins de 48 heures.</p>
      </div>
    </div>
    <div class="steps-grid">
      <div class="step-card reveal">
        <span class="step-num">1</span>
        <h3>Devis &amp; Convention</h3>
        <p>Définissez votre niveau de couverture (Bronze, Silver, Gold) et signez la convention collective d'entreprise.</p>
      </div>
      <div class="step-card reveal">
        <span class="step-num">2</span>
        <h3>Import Flotte RH</h3>
        <p>Transmettez votre fichier Excel de collaborateurs avec les éventuels ayants droit (conjoints et enfants).</p>
      </div>
      <div class="step-card reveal">
        <span class="step-num">3</span>
        <h3>Cartes Digitales CSSA</h3>
        <p>Chaque salarié reçoit son identifiant sécurisé et sa carte digitale avec QR Code sur son smartphone.</p>
      </div>
      <div class="step-card reveal">
        <span class="step-num">4</span>
        <h3>Tiers-Payant Actif</h3>
        <p>Vos équipes se soignent directement dans le réseau agréé sans débourser un franc. Facturation unique mensuelle.</p>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ TÉMOIGNAGES DRH AVEC PHOTOS ═══════════ -->
<section class="drh-sec">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">04</span>
      <div>
        <p class="eyebrow">Ils nous font confiance</p>
        <h2>Ce que disent les DRH et Dirigeants d'entreprises.</h2>
        <p class="sec-sub">Découvrez les retours d'expérience des entreprises qui ont choisi le tiers-payant MulemaCare.</p>
      </div>
    </div>
    <div class="drh-grid">
      <div class="drh-card reveal">
        <p class="drh-quote">« Auparavant, la gestion des notes de frais de pharmacie et d'hôpital nous prenait 3 jours par mois en comptabilité. Avec MulemaCare Pro, nos 45 collaborateurs vont directement en clinique sans avancer de fonds. C'est un gain de temps inestimable. »</p>
        <div class="drh-profile">
          <div class="drh-avatar" style="background:linear-gradient(135deg,#064E3B,#0D9488);color:#fff;display:grid;place-items:center;font:700 16px var(--font-b);border:2px solid var(--emerald-500);box-shadow:var(--shadow-sm)">CT</div>
          <div class="drh-info">
            <h4>Cédric Tchakounte</h4>
            <span>Directeur des Ressources Humaines · Fintech (Douala)</span>
          </div>
        </div>
      </div>

      <div class="drh-card reveal">
        <p class="drh-quote">« Dans le secteur du BTP et de l'ingénierie, la sécurité médicale sur chantier est primordiale. L'accès instantané aux urgences et à la télérégulation Lisacare 24/7 a divisé nos temps d'arrêt maladie par deux. »</p>
        <div class="drh-profile">
          <div class="drh-avatar" style="background:linear-gradient(135deg,#0F766E,#14B8A6);color:#fff;display:grid;place-items:center;font:700 16px var(--font-b);border:2px solid var(--emerald-500);box-shadow:var(--shadow-sm)">AT</div>
          <div class="drh-info">
            <h4>Amina Traoré</h4>
            <span>Directrice Générale · Groupe BTP (Abidjan)</span>
          </div>
        </div>
      </div>

      <div class="drh-card reveal">
        <p class="drh-quote">« La déductibilité fiscale à 100% et la facturation trimestrielle claire nous permettent de maîtriser nos coûts RH tout en offrant un avantage social majeur qui attire les meilleurs ingénieurs tech de la région. »</p>
        <div class="drh-profile">
          <div class="drh-avatar" style="background:linear-gradient(135deg,#1E293B,#334155);color:#fff;display:grid;place-items:center;font:700 16px var(--font-b);border:2px solid #64748B;box-shadow:var(--shadow-sm)">DM</div>
          <div class="drh-info">
            <h4>Dieudonné Mukendi</h4>
            <span>Directeur Administratif &amp; Financier (Kinshasa)</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<script>
/* Moteur de Calcul B2B Dynamique */
const empSlider = $('#empRange');
function calcB2B() {
  const count = parseInt(empSlider.value, 10);
  $('#empCountDisplay').textContent = count + ' salarié' + (count > 1 ? 's' : '');

  let discountPct = 0;
  let unitPriceXAF = 30000;
  let discountLabel = 'Tarif standard';

  if (count >= 100) {
    discountPct = 25;
    unitPriceXAF = 22500;
    discountLabel = '25 % de remise Grands Comptes';
  } else if (count >= 25) {
    discountPct = 20;
    unitPriceXAF = 24000;
    discountLabel = '20 % de remise PME';
  } else if (count >= 10) {
    discountPct = 10;
    unitPriceXAF = 27000;
    discountLabel = '10 % de remise Équipe';
  }

  const totalXAF = unitPriceXAF * count;
  const unitPriceEUR = Math.round(unitPriceXAF / 655.957);
  const totalEUR = Math.round(totalXAF / 655.957);

  $('#b2bDiscountLabel').textContent = discountLabel;
  $('#b2bUnitPriceDisplay').textContent = cur === 'XAF' 
    ? `${unitPriceXAF.toLocaleString('fr-FR')} FCFA / mois (≈ ${unitPriceEUR} €)`
    : `${fmt(unitPriceEUR)} / salarié / mois`;

  $('#b2bTotalDisplay').textContent = cur === 'XAF'
    ? `${totalXAF.toLocaleString('fr-FR')} FCFA / mois`
    : `${fmt(totalEUR)} / mois`;
}

if(empSlider) {
  empSlider.addEventListener('input', calcB2B);
  calcB2B();
}

/* Soumission formulaire B2B avec Toast */
const formB2B = $('#formB2B');
if(formB2B) {
  formB2B.addEventListener('submit', (e) => {
    e.preventDefault();
    const company = $('#b2bCompany').value.trim();
    const contact = $('#b2bContact').value.trim();
    const email = $('#b2bEmail').value.trim();
    const phone = $('#b2bPhone').value.trim();
    const count = empSlider.value;

    toast('Demande RH enregistrée', `Merci ${contact} ! Notre direction Grands Comptes a bien reçu votre demande pour ${company} (${count} salariés) et vous contactera sous 24h.`, 'success');
    formB2B.reset();
  });
}
</script>
