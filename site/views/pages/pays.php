<?php
$countrySlug = $countrySlug ?? 'cameroun';
$countryInfo = $countryInfo ?? [
    'name' => 'Cameroun',
    'flag' => '🇨🇲',
    'cities' => 'Douala, Yaoundé, Bafoussam',
    'clinics_count' => 18,
    'currency' => 'FCFA (XAF)',
    'price_from' => '15 000 FCFA',
    'price_eur' => '23 €',
    'momo' => 'Orange Money (#150*1*1*52112021*) & MTN MoMo (*126*1*65145837*)',
    'headline' => 'La Mutuelle Santé n°1 au Cameroun sans Avance de Frais',
    'sub' => 'Tiers-payant direct à la Polyclinique Mermoz, Clinique de l\'Étoile, Centre Médico-Chirurgical d\'Akwa et Pharmacie des Nations.',
];
?>

<style>
/* ================= PAGE PAYS & DIASPORA DÉDIÉE ================= */
.pays-hero{position:relative;background:var(--emerald-900);color:#ECFDF8;padding:76px 0 84px;border-bottom:1px solid rgba(255,255,255,.1);overflow:hidden}
.pays-hero-in{position:relative;z-index:1;display:grid;grid-template-columns:1.2fr .8fr;gap:48px;align-items:center}
.pays-hero h1{font-size:clamp(2.2rem,4vw,3.4rem);font-weight:800;color:#fff;margin:18px 0 16px;line-height:1.18}
.pays-hero h1 .hl{background:linear-gradient(transparent 62%,rgba(217,119,6,.4) 62%);border-radius:3px;padding:0 3px}
.pays-hero-sub{font-size:17px;color:rgba(255,255,255,.85);line-height:1.6;margin-bottom:28px;max-width:36rem}

.pays-kpi-card{background:rgba(255,255,255,.08);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1.5px solid rgba(255,255,255,.15);border-radius:22px;padding:30px;box-shadow:0 24px 48px -16px rgba(0,0,0,.45)}
.pays-kpi-card h3{font-size:19px;color:#fff;margin-bottom:14px;display:flex;align-items:center;gap:10px}
.pays-kpi-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0}
.pays-kpi-item{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px}
.pays-kpi-item span{display:block;font:600 11px var(--font-b);text-transform:uppercase;color:#A7F3D0;margin-bottom:4px}
.pays-kpi-item b{font:800 19px var(--font-n);color:#fff}

.pays-clinics-sec{padding:80px 0;background:#fff}
.pays-clinics-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(320px,100%),1fr));gap:22px;margin-top:36px}
.pays-clinic-card{background:var(--bg);border:1.5px solid var(--line);border-radius:18px;padding:22px;transition:.18s}
.pays-clinic-card:hover{border-color:var(--emerald);transform:translateY(-3px);box-shadow:var(--shadow-1)}

@media(max-width:960px){
  .pays-hero-in{grid-template-columns:1fr}
}

/* ================= ADAPTATION MOBILE (≤ 760px) ================= */
@media(max-width:760px){
  .pays-hero{padding:38px 0 52px}
  .pays-hero-in{gap:30px}
  .pays-hero h1{font-size:clamp(1.9rem,8vw,2.4rem);margin:14px 0 13px}
  .pays-hero-sub{font-size:15.5px;margin-bottom:22px}
  .pays-hero .btn{width:100%;justify-content:center;min-height:50px}

  .pays-kpi-card{padding:20px 17px;border-radius:19px}
  .pays-kpi-card h3{font-size:17px}
  .pays-kpi-grid{gap:10px;margin:16px 0}
  .pays-kpi-item{padding:11px}
  .pays-kpi-item b{font-size:17px}

  .pays-clinics-sec{padding:52px 0}
  .pays-clinics-grid{grid-template-columns:1fr;gap:14px;margin-top:26px}
  .pays-clinic-card{padding:17px 16px}
  .pays-clinic-card button,.pays-clinic-card .btn{min-height:44px}
}
</style>

<!-- ═══════════ HERO PAYS ═══════════ -->
<section class="pays-hero">
  <div class="wrap pays-hero-in">
    <div>
      <span class="badge-agr" style="background:rgba(255,255,255,.12);border-color:rgba(255,255,255,.2);color:#A7F3D0">
        <span style="font-size:18px"><?= $countryInfo['flag'] ?></span> MulemaCare <?= htmlspecialchars($countryInfo['name']) ?> · Tiers-Payant Agréé
      </span>
      <h1><?= htmlspecialchars($countryInfo['headline']) ?></h1>
      <p class="pays-hero-sub"><?= htmlspecialchars($countryInfo['sub']) ?></p>
      <div style="display:flex;gap:14px;flex-wrap:wrap">
        <button class="btn btn-white" data-open-sub><i data-lucide="badge-check"></i>Adhérer dès <?= htmlspecialchars($countryInfo['price_eur']) ?> / mois</button>
        <a class="btn btn-outline-w" href="/#simulateur"><i data-lucide="calculator"></i>Simuler ma cotisation</a>
      </div>
      <div style="display:flex;gap:20px;margin-top:28px;padding-top:20px;border-top:1px solid rgba(255,255,255,.15);flex-wrap:wrap;font-size:13px;color:rgba(255,255,255,.85)">
        <span><i data-lucide="shield-check" style="width:14px;height:14px;display:inline;color:#5EEAD4"></i> Agrément CSSA n° 045</span>
        <span><i data-lucide="phone" style="width:14px;height:14px;display:inline;color:#5EEAD4"></i> Télétriage Lisacare 24/7</span>
        <span><i data-lucide="credit-card" style="width:14px;height:14px;display:inline;color:#5EEAD4"></i> Mobile Money &amp; CB</span>
      </div>
    </div>

    <div class="pays-kpi-card">
      <h3><span style="font-size:22px"><?= $countryInfo['flag'] ?></span> Couverture <?= htmlspecialchars($countryInfo['name']) ?></h3>
      <p style="font-size:13.5px;color:rgba(255,255,255,.8);line-height:1.5">Réseau médical conventionné et disponible immédiatement :</p>
      <div class="pays-kpi-grid">
        <div class="pays-kpi-item"><span>Cliniques</span><b><?= htmlspecialchars((string)$countryInfo['clinics_count']) ?> Partenaires</b></div>
        <div class="pays-kpi-item"><span>Tiers-Payant</span><b>0 F Avancé</b></div>
        <div class="pays-kpi-item"><span>Dès</span><b><?= htmlspecialchars($countryInfo['price_from']) ?></b></div>
        <div class="pays-kpi-item"><span>Villes</span><b><?= htmlspecialchars($countryInfo['cities']) ?></b></div>
      </div>
      <div style="background:rgba(255,255,255,.1);border-radius:12px;padding:12px 14px;font-size:12.5px;color:#D7F0EA">
        <b>Paiements locaux acceptés :</b><br><?= htmlspecialchars($countryInfo['momo']) ?>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ RÉSEAU CLINIQUE DU PAYS ═══════════ -->
<section class="pays-clinics-sec">
  <div class="wrap">
    <div class="sec-head">
      <span class="sec-index">01</span>
      <div>
        <p class="eyebrow">Réseau Local Conventionné</p>
        <h2>Établissements partenaires en <?= htmlspecialchars($countryInfo['name']) ?> <?= $countryInfo['flag'] ?></h2>
        <p class="sec-sub">Présentez simplement le QR Code de votre Carte Mutuelle Digitale CSSA pour une prise en charge immédiate.</p>
      </div>
    </div>

    <div class="pays-clinics-grid">
      <div class="pays-clinic-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:12px;font-weight:700;color:var(--emerald);background:var(--emerald-050);padding:3px 9px;border-radius:6px">Tiers-Payant 100%</span>
          <span style="font-size:13px;font-weight:700;color:#D97706"><i data-lucide="star" style="width:13px;height:13px;display:inline"></i> 4.8/5</span>
        </div>
        <h3 style="font-size:17px;font-weight:700;margin-bottom:4px">Hôpital &amp; Polyclinique de Référence</h3>
        <p style="font-size:13.5px;color:var(--ink-3);margin-bottom:12px"><i data-lucide="map-pin" style="width:13px;height:13px;display:inline"></i> <?= htmlspecialchars($countryInfo['cities']) ?></p>
        <div style="font-size:12.5px;color:var(--ink-2);display:flex;gap:6px;flex-wrap:wrap">
          <span style="background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 7px">Urgences 24/7</span>
          <span style="background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 7px">Chirurgie</span>
          <span style="background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 7px">Maternité</span>
        </div>
      </div>

      <div class="pays-clinic-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:12px;font-weight:700;color:var(--emerald);background:var(--emerald-050);padding:3px 9px;border-radius:6px">Pharmacie Agréée</span>
          <span style="font-size:13px;font-weight:700;color:#D97706"><i data-lucide="star" style="width:13px;height:13px;display:inline"></i> 4.7/5</span>
        </div>
        <h3 style="font-size:17px;font-weight:700;margin-bottom:4px">Pharmacie Principale Conventionnée</h3>
        <p style="font-size:13.5px;color:var(--ink-3);margin-bottom:12px"><i data-lucide="map-pin" style="width:13px;height:13px;display:inline"></i> Centre-ville &amp; Quartiers majeurs</p>
        <div style="font-size:12.5px;color:var(--ink-2);display:flex;gap:6px;flex-wrap:wrap">
          <span style="background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 7px">Délivrance directe</span>
          <span style="background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 7px">Anti-contrefaçon</span>
          <span style="background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 7px">Garde de nuit</span>
        </div>
      </div>

      <div class="pays-clinic-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:12px;font-weight:700;color:#1E40AF;background:var(--blue-050);padding:3px 9px;border-radius:6px">Téléconsultation Inclus</span>
          <span style="font-size:13px;font-weight:700;color:#D97706"><i data-lucide="star" style="width:13px;height:13px;display:inline"></i> 4.9/5</span>
        </div>
        <h3 style="font-size:17px;font-weight:700;margin-bottom:4px">Lisacare Desk Médical WhatsApp</h3>
        <p style="font-size:13.5px;color:var(--ink-3);margin-bottom:12px"><i data-lucide="phone-call" style="width:13px;height:13px;display:inline"></i> Accessible partout en <?= htmlspecialchars($countryInfo['name']) ?></p>
        <div style="font-size:12.5px;color:var(--ink-2);display:flex;gap:6px;flex-wrap:wrap">
          <span style="background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 7px">Médecin de garde</span>
          <span style="background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 7px">Réponse en 4 min</span>
          <span style="background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 7px">Ordonnance PDF</span>
        </div>
      </div>
    </div>

    <div style="text-align:center;margin-top:40px">
      <button class="btn btn-primary btn-lg" data-open-sub><i data-lucide="shield-plus"></i>Protéger ma famille en <?= htmlspecialchars($countryInfo['name']) ?></button>
    </div>
  </div>
</section>
