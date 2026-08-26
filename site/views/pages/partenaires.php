<style>
/* ================= PAGE PARTENAIRES & CONVENTIONNEMENT SANTÉ ================= */
.part-hero{position:relative;background:var(--bg);background-image:radial-gradient(rgba(9,114,104,.08) 1px,transparent 1px);background-size:22px 22px;border-bottom:1px solid var(--line);padding:72px 0 84px;overflow:hidden}
.part-hero-in{position:relative;z-index:1;display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center}
.part-hero h1{font-size:clamp(2.3rem,4.4vw,3.6rem);font-weight:800;color:var(--ink);margin:20px 0 18px;line-height:1.16}
.part-hero h1 .hl{background:linear-gradient(transparent 62%,var(--gold-100) 62%);border-radius:3px;padding:0 3px}
.part-hero-sub{font-size:17px;color:var(--ink-2);line-height:1.6;margin-bottom:30px;max-width:35rem}
.part-hero-cta{display:flex;gap:14px;flex-wrap:wrap}

.part-badges{display:flex;gap:18px;flex-wrap:wrap;margin-top:32px;padding-top:24px;border-top:1px solid var(--line)}
.part-badge{display:flex;align-items:center;gap:8px;font:600 13px var(--font-b);color:var(--ink-2)}
.part-badge svg{width:16px;height:16px;color:var(--emerald);flex:none}

.part-hero-visual{position:relative}
.part-hero-card-frame{position:relative;background:#fff;border:1.5px solid var(--line);border-radius:24px;padding:16px;box-shadow:var(--shadow-2)}
.part-hero-img-wrap{position:relative;border-radius:18px;overflow:hidden;background:#0F172A;height:340px}
.part-hero-img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .3s}
.part-hero-card-frame:hover .part-hero-img{transform:scale(1.02)}

.part-float-top{position:absolute;top:28px;right:28px;background:rgba(255,255,255,.94);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:12px;padding:8px 14px;box-shadow:var(--shadow-1);display:flex;align-items:center;gap:8px}
.part-float-top b{font-size:12.5px;color:var(--ink);font-weight:700}
.part-float-top .pulse-dot{width:7px;height:7px;border-radius:50%;background:#10B981}

.part-hero-overlay-card{margin-top:14px;background:var(--emerald-050);border:1px solid var(--emerald-100);border-radius:14px;padding:14px 18px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.part-hero-overlay-card .part-ov-left b{display:block;font-size:14.5px;color:var(--emerald-900);font-weight:700}
.part-hero-overlay-card .part-ov-left span{font-size:12px;color:var(--emerald);font-weight:500}
.part-hero-overlay-card .part-ov-badge{background:var(--emerald);color:#fff;font:700 11px var(--font-b);padding:5px 11px;border-radius:99px;white-space:nowrap}

/* ================= PILIERS POUR ÉTABLISSEMENTS ================= */
.part-pillars-sec{background:#fff;padding:88px 0;border-bottom:1px solid var(--line)}
.part-pillars-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:24px}
.part-card{background:var(--bg);border:1.5px solid var(--line);border-radius:20px;padding:28px 24px;display:flex;flex-direction:column;gap:12px;transition:transform .2s,box-shadow .2s}
.part-card:hover{transform:translateY(-4px);box-shadow:var(--shadow-1);border-color:#CBD5E1}
.part-ic{width:46px;height:46px;border-radius:12px;background:var(--emerald-050);color:var(--emerald);display:grid;place-items:center;margin-bottom:4px}
.part-ic svg{width:22px;height:22px}
.part-card h3{font-size:17px;font-weight:700;color:var(--ink)}
.part-card p{font-size:13.5px;color:var(--ink-2);line-height:1.55}

/* ================= SECTION FORMULAIRE & CONTACT CONVENTIONNEMENT ================= */
.part-form-grid{display:grid;grid-template-columns:1fr 1.15fr;gap:44px;align-items:start}

.part-left-col{display:flex;flex-direction:column;gap:24px}
.part-info-card{background:#fff;border:1.5px solid var(--line);border-radius:22px;padding:28px;box-shadow:var(--shadow-sm)}
.part-info-card h3{font-size:17px;font-weight:700;color:var(--ink);margin-bottom:16px;display:flex;align-items:center;gap:10px}

/* Étapes Onboarding */
.part-steps-list{display:flex;flex-direction:column;gap:16px}
.part-step-item{display:flex;gap:14px;align-items:flex-start}
.part-step-badge{width:28px;height:28px;border-radius:8px;background:var(--emerald-050);color:var(--emerald);font:800 13px var(--font-n);display:grid;place-items:center;flex:none}
.part-step-text h4{font-size:14.5px;font-weight:700;color:var(--ink);margin:0 0 3px}
.part-step-text p{font-size:13px;color:var(--ink-3);margin:0;line-height:1.5}

/* Bloc Contact Médical Direct */
.part-contact-box{background:linear-gradient(135deg,#062C27 0%,#093C35 100%);color:#fff;border-radius:22px;padding:28px;border:1.5px solid rgba(255,255,255,.15);box-shadow:var(--shadow-1)}
.part-contact-box h3{font-size:18px;font-weight:800;color:#fff;margin-bottom:8px;display:flex;align-items:center;gap:10px}
.part-contact-box p{font-size:13.5px;color:rgba(255,255,255,.8);line-height:1.55;margin-bottom:20px}
.part-contact-channels{display:flex;flex-direction:column;gap:12px;margin-bottom:20px}
.part-contact-item{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.08);padding:10px 14px;border-radius:12px;border:1px solid rgba(255,255,255,.12);font-size:13.5px;color:#fff}
.part-contact-item svg{width:18px;height:18px;color:#5EEAD4;flex:none}
.part-contact-item b{font-weight:700}

/* Formulaire Box */
.part-form-box{background:#fff;border:1.5px solid var(--line);border-radius:24px;padding:34px;box-shadow:var(--shadow-1)}
.field{display:flex;flex-direction:column;gap:7px}
.field label{font:600 13px var(--font-b);color:var(--ink-2)}
.field input,.field select,.field textarea{width:100%;padding:11px 14px;border:1.5px solid var(--line);border-radius:12px;font:500 14px var(--font-b);color:var(--ink);background:var(--bg);outline:none;transition:border-color .18s,background .18s}
.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--emerald);background:#fff}
.f-grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}

@media(max-width:960px){
  .part-hero-in,.part-form-grid{grid-template-columns:1fr}
  .part-pillars-grid{grid-template-columns:1fr 1fr}
  .f-grid2{grid-template-columns:1fr}
}
@media(max-width:600px){
  .part-pillars-grid{grid-template-columns:1fr}
}

/* ================= ADAPTATION MOBILE (≤ 760px) ================= */
@media(max-width:760px){
  .part-hero{padding:36px 0 52px}
  .part-hero h1{font-size:clamp(1.95rem,8.2vw,2.5rem);margin:16px 0 14px}
  .part-hero-sub{font-size:15.5px;margin-bottom:24px}
  .part-hero-cta{gap:10px}
  .part-hero-cta .btn{flex:1 1 100%;min-height:50px}
  .part-badges{gap:12px 18px;margin-top:24px;padding-top:20px}

  .part-hero-visual,.part-hero-visual *{min-width:0}
  .part-hero-card-frame{padding:12px;border-radius:20px}
  .part-hero-img-wrap{height:210px;border-radius:14px}
  .part-float-top{top:20px;right:20px;padding:6px 11px}
  .part-float-top b{font-size:11.5px}
  .part-hero-overlay-card{flex-wrap:wrap;padding:13px 15px;gap:10px}

  .part-pillars-sec{padding:56px 0}
  .part-card{padding:22px 18px}

  .part-form-grid{gap:24px}
  .part-form-grid>*,.part-left-col,.part-left-col>*{min-width:0}
  .part-info-card,.part-contact-box{padding:22px 17px;border-radius:18px}
  .part-contact-item{padding:11px 13px;font-size:13px;overflow-wrap:anywhere}
  .part-form-box{padding:22px 17px;border-radius:18px}
  .part-form-box .btn{min-height:50px}
  /* Sur iOS, une police < 16px déclenche un zoom automatique à la saisie */
  .field input,.field select,.field textarea{font-size:16px}
}
</style>

<!-- ═══════════ HERO CONVENTIONNEMENT ═══════════ -->
<section class="part-hero">
  <div class="wrap part-hero-in">
    <div>
      <span class="badge-agr"><i data-lucide="handshake"></i>Espace Professionnels de Santé · Réseau Agréé</span>
      <h1>Devenez Établissement Conventionné, <span class="hl">Règlement sous 72 h</span>.</h1>
      <p class="part-hero-sub">Rejoignez le 1er réseau de tiers-payant en Afrique subsaharienne. Supprimez les risques d'impayés, accueillez plus de 12 400 assurés solvables et validez les prises en charge en 0.2 seconde via QR Code.</p>
      <div class="part-hero-cta">
        <a class="btn btn-primary" href="#conventionForm"><i data-lucide="file-signature"></i>Postuler au conventionnement</a>
        <a class="btn btn-ghost" href="https://wa.me/33659513458?text=<?= urlencode("Bonjour, je représente un établissement de santé et souhaite échanger sur le conventionnement MulemaCare.") ?>" target="_blank" rel="noopener"><i data-lucide="message-square"></i>Contacter la Direction Médicale</a>
      </div>
      <div class="part-badges">
        <span class="part-badge"><i data-lucide="shield-check"></i>Agrément CSSA Garanti</span>
        <span class="part-badge"><i data-lucide="clock"></i>Règlement sous 72 h</span>
        <span class="part-badge"><i data-lucide="users"></i>12 400+ Patients Solvables</span>
      </div>
    </div>

    <!-- Panneau de Conventionnement Professionnel (Design Iconique Uni) -->
    <div class="part-hero-visual reveal">
      <div style="background:#0B132B;color:#fff;border-radius:24px;border:1.5px solid rgba(255,255,255,.12);padding:32px;box-shadow:0 24px 48px -12px rgba(6,74,67,.35);position:relative;overflow:hidden">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;padding-bottom:18px;border-bottom:1px solid rgba(255,255,255,.1)">
          <span style="display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);padding:6px 14px;border-radius:99px;font:700 12px var(--font-b);color:#5EEAD4">
            <span class="pulse-dot"></span>Protocole d'Agrément Réseau
          </span>
          <span style="font:600 12px var(--font-b);color:#94A3B8">Agrément CSSA n° 045</span>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:24px">
          <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;display:flex;align-items:flex-start;gap:12px">
            <i data-lucide="banknote" style="width:22px;height:22px;color:#5EEAD4;flex:none;margin-top:2px"></i>
            <div>
              <b style="display:block;font-size:14px;font-weight:700;color:#fff;margin-bottom:2px">Paiement en 72 h</b>
              <span style="font-size:11.5px;color:#94A3B8;line-height:1.4">Virement bancaire ou Mobile Money Entreprise</span>
            </div>
          </div>
          <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;display:flex;align-items:flex-start;gap:12px">
            <i data-lucide="qr-code" style="width:22px;height:22px;color:#5EEAD4;flex:none;margin-top:2px"></i>
            <div>
              <b style="display:block;font-size:14px;font-weight:700;color:#fff;margin-bottom:2px">Validation en 0.2 s</b>
              <span style="font-size:11.5px;color:#94A3B8;line-height:1.4">Scan immédiat sans accord préalable papier</span>
            </div>
          </div>
          <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;display:flex;align-items:flex-start;gap:12px">
            <i data-lucide="users" style="width:22px;height:22px;color:#5EEAD4;flex:none;margin-top:2px"></i>
            <div>
              <b style="display:block;font-size:14px;font-weight:700;color:#fff;margin-bottom:2px">12 400+ Adhérents</b>
              <span style="font-size:11.5px;color:#94A3B8;line-height:1.4">Flux régulier de patients pris en charge</span>
            </div>
          </div>
          <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;display:flex;align-items:flex-start;gap:12px">
            <i data-lucide="headphones" style="width:22px;height:22px;color:#5EEAD4;flex:none;margin-top:2px"></i>
            <div>
              <b style="display:block;font-size:14px;font-weight:700;color:#fff;margin-bottom:2px">Support Dédié 24/7</b>
              <span style="font-size:11.5px;color:#94A3B8;line-height:1.4">Hotline médicale réservée aux praticiens</span>
            </div>
          </div>
        </div>
        <div style="background:rgba(9,114,104,.2);border:1px solid rgba(94,234,212,.25);border-radius:14px;padding:14px 18px;display:flex;align-items:center;justify-content:space-between;gap:14px">
          <div>
            <b style="display:block;font-size:13.5px;color:#ECFDF8;font-weight:700">Direction Médicale MulemaCare</b>
            <span style="font-size:11.5px;color:#99F6E4">Conventionnement simple sous 48h</span>
          </div>
          <a href="#conventionner" class="btn btn-sm btn-primary" style="white-space:nowrap;padding:8px 14px;font-size:12px">
            Postuler
          </a>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ LOGOS DES ÉTABLISSEMENTS AGRÉÉS ═══════════ -->
<div class="partner-logos-bar" style="background:#fff;border-bottom:1px solid var(--line);padding:20px 0;overflow:hidden">
  <div class="wrap" style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;justify-content:space-between">
    <span style="font:700 11.5px var(--font-b);letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);white-space:nowrap;display:flex;align-items:center;gap:7px">
      <i data-lucide="building-2" style="width:16px;height:16px;color:var(--emerald)"></i>Réseau &amp; Partenaires Agréés :
    </span>
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:center">
      <div class="partner-badge-pill" style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:100px;font:700 12px var(--font-b);color:var(--ink);transition:all .2s">
        <i data-lucide="shield-check" style="width:14px;height:14px;color:#0D9488"></i>
        <span>MFDI Assurances</span>
      </div>
      <div class="partner-badge-pill" style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:100px;font:700 12px var(--font-b);color:var(--ink);transition:all .2s">
        <i data-lucide="hospital" style="width:14px;height:14px;color:#097268"></i>
        <span>Polyclinique Sainte-Anne</span>
      </div>
      <div class="partner-badge-pill" style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:100px;font:700 12px var(--font-b);color:var(--ink);transition:all .2s">
        <i data-lucide="pill" style="width:14px;height:14px;color:#059669"></i>
        <span>Pharmacie Centrale du Golfe</span>
      </div>
      <div class="partner-badge-pill" style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:100px;font:700 12px var(--font-b);color:var(--ink);transition:all .2s">
        <i data-lucide="flask-conical" style="width:14px;height:14px;color:#0284C7"></i>
        <span>Laboratoire BioSanté</span>
      </div>
      <div class="partner-badge-pill" style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:100px;font:700 12px var(--font-b);color:var(--ink);transition:all .2s">
        <i data-lucide="activity" style="width:14px;height:14px;color:#D97706"></i>
        <span>Ivory Health Network</span>
      </div>
      <div class="partner-badge-pill" style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:100px;font:700 12px var(--font-b);color:var(--ink);transition:all .2s">
        <i data-lucide="heart-pulse" style="width:14px;height:14px;color:#DC2626"></i>
        <span>Centre Médical International</span>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════ SECTION 01 : PILIERS & ENGAGEMENTS MULEMACARE ═══════════ -->
<section class="sec" style="background:#fff;border-bottom:1px solid var(--line)">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">01</span>
      <div>
        <p class="eyebrow">Les Avantages Partenaire</p>
        <h2>Pourquoi les cliniques et pharmacies nous rejoignent.</h2>
        <p class="sec-sub">Une relation contractuelle claire, transparente et optimisée pour sécuriser votre trésorerie médicale.</p>
      </div>
    </div>
    <div class="part-pillars-grid">
      <div class="part-card reveal">
        <div class="part-ic"><i data-lucide="banknote"></i></div>
        <h3>Règlement sous 72 h Garanti</h3>
        <p>Virement bancaire ou Mobile Money Entreprise garanti sous 72 heures ouvrées après réception du bordereau de soins.</p>
      </div>
      <div class="part-card reveal">
        <div class="part-ic" style="background:var(--gold-100);color:#92400E"><i data-lucide="qr-code"></i></div>
        <h3>Validation Digitale en 0.2 s</h3>
        <p>Scannez la carte CSSA de l'assuré depuis votre smartphone ou ordinateur. Accord préalable instantané sans attente téléphonique.</p>
      </div>
      <div class="part-card reveal">
        <div class="part-ic" style="background:var(--blue-050);color:var(--blue-800)"><i data-lucide="users"></i></div>
        <h3>Afflux de Nouveaux Patients</h3>
        <p>Orientation prioritaire de nos adhérents (diaspora, familles locales et salariés de nos 140+ entreprises clientes).</p>
      </div>
      <div class="part-card reveal">
        <div class="part-ic" style="background:var(--emerald-050);color:var(--emerald)"><i data-lucide="shield-check"></i></div>
        <h3>Zéro Risque de Créance</h3>
        <p>MulemaCare Health Group prend en charge 100% du risque financier pour les actes garantis dans le contrat.</p>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ SECTION 02 : FORMULAIRE DE CANDIDATURE & CONTACT MÉDICAL ═══════════ -->
<section class="sec" id="conventionForm" style="background:linear-gradient(180deg,#F8FAFC 0%,#EEF8F6 100%)">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">02</span>
      <div>
        <p class="eyebrow">Dossier de Conventionnement</p>
        <h2>Conventionnez votre structure en 3 étapes.</h2>
        <p class="sec-sub">Remplissez le formulaire ci-dessous ou contactez directement notre Direction Médicale pour un échange préalable.</p>
      </div>
    </div>

    <div class="part-form-grid">
      
      <!-- Colonne Gauche : Démarches & Contact Médical Direct -->
      <div class="part-left-col reveal">
        
        <!-- Bloc Démarche en 3 Étapes -->
        <div class="part-info-card">
          <h3><i data-lucide="list-ordered" style="color:var(--emerald)"></i>Processus de Conventionnement</h3>
          <div class="part-steps-list">
            <div class="part-step-item">
              <span class="part-step-badge">1</span>
              <div class="part-step-text">
                <h4>Dépôt du Dossier en Ligne</h4>
                <p>Soumettez le formulaire avec les coordonnées de votre structure et votre agrément ministériel.</p>
              </div>
            </div>
            <div class="part-step-item">
              <span class="part-step-badge">2</span>
              <div class="part-step-text">
                <h4>Audit &amp; Signature Convention</h4>
                <p>Échange avec notre médecin régulateur sous 48h et signature du protocole de tiers-payant 72h.</p>
              </div>
            </div>
            <div class="part-step-item">
              <span class="part-step-badge">3</span>
              <div class="part-step-text">
                <h4>Activation Réseau &amp; QR Code</h4>
                <p>Intégration sur l'annuaire MulemaCare et accueil immédiat de vos premiers patients conventionnés.</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Bloc Contact Direct Direction Médicale -->
        <div class="part-contact-box">
          <h3><i data-lucide="headset" style="color:#5EEAD4"></i>Direction Médicale Dédiée</h3>
          <p>Un interlocuteur médecin régulateur dédié est à votre disposition pour vous présenter les modalités de partenariat et d'intégration logicielle.</p>
          
          <div class="part-contact-channels">
            <div class="part-contact-item">
              <i data-lucide="phone-call"></i>
              <div><b>Hotline Médicale :</b> +33 6 59 51 34 58 / +237 6 52 11 20 21</div>
            </div>
            <div class="part-contact-item">
              <i data-lucide="mail"></i>
              <div><b>Email :</b> direction.medicale@mulemacare.com</div>
            </div>
            <div class="part-contact-item">
              <i data-lucide="clock"></i>
              <div><b>Délai de réponse :</b> Sous 48 heures ouvrées</div>
            </div>
          </div>

          <a href="https://wa.me/33659513458?text=<?= urlencode("Bonjour Docteur, je représente un établissement de santé et souhaite échanger sur le conventionnement tiers-payant MulemaCare.") ?>" target="_blank" rel="noopener" class="btn btn-white btn-block">
            <i data-lucide="message-square"></i>Échanger directement sur WhatsApp
          </a>
        </div>

        <!-- Critères d'Agrément Réseau -->
        <div class="part-info-card">
          <h3><i data-lucide="shield-check" style="color:var(--emerald)"></i>Critères d'Agrément Réseau</h3>
          <div class="part-steps-list">
            <div class="part-step-item">
              <div class="part-ic" style="width:34px;height:34px;border-radius:8px;flex:none;margin:0"><i data-lucide="award" style="width:17px;height:17px"></i></div>
              <div class="part-step-text">
                <h4>Agrément Ministériel Officiel</h4>
                <p>Autorisation d'ouverture délivrée par le Ministère de la Santé du pays d'exercice.</p>
              </div>
            </div>
            <div class="part-step-item">
              <div class="part-ic" style="width:34px;height:34px;border-radius:8px;flex:none;margin:0"><i data-lucide="stethoscope" style="width:17px;height:17px"></i></div>
              <div class="part-step-text">
                <h4>Médecin / Pharmacien Inscrit à l'Ordre</h4>
                <p>Directeur médical ou titulaire inscrit au Conseil National de l'Ordre.</p>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- Colonne Droite : Formulaire de Candidature Convention -->
      <div class="part-form-box reveal">
        <h3 style="font-size:22px;font-weight:800;color:var(--ink);margin-bottom:6px">Dossier de Candidature Partenaire</h3>
        <p style="font-size:13.5px;color:var(--ink-3);margin-bottom:24px">Remplissez les informations administratives de votre structure.</p>

        <form id="formPartenaire" style="display:flex;flex-direction:column;gap:14px">
          
          <div class="field">
            <label for="pName">Nom officiel de l'établissement *</label>
            <input type="text" id="pName" required placeholder="Ex. Polyclinique Sainte-Marie, Pharmacie du Centre…">
          </div>

          <div class="f-grid2">
            <div class="field">
              <label for="pType">Type d'établissement *</label>
              <select id="pType" required>
                <option value="clinique">Polyclinique / Clinique Médico-Chirurgicale</option>
                <option value="hopital">Hôpital de Référence / Centre Hospitalier</option>
                <option value="pharmacie">Pharmacie d'Officine</option>
                <option value="laboratoire">Laboratoire de Biologie Médicale</option>
                <option value="imagerie">Centre d'Imagerie / Radiologie</option>
                <option value="dentaire">Cabinet Dentaire / Optique</option>
              </select>
            </div>
            <div class="field">
              <label for="pCountry">Pays d'implantation *</label>
              <select id="pCountry" required>
                <option value="Cameroun">Cameroun 🇨🇲</option>
                <option value="RDC">RDC (Congo Kinshasa) 🇨🇩</option>
                <option value="Côte d'Ivoire">Côte d'Ivoire 🇨🇮</option>
                <option value="Sénégal">Sénégal 🇸🇳</option>
                <option value="Gabon">Gabon 🇬🇦</option>
                <option value="Congo">Congo Brazzaville 🇨🇬</option>
              </select>
            </div>
          </div>

          <div class="f-grid2">
            <div class="field">
              <label for="pCity">Ville *</label>
              <input type="text" id="pCity" required placeholder="Ex. Douala, Abidjan, Kinshasa…">
            </div>
            <div class="field">
              <label for="pDistrict">Quartier / Adresse *</label>
              <input type="text" id="pDistrict" required placeholder="Ex. Bonapriso, Cocody, Gombe…">
            </div>
          </div>

          <div class="f-grid2">
            <div class="field">
              <label for="pDoctor">Directeur Médical / Responsable *</label>
              <input type="text" id="pDoctor" required placeholder="Dr. Prénom Nom">
            </div>
            <div class="field">
              <label for="pRegNo">N° d'Agrément ou N° d'Ordre *</label>
              <input type="text" id="pRegNo" required placeholder="Ex. 048/MINSANTE/2023">
            </div>
          </div>

          <div class="f-grid2">
            <div class="field">
              <label for="pPhone">Téléphone Direct / WhatsApp Pro *</label>
              <input type="tel" id="pPhone" required placeholder="+237 6XX XX XX XX">
            </div>
            <div class="field">
              <label for="pEmail">Email Professionnel *</label>
              <input type="email" id="pEmail" required placeholder="direction@clinique.com">
            </div>
          </div>

          <div class="field">
            <label for="pNotes">Spécialités médicales &amp; Équipements clés</label>
            <textarea id="pNotes" rows="3" placeholder="Ex. Urgences 24/7, Bloc opératoire, Scanner, Maternité, 25 lits..."></textarea>
          </div>

          <button type="submit" class="btn btn-primary btn-block" style="margin-top:8px">
            <i data-lucide="send"></i>Soumettre ma candidature de conventionnement
          </button>
        </form>
      </div>

    </div>
  </div>
</section>

<script>
/* Soumission Formulaire Convention Partenaire avec Toast & Feedback */
const formPart = $('#formPartenaire');
if(formPart) {
  formPart.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = $('#pName').value.trim();
    const city = $('#pCity').value.trim();
    const doctor = $('#pDoctor').value.trim();

    toast('Candidature Enregistrée !', `Merci ${doctor}. Le dossier de conventionnement pour ${name} (${city}) a bien été transmis à notre Direction Médicale. Vous serez contacté sous 48h.`, 'success');
    formPart.reset();
  });
}
</script>
