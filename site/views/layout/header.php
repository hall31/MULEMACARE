<!DOCTYPE html>
<html lang="fr" dir="ltr" itemscope itemtype="https://schema.org/MedicalOrganization">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<?= $seo->renderMetaTags() ?>

<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23097268'/%3E%3Crect x='13' y='6' width='6' height='20' rx='3' fill='white'/%3E%3Crect x='6' y='13' width='20' height='6' rx='3' fill='white'/%3E%3Cpath d='M7 16h5l2-3.5 3 7 2-3.5h6' stroke='%23D97706' stroke-width='2' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Inter:wght@500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.min.js"></script>
<script src="https://unpkg.com/lucide@0.462.0/dist/umd/lucide.min.js"></script>

<!-- Google tag (gtag.js) - Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-NWCD16MREK"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-NWCD16MREK');
</script>

<style>
/* ================= TOKENS MULEMACARE ================= */
:root{
  --emerald-900:#064A43; --emerald:#097268; --emerald-500:#0D9488;
  --emerald-050:#F0FAF8; --emerald-100:#D9F1EC;
  --blue-800:#1E40AF; --blue-050:#EFF6FF;
  --gold-600:#D97706; --gold-100:#FEF3C7; --gold-050:#FFFDF6;
  --bg:#F8FAFC; --card:#FFFFFF; --ink:#0F172A; --ink-2:#334155; --ink-3:#64748B;
  --line:#E2E8F0; --line-2:#EEF2F7;
  --font-h:'Outfit',sans-serif; --font-b:'Plus Jakarta Sans',sans-serif; --font-n:'Inter',sans-serif;
  --r-lg:20px; --r-md:14px; --r-sm:10px;
  --shadow-1:0 1px 2px rgba(15,23,42,.05),0 8px 24px rgba(15,23,42,.06);
  --shadow-2:0 12px 40px -12px rgba(6,74,67,.28);
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:var(--font-b);background:var(--bg);color:var(--ink);line-height:1.6;-webkit-font-smoothing:antialiased}
img,svg{display:block}
a{color:inherit;text-decoration:none}
button{font-family:inherit;cursor:pointer}
input,select{font-family:inherit}
section{scroll-margin-top:84px}
.wrap{max-width:1200px;margin:0 auto;padding:0 24px}
h1,h2,h3,h4{font-family:var(--font-h);line-height:1.15;letter-spacing:-.02em}
.num{font-family:var(--font-n);font-variant-numeric:tabular-nums;letter-spacing:-.01em}
:focus-visible{outline:2.5px solid var(--emerald-500);outline-offset:2px;border-radius:6px}
::selection{background:var(--emerald-100)}

/* ================= DESIGN SYSTEM : EN-TÊTES DE SECTION & INDEXATION ================= */
.sec{padding:88px 0;position:relative}
.sec-head{display:flex;gap:26px;align-items:flex-start;margin-bottom:52px}
.sec-index{font:800 52px var(--font-h);color:var(--line);line-height:.9;flex:none;letter-spacing:-.04em}
.eyebrow{display:flex;align-items:center;gap:10px;font:700 12.5px var(--font-b);letter-spacing:.16em;text-transform:uppercase;color:var(--emerald);margin-bottom:12px}
.eyebrow::before{content:"";width:26px;height:2.5px;background:var(--gold-600);border-radius:2px}
.sec-head h2{font-size:clamp(1.7rem,3.1vw,2.5rem);font-weight:700;color:var(--ink);margin-bottom:12px;letter-spacing:-.02em}
.sec-head h2 .hl{background:linear-gradient(transparent 62%,var(--gold-100) 62%);border-radius:3px;padding:0 3px}
.sec-sub{color:var(--ink-3);font-size:16px;max-width:44rem;line-height:1.6}
@media(max-width:640px){.sec{padding:60px 0}.sec-index{font-size:38px}.sec-head{gap:16px;margin-bottom:36px}}

/* ================= DESIGN SYSTEM : BANDE STATS & METRIQUES ================= */
.stats-band{background:#fff;border-bottom:1px solid var(--line)}
.stats-list{display:flex;flex-wrap:wrap;padding:30px 0}
.stat{flex:1 1 150px;padding:6px 26px;display:flex;flex-direction:column;gap:2px;border-left:1px solid var(--line)}
.stat:first-child{border-left:0;padding-left:0}
.stat b{font:700 30px var(--font-h);color:var(--emerald);letter-spacing:-.03em;line-height:1.1}
.stat span{font:500 13px var(--font-b);color:var(--ink-3)}
@media(max-width:860px){.stat{flex:1 1 40%;padding:12px 20px;border-left:0}.stat:nth-child(even){border-left:1px solid var(--line)}}

/* ================= DESIGN SYSTEM : CADRES HERO & VISUELS ================= */
.pro-hero-card-frame,.dir-hero-card-frame,.part-hero-card-frame{position:relative;background:#fff;border:1.5px solid var(--line);border-radius:24px;padding:16px;box-shadow:var(--shadow-2)}
.pro-hero-img-wrap,.dir-hero-img-wrap,.part-hero-img-wrap{position:relative;border-radius:18px;overflow:hidden;background:#0F172A;height:340px}
.pro-hero-img,.dir-hero-img,.part-hero-img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .3s}
.pro-hero-card-frame:hover .pro-hero-img,.dir-hero-card-frame:hover .dir-hero-img,.part-hero-card-frame:hover .part-hero-img{transform:scale(1.02)}

/* ================= BOUTONS ================= */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;font:600 15px var(--font-b);padding:13px 22px;border-radius:12px;border:1.5px solid transparent;transition:transform .18s,box-shadow .18s,background .18s,border-color .18s,color .18s;white-space:nowrap}
.btn svg{width:17px;height:17px}
.btn-primary{background:var(--emerald);color:#fff}
.btn-primary:hover{background:var(--emerald-500);transform:translateY(-1.5px);box-shadow:0 10px 22px -6px rgba(9,114,104,.45)}
.btn-ghost{background:#fff;border-color:var(--line);color:var(--ink)}
.btn-ghost:hover{border-color:var(--emerald-500);color:var(--emerald);transform:translateY(-1.5px)}
.btn-white{background:#fff;color:var(--emerald-900)}
.btn-white:hover{transform:translateY(-1.5px);box-shadow:0 12px 26px -8px rgba(0,0,0,.35)}
.btn-outline-w{background:transparent;border-color:rgba(255,255,255,.4);color:#fff}
.btn-outline-w:hover{border-color:#fff;background:rgba(255,255,255,.08)}
.btn-sm{padding:9px 14px;font-size:13.5px;border-radius:var(--r-sm)}
.btn-block{width:100%}
.btn[disabled]{opacity:.55;pointer-events:none}
.link-arrow{display:inline-flex;align-items:center;gap:7px;font-weight:600;color:var(--emerald);font-size:15px}
.link-arrow svg{width:16px;height:16px;transition:transform .18s}
.link-arrow:hover svg{transform:translateX(4px)}

/* ================= SEGMENTED ================= */
.seg{display:inline-flex;background:#F1F5F9;border:1px solid var(--line);border-radius:11px;padding:3px;gap:2px}
.seg button{border:0;background:transparent;padding:7px 13px;border-radius:8px;font:600 13px var(--font-b);color:var(--ink-3);transition:.16s}
.seg button.on{background:#fff;color:var(--emerald);box-shadow:0 1px 3px rgba(15,23,42,.14)}
.seg-dark{background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.18)}
.seg-dark button{color:rgba(255,255,255,.65)}
.seg-dark button.on{background:#fff;color:var(--emerald-900)}

/* ================= TOPBAR ================= */
.topbar{background:var(--emerald-900);color:#D7F0EA;font-size:13px;height:40px;display:flex;align-items:center;overflow:hidden}
.tb-inner{max-width:1200px;margin:0 auto;width:100%;padding:0 24px;display:flex;align-items:center;justify-content:center}
.tb-flow{display:flex;align-items:center;gap:10px;white-space:nowrap}
.tb-flow .lucide-globe{width:14px;height:14px;color:#5EEAD4;flex:none}
.pulse-dot{width:7px;height:7px;border-radius:50%;background:#34D399;flex:none;position:relative}
.pulse-dot::after{content:"";position:absolute;inset:-4px;border-radius:50%;border:1.5px solid #34D399;animation:ping 2s ease-out infinite}
@keyframes ping{0%{transform:scale(.4);opacity:1}80%,100%{transform:scale(1.25);opacity:0}}
.tb-flow b{color:#fff}
.tb-seq{display:inline-flex;align-items:center;gap:10px}
@media(max-width:767px){
  .topbar{height:36px}
  .tb-inner{padding:0;justify-content:flex-start}
  .tb-flow{animation:tbmar 24s linear infinite}
  .tb-seq{padding-right:60px}
  .tb-flow:hover{animation-play-state:paused}
}
@keyframes tbmar{from{transform:translateX(0)}to{transform:translateX(-50%)}}

/* ================= HEADER ================= */
header.site{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.9);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid transparent;transition:border-color .25s,box-shadow .25s}
header.site.scrolled{border-color:var(--line);box-shadow:0 6px 24px -18px rgba(15,23,42,.25)}
.h-in{max-width:1200px;margin:0 auto;padding:0 24px;height:70px;display:flex;align-items:center;gap:28px}
.logo{display:flex;align-items:center;gap:10px;flex:none}
.logo svg{width:36px;height:36px}
.logo-txt b{display:block;font:700 19px var(--font-h);color:var(--ink);letter-spacing:-.02em;line-height:1}
.logo-txt b i{font-style:normal;color:var(--emerald)}
.logo-txt span{font:600 9.5px var(--font-b);letter-spacing:.22em;color:var(--ink-3);text-transform:uppercase}
nav.main{display:flex;gap:26px;margin:0 auto}
nav.main a{font:600 14.5px var(--font-b);color:var(--ink-2);position:relative;padding:6px 0}
nav.main a::after{content:"";position:absolute;left:0;bottom:0;width:0;height:2px;background:var(--emerald-500);border-radius:2px;transition:width .2s}
nav.main a:hover,nav.main a.active{color:var(--emerald)}
nav.main a:hover::after,nav.main a.active::after{width:100%}
.h-right{display:flex;align-items:center;gap:14px;flex:none}
.burger{display:none;background:none;border:1.5px solid var(--line);border-radius:10px;width:42px;height:42px;place-items:center;color:var(--ink)}
.burger svg{width:20px;height:20px}
.m-nav{display:none}
@media(max-width:960px){
  nav.main,.h-right .seg{display:none}
  .burger{display:grid}
  .m-nav{display:block;position:absolute;top:70px;left:0;right:0;background:#fff;border-bottom:1px solid var(--line);box-shadow:var(--shadow-1);padding:14px 24px 22px;transform:translateY(-8px);opacity:0;pointer-events:none;transition:.22s}
  header.site.open .m-nav{transform:none;opacity:1;pointer-events:auto}
  .m-nav a{display:flex;align-items:center;justify-content:space-between;padding:13px 4px;font:600 15px var(--font-b);color:var(--ink-2);border-bottom:1px solid var(--line-2)}
  .m-nav a svg{width:16px;height:16px;color:var(--ink-3)}
  .m-nav .btn{margin-top:16px}
}
</style>

<?= $seo->renderSchemaOrgJsonLd() ?>
</head>
<body>

<!-- ═══════════ TOP BAR DIASPORA ═══════════ -->
<div class="topbar" role="note">
  <div class="tb-inner">
    <div class="tb-flow" id="tbFlow">
      <span class="tb-seq"><span class="pulse-dot"></span><i data-lucide="globe" aria-hidden="true"></i>Diaspora &amp; Afrique Centrale / Ouest : <b>tiers-payant 100 %</b> sans avance de frais dans 45+ cliniques partenaires · Adhésion en ligne dès <b class="num" data-base-eur="23">23 €</b> par mois</span>
      <span class="tb-seq" aria-hidden="true"><span class="pulse-dot"></span><i data-lucide="globe" aria-hidden="true"></i>Diaspora &amp; Afrique Centrale / Ouest : <b>tiers-payant 100 %</b> sans avance de frais dans 45+ cliniques partenaires · Adhésion en ligne dès <b class="num" data-base-eur="23">23 €</b> par mois</span>
    </div>
  </div>
</div>

<?php
$reqPath = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?? '/';
$isEntreprises = ($reqPath === '/entreprises' || str_starts_with($reqPath, '/mutuelle-entreprises'));
$isReseau = ($reqPath === '/reseau-soins' || $reqPath === '/annuaire');
$isPartenaires = ($reqPath === '/partenaires' || $reqPath === '/devenir-partenaire');
$isAdherent = str_starts_with($reqPath, '/espace-adherent');
$isAdmin = str_starts_with($reqPath, '/admin');
?>

<!-- ═══════════ HEADER ═══════════ -->
<header class="site" id="siteHeader">
  <div class="h-in">
    <a href="/" class="logo" id="logoHome" aria-label="MulemaCare — retour en haut de page">
      <img src="/assets/img/logo.png" alt="MulemaCare" height="42" style="height:42px;width:auto;display:block">
    </a>
    <nav class="main" aria-label="Navigation principale">
      <a href="/#simulateur">Simulateur</a>
      <a href="/#garanties">Garanties</a>
      <a href="/entreprises" class="<?= $isEntreprises ? 'active' : '' ?>">Entreprises</a>
      <a href="/reseau-soins" class="<?= $isReseau ? 'active' : '' ?>">Annuaire</a>
      <a href="/partenaires" class="<?= $isPartenaires ? 'active' : '' ?>">Partenaires</a>
      <a href="/espace-adherent" class="<?= $isAdherent ? 'active' : '' ?>">Espace Adhérent</a>
    </nav>
    <div class="h-right">
      <div class="seg" data-cur-seg role="group" aria-label="Choix de la devise">
        <button type="button" data-cur="EUR" class="on">€ EUR</button>
        <button type="button" data-cur="USD">$ USD</button>
        <button type="button" data-cur="XAF">FCFA</button>
      </div>
      <button class="btn btn-primary btn-sm" data-open-sub><i data-lucide="badge-check"></i>Adhérer</button>
      <button class="burger" id="burger" aria-label="Ouvrir le menu" aria-expanded="false"><i data-lucide="menu"></i></button>
    </div>
  </div>
  <div class="m-nav" id="mNav">
    <a href="/#simulateur">Simulateur<i data-lucide="arrow-right"></i></a>
    <a href="/#garanties">Garanties<i data-lucide="arrow-right"></i></a>
    <a href="/entreprises" class="<?= $isEntreprises ? 'active' : '' ?>">Entreprises &amp; PME<i data-lucide="arrow-right"></i></a>
    <a href="/reseau-soins" class="<?= $isReseau ? 'active' : '' ?>">Annuaire Cliniques &amp; Pharmacies<i data-lucide="arrow-right"></i></a>
    <a href="/partenaires" class="<?= $isPartenaires ? 'active' : '' ?>">Devenir Établissement Partenaire<i data-lucide="arrow-right"></i></a>
    <a href="/espace-adherent" class="<?= $isAdherent ? 'active' : '' ?>">Espace Adhérent<i data-lucide="arrow-right"></i></a>
    <a href="/admin" class="<?= $isAdmin ? 'active' : '' ?>">Tour de Contrôle Admin<i data-lucide="arrow-right"></i></a>
    <div class="seg" data-cur-seg role="group" aria-label="Choix de la devise" style="margin:12px 0">
      <button type="button" data-cur="EUR" class="on">€ EUR</button>
      <button type="button" data-cur="USD">$ USD</button>
      <button type="button" data-cur="XAF">FCFA</button>
    </div>
    <button class="btn btn-primary btn-block" data-open-sub><i data-lucide="badge-check"></i>Adhérer en 2 minutes</button>
  </div>
</header>

<main id="main">
