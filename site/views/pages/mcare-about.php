<?php
declare(strict_types=1);
$skus = $this->config['mcare']['skus'] ?? [];
?>
<style>
.mcare-about{padding:48px 0 80px;background:var(--bg,#F6F9FB)}
.mcare-hero{max-width:720px;margin:0 auto 40px;text-align:center}
.mcare-hero h1{font:800 clamp(1.8rem,4vw,2.6rem)/1.15 Outfit,sans-serif;color:#0F172A;margin-bottom:12px}
.mcare-hero h1 i{font-style:normal;color:#097268}
.mcare-hero p{color:#64748B;font-size:16px;margin-bottom:22px}
.sku-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;max-width:1000px;margin:0 auto}
.sku{background:#fff;border:1.5px solid #E2E8F0;border-radius:18px;padding:22px}
.sku h3{font:800 18px Outfit,sans-serif;margin-bottom:8px;color:#097268}
.sku p{font-size:14px;color:#64748B;margin-bottom:12px}
@media(max-width:800px){.sku-grid{grid-template-columns:1fr}}
</style>
<div class="breadcrumb"><div class="wrap"><a href="/">Accueil</a> <span>/</span> <b style="color:#097268">MCare</b></div></div>
<main class="mcare-about">
  <div class="wrap">
    <div class="mcare-hero">
      <h1>M<i>Care</i> — le chat santé de votre famille au pays</h1>
      <p>Posez la question en français. L’assistant oriente (couverture, réseau, triage). Un médecin humain valide. Jamais de diagnostic final IA.</p>
      <a class="btn btn-primary" href="/login/adherent?next=/mcare">Ouvrir MCare</a>
      <a class="btn btn-secondary" href="/adhesion" style="margin-left:8px">Souscrire</a>
    </div>
    <div class="sku-grid">
      <?php foreach ($skus as $id => $sku): ?>
      <div class="sku">
        <h3><?= htmlspecialchars((string) ($sku['label'] ?? $id)) ?></h3>
        <p>Quota transmissions médecin : <b><?= (int) ($sku['quota'] ?? 0) ?> / mois</b>
          <?php if (!empty($sku['addon_eur'])): ?> · add-on <?= (int) $sku['addon_eur'] ?> €<?php endif; ?></p>
        <p style="font-size:13px">Plans : <?= htmlspecialchars(implode(', ', $sku['plans'] ?? [])) ?></p>
      </div>
      <?php endforeach; ?>
    </div>
  </div>
</main>
