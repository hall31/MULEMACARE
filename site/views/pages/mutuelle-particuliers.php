<style>
/* ================= ADAPTATION MOBILE (≤ 760px) ================= */
@media(max-width:760px){
  .mp-compare{overflow-x:auto;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;margin-inline:-16px;padding-inline:16px}
  .mp-compare table{min-width:680px !important}
  .mp-compare th,.mp-compare td{padding:13px 12px !important;font-size:13px !important}
  .mp-cta .btn{width:100%;white-space:normal;line-height:1.35;text-align:center;padding:15px 20px !important;min-height:54px}
  .mp-cta{padding:22px 0 !important}
  .seg{flex-wrap:wrap;justify-content:center}
}
</style>

<!-- ================= HERO MUTUELLE PARTICULIERS & DIASPORA ================= -->
<section class="sec" style="background:linear-gradient(180deg,#F8FAFC 0%,#EEF8F6 100%);border-bottom:1px solid var(--line);padding:72px 0 84px">
  <div class="wrap">
    <div style="max-width:820px;margin:0 auto;text-align:center">
      <span class="badge-agr" style="margin-bottom:18px"><i data-lucide="shield-check"></i> Assurance Santé Solidaire Afrique &amp; Diaspora</span>
      <h1 style="font-size:clamp(2.3rem,4.2vw,3.6rem);font-weight:800;color:var(--ink);margin-bottom:18px;line-height:1.16">
        La Mutuelle Santé sans Avance de Frais <span class="hl">pour toute la Famille</span>.
      </h1>
      <p style="font-size:17px;color:var(--ink-2);line-height:1.6;margin-bottom:28px">
        Protégez vos enfants, votre conjoint et vos parents au pays grâce à nos 4 formules modulables. Tiers-payant 100% dans 45+ cliniques et téléconsultations Lisacare 24/7 incluses.
      </p>

      <div class="seg" style="margin-bottom:12px">
        <button type="button" class="on" data-curr="XAF" onclick="setGlobalCurrency('XAF')">🇨🇲 FCFA (XAF)</button>
        <button type="button" data-curr="EUR" onclick="setGlobalCurrency('EUR')">💶 Euros (EUR)</button>
        <button type="button" data-curr="USD" onclick="setGlobalCurrency('USD')">💵 Dollars (USD)</button>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ SECTION 01 : TABLEAU COMPARATIF DES GARANTIES ═══════════ -->
<section class="sec" id="garanties" style="background:#fff;border-bottom:1px solid var(--line)">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">01</span>
      <div>
        <p class="eyebrow">Comparateur Détaillé</p>
        <h2>Tableau Comparatif &amp; Plafonds des 4 Formules.</h2>
        <p class="sec-sub">Comparez les plafonds annuels, les délais de carence, les actes couverts et les niveaux de dispense d'avance de frais.</p>
      </div>
    </div>

    <p class="table-hint"><i data-lucide="move-horizontal"></i>Faites glisser le tableau vers la gauche pour comparer les 4 formules</p>
    <div class="mp-compare" style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;min-width:780px;background:#fff;border-radius:20px;overflow:hidden;box-shadow:var(--shadow-sm);border:1.5px solid var(--line)">
        <thead>
          <tr style="background:#064A43;color:#fff;text-align:left">
            <th style="padding:20px;font-size:15px;font-weight:700">Prestations &amp; Garanties</th>
            <th style="padding:20px;font-size:15px;font-weight:700;text-align:center">Bronze (Urgences)</th>
            <th style="padding:20px;font-size:15px;font-weight:800;text-align:center;background:#097268">Silver ⭐ (Famille)</th>
            <th style="padding:20px;font-size:15px;font-weight:700;text-align:center">Gold (Confort)</th>
            <th style="padding:20px;font-size:15px;font-weight:700;text-align:center">Platinium (Monde)</th>
          </tr>
        </thead>
        <tbody style="font-size:14.5px;color:var(--ink-2)">
          <tr style="border-bottom:1px solid var(--line);background:#F8FAFC">
            <td style="padding:16px 20px;font-weight:700;color:var(--ink)">Cotisation Solo / mois</td>
            <td style="padding:16px 20px;text-align:center;font-weight:800"><span data-plan-price="bronze" data-plan-comp="solo">15 000 FCFA</span></td>
            <td style="padding:16px 20px;text-align:center;font-weight:800;color:var(--emerald);background:#F0FDFA"><span data-plan-price="silver" data-plan-comp="solo">30 000 FCFA</span></td>
            <td style="padding:16px 20px;text-align:center;font-weight:800"><span data-plan-price="gold" data-plan-comp="solo">65 000 FCFA</span></td>
            <td style="padding:16px 20px;text-align:center;font-weight:800"><span data-plan-price="platinium" data-plan-comp="solo">130 000 FCFA</span></td>
          </tr>
          <tr style="border-bottom:1px solid var(--line)">
            <td style="padding:16px 20px;font-weight:700;color:var(--ink)">Cotisation Famille (4+) / mois</td>
            <td style="padding:16px 20px;text-align:center;font-weight:800"><span data-plan-price="bronze" data-plan-comp="family">45 000 FCFA</span></td>
            <td style="padding:16px 20px;text-align:center;font-weight:800;color:var(--emerald);background:#F0FDFA"><span data-plan-price="silver" data-plan-comp="family">85 000 FCFA</span></td>
            <td style="padding:16px 20px;text-align:center;font-weight:800"><span data-plan-price="gold" data-plan-comp="family">180 000 FCFA</span></td>
            <td style="padding:16px 20px;text-align:center;font-weight:800"><span data-plan-price="platinium" data-plan-comp="family">350 000 FCFA</span></td>
          </tr>
          <tr style="border-bottom:1px solid var(--line)">
            <td style="padding:16px 20px;font-weight:600">Plafond Annuel par Assuré</td>
            <td style="padding:16px 20px;text-align:center">500 000 FCFA (760 €)</td>
            <td style="padding:16px 20px;text-align:center;font-weight:700;color:var(--emerald);background:#F0FDFA">1 500 000 FCFA (2 290 €)</td>
            <td style="padding:16px 20px;text-align:center">3 500 000 FCFA (5 335 €)</td>
            <td style="padding:16px 20px;text-align:center;font-weight:800;color:#047857">8 000 000 FCFA (12 200 €)</td>
          </tr>
          <tr style="border-bottom:1px solid var(--line)">
            <td style="padding:16px 20px;font-weight:600">Délais de Carence</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:700">0j (Urgences vitales)</td>
            <td style="padding:16px 20px;text-align:center;background:#F0FDFA">3 mois soins / 6 mois maternité</td>
            <td style="padding:16px 20px;text-align:center">3 mois soins / 6 mois maternité</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:700">3 mois soins / 6 mois maternité &amp; évac.</td>
          </tr>
          <tr style="border-bottom:1px solid var(--line)">
            <td style="padding:16px 20px;font-weight:600">Hospitalisation Chirurgicale &amp; Médicale</td>
            <td style="padding:16px 20px;text-align:center">100% (Urgences)</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:700;background:#F0FDFA">100% Sans Avance</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:700">100% (Chambre Solo)</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:800">100% (Suite VIP)</td>
          </tr>
          <tr style="border-bottom:1px solid var(--line)">
            <td style="padding:16px 20px;font-weight:600">Consultations Généralistes &amp; Spécialistes</td>
            <td style="padding:16px 20px;text-align:center;color:var(--ink-3)">—</td>
            <td style="padding:16px 20px;text-align:center;background:#F0FDFA">80% Tiers-Payant</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:700">100% Intégral</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:800">100% Intégral</td>
          </tr>
          <tr style="border-bottom:1px solid var(--line)">
            <td style="padding:16px 20px;font-weight:600">Pharmacie &amp; Médicaments Certifiés</td>
            <td style="padding:16px 20px;text-align:center;color:var(--ink-3)">—</td>
            <td style="padding:16px 20px;text-align:center;background:#F0FDFA">80% Prise en Charge</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:700">100% Tiers-Payant</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:800">100% Tiers-Payant</td>
          </tr>
          <tr style="border-bottom:1px solid var(--line)">
            <td style="padding:16px 20px;font-weight:600">Maternité &amp; Forfait Accouchement</td>
            <td style="padding:16px 20px;text-align:center;color:var(--ink-3)">—</td>
            <td style="padding:16px 20px;text-align:center;background:#F0FDFA">Inclus 100%</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:700">Inclus 100% Confort</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:800">Inclus Suite Clinique</td>
          </tr>
          <tr style="border-bottom:1px solid var(--line)">
            <td style="padding:16px 20px;font-weight:600">Télétriage &amp; Téléconsultation Lisacare</td>
            <td style="padding:16px 20px;text-align:center;color:#047857">Inclus 24/7</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:700;background:#F0FDFA">Illimité 24/7</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:700">Illimité 24/7</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:800">Médecin Dédié VIP</td>
          </tr>
          <tr style="border-bottom:1px solid var(--line)">
            <td style="padding:16px 20px;font-weight:600">Soins Seniors à Domicile Ongwa</td>
            <td style="padding:16px 20px;text-align:center;color:var(--ink-3)">Option</td>
            <td style="padding:16px 20px;text-align:center;background:#F0FDFA">Tarif Réduit Adhérent</td>
            <td style="padding:16px 20px;text-align:center;color:#047857">1 Visite/mois Incluse</td>
            <td style="padding:16px 20px;text-align:center;color:#047857;font-weight:800">Suivi Complet Inclus</td>
          </tr>
          <tr>
            <td style="padding:20px"></td>
            <td style="padding:20px;text-align:center"><button onclick="openSubscribeModal('bronze')" class="btn btn-ghost btn-sm">Choisir Bronze</button></td>
            <td style="padding:20px;text-align:center;background:#F0FDFA"><button onclick="openSubscribeModal('silver')" class="btn btn-primary btn-sm">Souscrire Silver</button></td>
            <td style="padding:20px;text-align:center"><button onclick="openSubscribeModal('gold')" class="btn btn-ghost btn-sm">Choisir Gold</button></td>
            <td style="padding:20px;text-align:center"><button onclick="openSubscribeModal('platinium')" class="btn btn-primary btn-sm" style="background:#0F172A">Choisir Platinium</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</section>

<!-- ═══════════ SECTION 02 : SOUSCRIPTION & SIMULATION ═══════════ -->
<section class="sec" id="souscription" style="background:var(--bg)">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">02</span>
      <div>
        <p class="eyebrow">Adhésion Express</p>
        <h2>Simulez votre cotisation et recevez votre carte CSSA.</h2>
        <p class="sec-sub">Votre carte mutuelle digitale est activée en quelques clics dès validation de votre premier règlement sécurisé.</p>
      </div>
    </div>

    <div class="mp-cta" style="text-align:center;padding:32px 0">
      <a href="/#simulateur" class="btn btn-primary" style="font-size:16px;padding:15px 32px">
        <i data-lucide="calculator"></i>Lancer le Simulateur de Cotisation Personnalisé
      </a>
    </div>
  </div>
</section>

