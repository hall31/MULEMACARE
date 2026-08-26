<style>
/* ================= MODALE SOUSCRIPTION ================= */
.overlay{position:fixed;inset:0;background:rgba(15,23,42,.65);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);z-index:100;display:grid;place-items:center;padding:18px;opacity:0;pointer-events:none;transition:opacity .22s;overflow-y:auto}
.overlay.open{opacity:1;pointer-events:auto}
.modal{background:#fff;border-radius:24px;width:min(660px,100%);min-width:0;box-shadow:0 30px 60px -20px rgba(15,23,42,.45);border:1px solid var(--line);transform:translateY(18px) scale(.98);transition:transform .24s cubic-bezier(.2,.8,.3,1);display:flex;flex-direction:column;max-height:calc(100vh - 36px);max-height:calc(100dvh - 36px);overflow:hidden;margin:auto}
.overlay.open .modal{transform:none}
.m-head{padding:22px 26px 16px;border-bottom:1px solid var(--line);background:#FBFDFC;flex:none}
.m-head-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.m-head h3{font-size:20px;font-weight:700}
.m-close{background:none;border:0;color:var(--ink-3);width:36px;height:36px;border-radius:9px;display:grid;place-items:center;transition:.15s}
.m-close:hover{background:#F1F5F9;color:var(--ink)}
.m-close svg{width:19px;height:19px}
.stepper-bar{display:flex;align-items:center;gap:8px}
.stp{display:flex;align-items:center;gap:7px;font:600 12.5px var(--font-b);color:var(--ink-3)}
.stp-dot{width:22px;height:22px;border-radius:50%;background:#E2E8F0;color:var(--ink-3);display:grid;place-items:center;font:700 11px var(--font-n);transition:.2s}
.stp-dot svg{width:12px;height:12px}
.stp.cur{color:var(--emerald)}
.stp.cur .stp-dot{background:var(--emerald);color:#fff}
.stp.done .stp-dot{background:var(--emerald-100);color:var(--emerald)}
.stp-line{flex:1;height:2px;background:#E2E8F0;border-radius:2px;transition:.2s}
.stp-line.done{background:var(--emerald-500)}
.m-body{padding:26px;overflow-y:auto;flex:1}
.m-foot{padding:16px 26px;border-top:1px solid var(--line);background:#FBFDFC;display:flex;justify-content:space-between;align-items:center;gap:12px;flex:none}
.m-secure{font:500 11.5px var(--font-b);color:var(--ink-3);display:flex;align-items:center;gap:6px}
.m-secure svg{width:13px;height:13px;color:var(--emerald)}
.field{display:flex;flex-direction:column;gap:6px;margin-bottom:16px;min-width:0}
.field label{font:600 13px var(--font-b);color:var(--ink-2)}
.field input,.field select{border:1.5px solid var(--line);border-radius:11px;padding:12px 14px;font:500 14.5px var(--font-b);color:var(--ink);background:#fff;transition:.18s;outline:none;width:100%;min-width:0;max-width:100%}
.field input:focus,.field select:focus{border-color:var(--emerald);box-shadow:0 0 0 3px rgba(9,114,104,.1)}
.field .err{font:500 11.5px var(--font-b);color:#DC2626;display:none}
.field.invalid input{border-color:#DC2626;background:#FEF2F2}
.field.invalid .err{display:block}
.field.ok input{border-color:#10B981}
.f-grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.res-cards{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.res-card{border:1.5px solid var(--line);border-radius:var(--r-md);padding:12px 14px;cursor:pointer;display:flex;gap:11px;align-items:center;transition:.16s;background:#fff;position:relative}
.res-card input{position:absolute;opacity:0;pointer-events:none}
.res-card:hover{border-color:rgba(13,148,136,.55)}
.res-card.on{border-color:var(--emerald);background:var(--emerald-050)}
.res-card b{display:block;font:600 13.5px var(--font-b)}
.res-card small{display:block;font:500 11.5px var(--font-b);color:var(--ink-3)}
.phone-row{display:flex;gap:8px}
.phone-row select{width:110px;flex:none}
.recap-strip{display:flex;align-items:center;gap:10px;background:var(--emerald-050);border:1px solid var(--emerald-100);border-radius:11px;padding:11px 14px;margin-bottom:20px;font:500 13px var(--font-b);color:var(--emerald-900)}
.recap-strip svg{width:16px;height:16px;color:var(--emerald);flex:none}
.recap-strip b{color:var(--emerald-900)}
.ben-list{display:flex;flex-direction:column;gap:12px;margin-bottom:16px}
.ben-row{background:#F8FAFC;border:1.5px solid var(--line);border-radius:14px;padding:14px;position:relative}
.ben-row.locked{background:#F1F5F9;border-style:dashed}
.ben-tag{display:inline-block;font:700 10.5px var(--font-b);letter-spacing:.08em;text-transform:uppercase;color:var(--emerald);background:var(--emerald-100);padding:3px 8px;border-radius:6px;margin-bottom:9px}
.ben-grid{display:grid;grid-template-columns:1fr 150px 44px 36px;gap:10px;align-items:end}
.ben-grid .field{margin-bottom:0}
.ben-photo{width:44px;height:44px;border:1.5px dashed var(--line);border-radius:11px;display:grid;place-items:center;cursor:pointer;color:var(--ink-3);background:#fff;transition:.18s;overflow:hidden;position:relative}
.ben-photo:hover{border-color:var(--emerald);color:var(--emerald)}
.ben-photo input{position:absolute;opacity:0;pointer-events:none}
.ben-photo img{width:100%;height:100%;object-fit:cover}
.ben-photo svg{width:18px;height:18px}
.ben-del{width:36px;height:44px;border:0;background:none;color:#94A3B8;display:grid;place-items:center;border-radius:9px;transition:.15s}
.ben-del:hover{color:#DC2626;background:#FEE2E2}
.ben-del svg{width:17px;height:17px}
.ben-add{display:flex;align-items:center;justify-content:center;gap:8px;border:1.5px dashed var(--line);background:#fff;border-radius:12px;padding:12px;font:600 13.5px var(--font-b);color:var(--emerald);width:100%;transition:.18s}
.ben-add:hover{border-color:var(--emerald);background:var(--emerald-050)}
.ben-add svg{width:16px;height:16px}
.pay-opts{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(130px,100%),1fr));gap:10px;margin-bottom:18px}
.pay-opt{border:1.5px solid var(--line);border-radius:12px;padding:12px 10px;text-align:center;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:6px;background:#fff;transition:.16s;position:relative}
.pay-opt input{position:absolute;opacity:0;pointer-events:none}
.pay-opt:hover{border-color:rgba(13,148,136,.55)}
.pay-opt.on{border-color:var(--emerald);background:var(--emerald-050)}
.pay-opt b{font:600 12.5px var(--font-b);display:block}
.pay-opt small{font:500 11px var(--font-b);color:var(--ink-3);display:block}
.pay-panel{background:#F8FAFC;border:1.5px solid var(--line);border-radius:14px;padding:18px;margin-bottom:14px}
.mm-info{display:flex;gap:10px;align-items:flex-start;background:var(--gold-100);border:1px solid #FCD34D;border-radius:10px;padding:11px 13px;font:500 12.5px var(--font-b);color:#92400E;margin-bottom:12px}
.mm-info svg{width:16px;height:16px;flex:none;margin-top:2px}
.apple-pay{background:#000;color:#fff;border:0;border-radius:11px;padding:14px;width:100%;font:600 16px -apple-system,sans-serif;display:flex;align-items:center;justify-content:center;gap:6px;box-shadow:0 6px 18px -4px rgba(0,0,0,.4)}
.apple-pay svg{width:18px;height:18px}
.succ-wrap{text-align:center;padding:10px 0}
.succ-check{width:68px;height:68px;margin:0 auto 16px}
.succ-check .sc{stroke-dasharray:220;stroke-dashoffset:220;animation:draw 1.1s cubic-bezier(.2,.8,.3,1) forwards}
.succ-check .sp{stroke-dasharray:70;stroke-dashoffset:70;animation:draw .6s cubic-bezier(.2,.8,.3,1) .5s forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.succ-wrap h3{font-size:24px;margin-bottom:8px}
.succ-wrap>p{font-size:14.5px;color:var(--ink-2);max-width:28rem;margin:0 auto 24px}
.succ-card-zone{max-width:380px;margin:0 auto 20px}
.succ-meta{display:grid;grid-template-columns:1fr 1fr;gap:10px;background:#F8FAFC;border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:20px;text-align:left;font-size:13px}
.succ-meta span{color:var(--ink-3);display:block}
.succ-meta b{color:var(--ink);font-weight:600}
.succ-actions{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.spin{width:16px;height:16px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:sp 0.8s linear infinite;display:inline-block}
@keyframes sp{to{transform:rotate(360deg)}}
@media(max-width:600px){.ben-grid{grid-template-columns:1fr 1fr;gap:8px}.ben-grid .ben-photo,.ben-grid .ben-del{grid-column:span 1}.f-grid2,.res-cards{grid-template-columns:1fr}}

/* ================= MODALE : ADAPTATION MOBILE ================= */
@media(max-width:600px){
  .overlay{padding:10px;place-items:start center;padding-top:max(10px,env(safe-area-inset-top))}
  .modal{width:100%;border-radius:20px;max-height:calc(100dvh - 20px)}
  .m-head{padding:16px 16px 13px}
  .m-head h3{font-size:17px;line-height:1.25}
  .m-body{padding:18px 16px}
  .m-foot{padding:12px 16px;flex-wrap:wrap;row-gap:10px;padding-bottom:max(12px,env(safe-area-inset-bottom))}
  .m-foot .btn{flex:1 1 44%;min-height:46px}
  .m-secure{order:3;flex-basis:100%;justify-content:center;font-size:11px;text-align:center}
  /* Sur iOS, une police < 16px déclenche un zoom automatique à la saisie */
  .field input,.field select{font-size:16px;padding:13px 14px}
  .stepper-bar{gap:6px}
  .stp-label{display:none}
  .stp.cur .stp-label{display:inline}
  .res-cards>*,.pay-opts>*,.f-grid2>*,.ben-grid>*{min-width:0}
  .res-card{padding:12px;gap:10px}
  .res-card small{overflow-wrap:anywhere}
  .pay-opts{grid-template-columns:1fr 1fr;gap:8px}
  .pay-opt{padding:11px 8px}
  .pay-opt small{font-size:10.5px;overflow-wrap:anywhere}
  .pay-panel{padding:14px}
  .phone-row select{width:112px;padding-inline:10px}
  .succ-meta{grid-template-columns:1fr}
  .succ-actions{flex-direction:column}
  .succ-actions .btn{width:100%}
  .succ-wrap h3{font-size:21px}
  .mm-info b{overflow-wrap:anywhere}
}
</style>

<!-- ═══════════ MODALE SOUSCRIPTION ═══════════ -->
<div class="overlay" id="subModal" role="dialog" aria-modal="true" aria-labelledby="subTitle">
  <div class="modal">
    <div class="m-head">
      <div class="m-head-top">
        <h3 id="subTitle">Adhésion en ligne — 2 minutes</h3>
        <button class="m-close" data-close-sub aria-label="Fermer"><i data-lucide="x"></i></button>
      </div>
      <div class="stepper-bar" id="subStepper">
        <div class="stp cur" data-step="1"><span class="stp-dot">1</span><span class="stp-label">Identité</span></div>
        <div class="stp-line"></div>
        <div class="stp" data-step="2"><span class="stp-dot">2</span><span class="stp-label">Bénéficiaires</span></div>
        <div class="stp-line"></div>
        <div class="stp" data-step="3"><span class="stp-dot">3</span><span class="stp-label">Paiement</span></div>
      </div>
    </div>
    <div class="m-body" id="subBody">
      <!-- Étape 1 -->
      <div data-step-view="1">
        <div class="field">
          <label>Vous souscrivez en tant que…</label>
          <div class="res-cards">
            <label class="res-card on"><input type="radio" name="res" value="diaspora" checked><span class="o-ic"><i data-lucide="globe"></i></span><span><b>Diaspora</b><small>Europe / USA / Canada</small></span></label>
            <label class="res-card"><input type="radio" name="res" value="local"><span class="o-ic"><i data-lucide="map-pin"></i></span><span><b>Résident local</b><small>Je vis en Afrique</small></span></label>
          </div>
        </div>
        <div class="f-grid2">
          <div class="field"><label for="fPrenom">Prénom</label><input id="fPrenom" type="text" placeholder="Ex. Éric" autocomplete="given-name"><span class="err"></span></div>
          <div class="field"><label for="fNom">Nom</label><input id="fNom" type="text" placeholder="Ex. Awono Mballa" autocomplete="family-name"><span class="err"></span></div>
        </div>
        <div class="field"><label for="fEmail">Adresse e-mail</label><input id="fEmail" type="email" placeholder="vous@exemple.com" autocomplete="email"><span class="err"></span></div>
        <div class="field"><label for="fPhone">Téléphone (WhatsApp de préférence)</label>
          <div class="phone-row">
            <select id="phoneCode" aria-label="Indicatif téléphonique">
              <option value="+33">+33 FR</option><option value="+32">+32 BE</option><option value="+1">+1 CA/US</option>
              <option value="+237" selected>+237 CM</option><option value="+236">+236 CF</option><option value="+225">+225 CI</option>
              <option value="+221">+221 SN</option><option value="+243">+243 CD</option><option value="+241">+241 GA</option>
            </select>
            <input id="fPhone" type="tel" placeholder="6XX XX XX XX" autocomplete="tel" style="flex:1">
          </div><span class="err"></span>
        </div>
      </div>
      <!-- Étape 2 -->
      <div data-step-view="2" style="display:none">
        <div class="recap-strip"><i data-lucide="info"></i><span>Le souscripteur est automatiquement le premier bénéficiaire. Ajoutez ensuite votre conjoint, vos enfants ou vos parents.</span></div>
        <div class="ben-list" id="benList"></div>
        <button type="button" class="ben-add" id="benAdd"><i data-lucide="plus"></i>Ajouter un bénéficiaire</button>
      </div>
      <!-- Étape 3 -->
      <div data-step-view="3" style="display:none">
        <div class="recap-strip" id="subRecap"></div>
        <div class="pay-opts" id="payOpts">
          <label class="pay-opt on"><input type="radio" name="pay" value="card" checked><span class="o-ic"><i data-lucide="credit-card"></i></span><span><b>Carte bancaire</b><small>Stripe · Visa, Mastercard</small></span></label>
          <label class="pay-opt"><input type="radio" name="pay" value="apple"><span class="o-ic"><i data-lucide="apple"></i></span><span><b>Apple Pay</b><small>Paiement en un geste</small></span></label>
          <label class="pay-opt"><input type="radio" name="pay" value="om"><span class="o-ic" style="background:#FFE8D2;color:#C2410C"><i data-lucide="smartphone"></i></span><span><b>Orange Money</b><small class="num">Marchand +237 521 120 21</small></span></label>
          <label class="pay-opt"><input type="radio" name="pay" value="momo"><span class="o-ic" style="background:#FFE8D2;color:#C2410C"><i data-lucide="smartphone"></i></span><span><b>MTN MoMo</b><small class="num">Marchand +237 65 14 58 37</small></span></label>
        </div>
        <div class="pay-panel" id="payCard">
          <div class="field"><label for="cardName">Nom sur la carte</label><input id="cardName" type="text" placeholder="ÉRIC AWONO MBALLA" autocomplete="cc-name"><span class="err"></span></div>
          <div class="field"><label for="cardNum">Numéro de carte</label><input id="cardNum" type="text" inputmode="numeric" placeholder="4242 4242 4242 4242" autocomplete="cc-number"><span class="err"></span></div>
          <div class="f-grid2">
            <div class="field"><label for="cardExp">Expiration (MM/AA)</label><input id="cardExp" type="text" inputmode="numeric" placeholder="12/28" autocomplete="cc-exp"><span class="err"></span></div>
            <div class="field"><label for="cardCvc">CVC</label><input id="cardCvc" type="text" inputmode="numeric" placeholder="123" autocomplete="cc-csc"><span class="err"></span></div>
          </div>
        </div>
        <div class="pay-panel" id="payApple" style="display:none">
          <button type="button" class="apple-pay" id="applePayBtn"><i data-lucide="apple"></i>Pay</button>
          <p style="font:500 12.5px var(--font-b);color:var(--ink-3);margin-top:12px;text-align:center">Vous confirmez le paiement avec Face ID / Touch ID à l'étape suivante.</p>
        </div>
        <div class="pay-panel" id="payOM" style="display:none">
          <div class="mm-info"><i data-lucide="info"></i><span>Une demande de débit sera envoyée sur votre application Orange Money (Code USSD : <b>#150*1*1*52112021*MONTANT#</b>). Validez avec votre code secret. Marchand : <b>MULEMACARE HEALTH</b>.</span></div>
          <div class="field"><label for="omPhone">Votre numéro Orange Money</label><input id="omPhone" type="tel" placeholder="6XX XX XX XX"><span class="err"></span></div>
        </div>
        <div class="pay-panel" id="payMTN" style="display:none">
          <div class="mm-info"><i data-lucide="info"></i><span>Composez <b>*126*1*65145837*MONTANT#</b> ou validez l'invite MoMo sur votre smartphone. Marchand : <b>MULEMACARE HEALTH</b>.</span></div>
          <div class="field"><label for="mtnPhone">Votre numéro MTN MoMo</label><input id="mtnPhone" type="tel" placeholder="6XX XX XX XX"><span class="err"></span></div>
        </div>
      </div>
      <!-- Succès -->
      <div data-step-view="success" style="display:none">
        <div class="succ-wrap">
          <svg class="succ-check" viewBox="0 0 74 74" fill="none"><circle cx="37" cy="37" r="34" stroke="#D9F1EC" stroke-width="4"/><circle class="sc" cx="37" cy="37" r="34" stroke="#097268" stroke-width="4" stroke-linecap="round" transform="rotate(-90 37 37)"/><path class="sp" d="M23 38.5 L33 48 L52 28" stroke="#0D9488" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <h3>Adhésion confirmée</h3>
          <p>Votre carte mutuelle digitale est active dès maintenant. Présentez le QR code à l'accueil de n'importe quel établissement conventionné.</p>
          <div class="succ-card-zone"><div class="member-card static" id="succCard" data-plan="silver"></div></div>
          <div class="succ-meta" id="succMeta"></div>
          <div class="succ-actions">
            <button class="btn btn-primary" id="btnPdf"><i data-lucide="download"></i>Télécharger la carte (PDF)</button>
            <a class="btn btn-ghost" id="btnWa" href="#" target="_blank" rel="noopener"><i data-lucide="message-circle"></i>Recevoir sur WhatsApp</a>
          </div>
        </div>
      </div>
    </div>
    <div class="m-foot" id="subFoot">
      <button class="btn btn-ghost" id="subBack" style="display:none"><i data-lucide="arrow-left"></i>Retour</button>
      <span class="m-secure"><i data-lucide="lock"></i>Connexion chiffrée · Données hébergées en Europe</span>
      <button class="btn btn-primary" id="subNext">Continuer<i data-lucide="arrow-right"></i></button>
    </div>
  </div>
</div>
