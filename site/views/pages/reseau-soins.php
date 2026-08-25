<style>
/* ================= PAGE RÉSEAU DE SOINS & ANNUAIRE MÉDICAL ================= */
.dir-hero{position:relative;background:var(--bg);background-image:radial-gradient(rgba(9,114,104,.08) 1px,transparent 1px);background-size:22px 22px;border-bottom:1px solid var(--line);padding:72px 0 84px;overflow:hidden}
.dir-hero-in{position:relative;z-index:1;display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center}
.dir-hero h1{font-size:clamp(2.3rem,4.4vw,3.6rem);font-weight:800;color:var(--ink);margin:20px 0 18px;line-height:1.16}
.dir-hero h1 .hl{background:linear-gradient(transparent 62%,var(--gold-100) 62%);border-radius:3px;padding:0 3px}
.dir-hero p{font-size:17px;color:var(--ink-2);line-height:1.6;margin-bottom:30px;max-width:35rem}

.dir-stats{display:flex;gap:16px;flex-wrap:wrap;margin-top:28px;padding-top:22px;border-top:1px solid var(--line)}
.dir-stat{background:#fff;border:1.5px solid var(--line);border-radius:14px;padding:12px 18px;display:flex;flex-direction:column;box-shadow:var(--shadow-sm)}
.dir-stat b{font:800 22px var(--font-n);color:var(--emerald);letter-spacing:-.02em}
.dir-stat span{font:600 12px var(--font-b);color:var(--ink-3)}

/* Hero Hub Card (remplace les images de stock par un panneau unifié interactif) */
.dir-hero-hub{position:relative}
.dir-hub-card{background:#0B132B;color:#fff;border-radius:24px;border:1.5px solid rgba(255,255,255,.12);padding:32px;box-shadow:0 24px 48px -12px rgba(6,74,67,.35);position:relative;overflow:hidden}
.dir-hub-card::before{content:"";position:absolute;top:-60px;right:-60px;width:180px;height:180px;border-radius:50%;background:radial-gradient(circle,rgba(94,234,212,.18),transparent 70%);pointer-events:none}
.dir-hub-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;padding-bottom:18px;border-bottom:1px solid rgba(255,255,255,.1)}
.dir-hub-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);padding:6px 14px;border-radius:99px;font:700 12px var(--font-b);color:#5EEAD4}
.dir-hub-badge .pulse-dot{width:7px;height:7px;border-radius:50%;background:#34D399;box-shadow:0 0 0 3px rgba(52,211,153,.25)}
.dir-hub-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:24px}
.dir-hub-box{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:16px;display:flex;align-items:flex-start;gap:12px}
.dir-hub-box svg{width:22px;height:22px;color:#5EEAD4;flex:none;margin-top:2px}
.dir-hub-box b{display:block;font-size:14px;font-weight:700;color:#fff;margin-bottom:2px}
.dir-hub-box span{font-size:11.5px;color:#94A3B8;line-height:1.4}
.dir-hub-foot{background:rgba(9,114,104,.2);border:1px solid rgba(94,234,212,.25);border-radius:14px;padding:14px 18px;display:flex;align-items:center;justify-content:space-between;gap:14px}
.dir-hub-foot-txt b{display:block;font-size:13.5px;color:#ECFDF8;font-weight:700}
.dir-hub-foot-txt span{font-size:11.5px;color:#99F6E4}
.dir-hub-tag{background:#0D9488;color:#fff;font:800 11px var(--font-b);padding:5px 12px;border-radius:99px;white-space:nowrap}

/* ================= SECTION RECHERCHE & FILTRES ================= */
.dir-search-sec{background:#fff;padding:48px 0 20px;border-bottom:1px solid var(--line)}
.dir-bar-wrap{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}
.dir-input-box{flex:1;min-width:280px;position:relative}
.dir-input-box svg{position:absolute;left:16px;top:50%;transform:translateY(-50%);width:18px;height:18px;color:var(--ink-3)}
.dir-input-box input{width:100%;height:50px;padding:0 18px 0 46px;border-radius:14px;border:1.5px solid var(--line);background:var(--bg);font:500 15px var(--font-b);color:var(--ink);outline:none;transition:border-color .2s}
.dir-input-box input:focus{border-color:var(--emerald);background:#fff}

.dir-chips-wrap{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-bottom:14px}
.dir-chip{background:var(--bg);border:1.5px solid var(--line);border-radius:99px;padding:8px 16px;font:600 13px var(--font-b);color:var(--ink-2);cursor:pointer;transition:all .15s}
.dir-chip:hover{background:#E2E8F0;color:var(--ink)}
.dir-chip.active{background:var(--emerald);color:#fff;border-color:var(--emerald)}

/* ================= GRILLE DES ÉTABLISSEMENTS (ICÔNES UNIES) ================= */
.dir-grid-sec{background:var(--bg);padding:48px 0 88px}
.dir-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:26px}
.clinic-card{background:#fff;border:1.5px solid var(--line);border-radius:20px;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between;box-shadow:var(--shadow-sm);transition:transform .2s,box-shadow .2s}
.clinic-card:hover{transform:translateY(-4px);box-shadow:var(--shadow-1);border-color:#CBD5E1}

/* Bandeau Icône Unie */
.clinic-icon-hero{position:relative;height:130px;padding:16px;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden}
.clinic-icon-hero.type-clinic{background:linear-gradient(135deg,#063C36 0%,#09574D 100%)}
.clinic-icon-hero.type-pharmacy{background:linear-gradient(135deg,#0C4A43 0%,#0D9488 100%)}
.clinic-icon-hero.type-center{background:linear-gradient(135deg,#1E293B 0%,#334155 100%)}

.clinic-icon-bg-sym{position:absolute;right:-10px;bottom:-15px;opacity:.14;pointer-events:none}
.clinic-icon-bg-sym svg{width:110px;height:110px;color:#fff}

.clinic-top-row{display:flex;align-items:center;justify-content:space-between;position:relative;z-index:2}
.clinic-badge-type{display:inline-flex;align-items:center;gap:6px;background:rgba(0,0,0,.35);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.2);color:#5EEAD4;font:700 11px var(--font-b);padding:4px 10px;border-radius:8px;letter-spacing:.02em}
.clinic-badge-type svg{width:13px;height:13px}
.clinic-badge-tp{display:inline-flex;align-items:center;gap:5px;background:#047857;color:#fff;font:800 10.5px var(--font-b);padding:4px 9px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.clinic-badge-tp svg{width:12px;height:12px}

.clinic-mid-icon{display:flex;align-items:center;gap:12px;position:relative;z-index:2}
.clinic-icon-circle{width:46px;height:46px;border-radius:12px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);display:grid;place-items:center;color:#fff;flex:none}
.clinic-icon-circle svg{width:24px;height:24px}
.clinic-hero-loc{color:#E2E8F0;font:600 12.5px var(--font-b)}

.clinic-body{padding:22px}
.clinic-title{font-size:18px;font-weight:800;color:var(--ink);margin:0 0 8px;line-height:1.3}
.clinic-services{font-size:13.5px;color:var(--ink-2);line-height:1.55;margin-bottom:16px}
.clinic-features{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:18px}
.clinic-feat{background:var(--bg);border:1px solid var(--line);border-radius:6px;font:500 11.5px var(--font-b);color:var(--ink-2);padding:3px 8px}

.clinic-foot{padding:0 22px 22px;display:flex;gap:10px}
.clinic-foot .btn{flex:1;font-size:13px;padding:10px 14px;justify-content:center}

/* ================= BANNIÈRE CONVENTIONNEMENT ================= */
.dir-cta-box{background:linear-gradient(135deg,#062C27 0%,#093C35 100%);color:#fff;border-radius:24px;padding:48px 36px;display:flex;align-items:center;justify-content:space-between;gap:32px;margin-top:56px;border:1.5px solid rgba(255,255,255,.15);box-shadow:var(--shadow-1)}
.dir-cta-box h3{font-size:24px;font-weight:800;color:#fff;margin-bottom:8px}
.dir-cta-box p{font-size:15px;color:rgba(255,255,255,.82);margin:0;max-width:32rem;line-height:1.55}

@media(max-width:960px){
  .dir-hero-in{grid-template-columns:1fr}
  .dir-hub-grid{grid-template-columns:1fr}
  .dir-grid{grid-template-columns:1fr}
  .dir-cta-box{flex-direction:column;text-align:center}
}
</style>

<!-- ═══════════ HERO ANNUAIRE ═══════════ -->
<section class="dir-hero">
  <div class="wrap dir-hero-in">
    <div>
      <span class="badge-agr"><i data-lucide="map-pin"></i>Réseau de Santé Agréé CSSA · Tiers-Payant Direct</span>
      <h1>L'Annuaire Médical &amp; Réseau Tiers-Payant <span class="hl">en Afrique</span>.</h1>
      <p>Présentez votre carte mutuelle digitale CSSA dans plus de 45 cliniques, hôpitaux, centres d'imagerie et pharmacies conventionnées. Prise en charge immédiate avec dispense totale d'avance de frais.</p>
      <div class="dir-stats">
        <div class="dir-stat"><b>45+</b><span>Cliniques &amp; Pharmacies</span></div>
        <div class="dir-stat"><b>5</b><span>Pays Couverts</span></div>
        <div class="dir-stat"><b>0 F</b><span>Avancé par l'Assuré</span></div>
        <div class="dir-stat"><b>0.2 s</b><span>Vérification QR</span></div>
      </div>
    </div>

    <!-- Panneau Interactif du Réseau Agréé (Design Iconique Uni) -->
    <div class="dir-hero-hub reveal">
      <div class="dir-hub-card">
        <div class="dir-hub-top">
          <span class="dir-hub-badge"><span class="pulse-dot"></span>Réseau Conventionné Direct</span>
          <span style="font:600 12px var(--font-b);color:#94A3B8">Agrément CSSA n° 045</span>
        </div>
        <div class="dir-hub-grid">
          <div class="dir-hub-box">
            <i data-lucide="shield-check"></i>
            <div>
              <b>Tiers-Payant 100%</b>
              <span>Zéro avance de frais sur hospitalisations &amp; actes</span>
            </div>
          </div>
          <div class="dir-hub-box">
            <i data-lucide="qr-code"></i>
            <div>
              <b>Validation en 0.2 s</b>
              <span>Scan instantané de la carte digitale CSSA</span>
            </div>
          </div>
          <div class="dir-hub-box">
            <i data-lucide="building-2"></i>
            <div>
              <b>45+ Établissements</b>
              <span>Cliniques réputées, imagerie &amp; pharmacies</span>
            </div>
          </div>
          <div class="dir-hub-box">
            <i data-lucide="clock"></i>
            <div>
              <b>Urgences 24/7</b>
              <span>Prise en charge sans délai d'attente</span>
            </div>
          </div>
        </div>
        <div class="dir-hub-foot">
          <div class="dir-hub-foot-txt">
            <b>Orientation Médicale &amp; Prise en Charge</b>
            <span>Assistance Lisacare joignable 24h/24 par WhatsApp</span>
          </div>
          <a href="https://wa.me/33659513458?text=<?= urlencode("Bonjour Lisacare, je souhaite être orienté vers une clinique partenaire.") ?>" target="_blank" rel="noopener" class="dir-hub-tag">
            Contacter
          </a>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ SECTION 01 : RECHERCHE ET FILTRES ═══════════ -->
<section class="sec" id="recherche" style="background:#fff;border-bottom:1px solid var(--line)">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">01</span>
      <div>
        <p class="eyebrow">Recherche &amp; Filtres Géographiques</p>
        <h2>Trouvez une clinique ou pharmacie agréée près de chez vous.</h2>
        <p class="sec-sub">Recherche instantanée au clavier et filtrage par métropole (Douala, Yaoundé, Kinshasa, Abidjan, Dakar).</p>
      </div>
    </div>

    <div class="dir-bar-wrap">
      <div class="dir-input-box">
        <i data-lucide="search"></i>
        <input type="text" id="dirSearchInput" placeholder="Rechercher par clinique, quartier, médecin, spécialité (ex. Akwa, Mermoz, Cardiologie)…">
      </div>
    </div>

    <!-- Filtres Villes & Pays -->
    <div class="dir-chips-wrap">
      <button type="button" class="dir-chip active" data-city="all">🌍 Tous les Établissements</button>
      <button type="button" class="dir-chip" data-city="douala">🇨🇲 Douala</button>
      <button type="button" class="dir-chip" data-city="yaounde">🇨🇲 Yaoundé</button>
      <button type="button" class="dir-chip" data-city="kinshasa">🇨🇩 Kinshasa</button>
      <button type="button" class="dir-chip" data-city="abidjan">🇨🇮 Abidjan</button>
      <button type="button" class="dir-chip" data-city="dakar">🇸🇳 Dakar</button>
    </div>
  </div>
</section>

<!-- ═══════════ SECTION 02 : GRILLE DES CLINIQUES & PHARMACIES (ICÔNES UNIES) ═══════════ -->
<section class="sec" id="etablissements" style="background:var(--bg)">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">02</span>
      <div>
        <p class="eyebrow">Réseau Médical Agréé</p>
        <h2>Établissements &amp; Réseau Tiers-Payant Partenaires.</h2>
        <p class="sec-sub">Présentez votre QR Code d'assuré MulemaCare pour une validation immédiate en 0.2 seconde sans avance de frais.</p>
      </div>
    </div>

    <div class="dir-grid" id="clinicGrid">
      <?php foreach ($clinics as $cityKey => $cityData): ?>
        <?php foreach ($cityData['partners'] as $partner): 
          $isPharm = str_contains(strtolower($partner['type'] . ' ' . $partner['name']), 'pharmacie');
          $isCenter = str_contains(strtolower($partner['type'] . ' ' . $partner['name']), 'centre') || str_contains(strtolower($partner['type'] . ' ' . $partner['name']), 'labo');
          
          $heroClass = $isPharm ? 'type-pharmacy' : ($isCenter ? 'type-center' : 'type-clinic');
          $iconName = $isPharm ? 'pill' : ($isCenter ? 'flask-conical' : 'building-2');
          $symIcon = $isPharm ? 'heart-pulse' : ($isCenter ? 'activity' : 'hospital');
        ?>
          <article class="clinic-card" data-city="<?= $cityKey ?>" data-keywords="<?= strtolower($partner['name'] . ' ' . $partner['district'] . ' ' . $partner['type'] . ' ' . $partner['services'] . ' ' . $cityData['city']) ?>">
            <div class="clinic-icon-hero <?= $heroClass ?>">
              <div class="clinic-icon-bg-sym">
                <i data-lucide="<?= $symIcon ?>"></i>
              </div>
              <div class="clinic-top-row">
                <span class="clinic-badge-type">
                  <i data-lucide="<?= $iconName ?>"></i>
                  <?= htmlspecialchars($partner['type']) ?>
                </span>
                <span class="clinic-badge-tp">
                  <i data-lucide="shield-check"></i>
                  100% TIERS-PAYANT
                </span>
              </div>
              <div class="clinic-mid-icon">
                <div class="clinic-icon-circle">
                  <i data-lucide="<?= $iconName ?>"></i>
                </div>
                <div class="clinic-hero-loc">
                  <?= htmlspecialchars($partner['district']) ?>, <?= htmlspecialchars($cityData['city']) ?> <?= $cityData['flag'] ?>
                </div>
              </div>
            </div>

            <div class="clinic-body">
              <h3 class="clinic-title"><?= htmlspecialchars($partner['name']) ?></h3>
              <p class="clinic-services"><?= htmlspecialchars($partner['services']) ?></p>
              <div class="clinic-features">
                <span class="clinic-feat">Urgences 24/7</span>
                <span class="clinic-feat">Carte QR Acceptée</span>
                <span class="clinic-feat">Dispense de Frais</span>
              </div>
            </div>

            <div class="clinic-foot">
              <a href="https://www.google.com/maps/search/?api=1&query=<?= urlencode($partner['name'] . ' ' . $partner['district'] . ' ' . $cityData['city']) ?>" target="_blank" rel="noopener" class="btn btn-ghost btn-sm">
                <i data-lucide="navigation"></i>Itinéraire
              </a>
              <a href="https://wa.me/33659513458?text=<?= urlencode("Bonjour Lisacare, je souhaite vérifier ma prise en charge à l'établissement {$partner['name']} ({$cityData['city']}).") ?>" target="_blank" rel="noopener" class="btn btn-primary btn-sm">
                <i data-lucide="message-square"></i>Vérifier
              </a>
            </div>
          </article>
        <?php endforeach; ?>
      <?php endforeach; ?>
    </div>

    <!-- SECTION 03 : Bannière Devenir Partenaire -->
    <div class="dir-cta-box reveal" id="convention" style="margin-top:72px">
      <div>
        <div class="sec-head" style="margin-bottom:12px">
          <span class="sec-index" style="color:rgba(255,255,255,.2)">03</span>
          <div>
            <p class="eyebrow" style="color:#5EEAD4">Espace Professionnels de Santé</p>
            <h3 style="font-size:24px;font-weight:800;color:#fff;margin-bottom:8px">Vous dirigez une clinique, un hôpital ou une pharmacie ?</h3>
            <p style="font-size:15px;color:rgba(255,255,255,.82);margin:0;max-width:34rem;line-height:1.55">Rejoignez le 1er réseau de tiers-payant en Afrique subsaharienne. Règlement sous 72h garanti, validation en 0.2s et apport régulier de nouveaux patients solvables.</p>
          </div>
        </div>
      </div>
      <a href="/partenaires" class="btn btn-white" style="white-space:nowrap;flex:none">
        <i data-lucide="file-signature"></i>Devenir Établissement Conventionné
      </a>
    </div>

  </div>
</section>

<script>
/* Filtrage en direct de l'Annuaire (Villes + Mots-clés) */
const dirSearch = $('#dirSearchInput');
const cityChips = $$('.dir-chip');
let activeCity = 'all';

function filterClinics() {
  const query = dirSearch ? dirSearch.value.toLowerCase().trim() : '';
  const cards = $$('.clinic-card');

  cards.forEach(card => {
    const cardCity = card.dataset.city;
    const cardKw = card.dataset.keywords;

    const cityMatch = (activeCity === 'all' || cardCity === activeCity);
    const searchMatch = (query === '' || cardKw.includes(query));

    card.style.display = (cityMatch && searchMatch) ? 'flex' : 'none';
  });
}

if(dirSearch) {
  dirSearch.addEventListener('input', filterClinics);
}

cityChips.forEach(chip => {
  chip.addEventListener('click', () => {
    cityChips.forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    activeCity = chip.dataset.city;
    filterClinics();
  });
});
</script>
