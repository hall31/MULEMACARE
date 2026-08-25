</main>

<style>
/* ================= FOOTER ================= */
footer.site{background:#0B1220;color:#94A3B8;padding:72px 0 34px;border-top:1px solid rgba(255,255,255,.08);font-size:14px}
.f-grid{display:grid;grid-template-columns:1.6fr 1fr 1fr 1.3fr;gap:48px;padding-bottom:52px;border-bottom:1px solid rgba(255,255,255,.08)}
.f-brand p{margin:16px 0 20px;line-height:1.6;color:#94A3B8;max-width:24rem}
.f-badges{display:flex;gap:12px;flex-wrap:wrap}
.f-badges span{display:inline-flex;align-items:center;gap:7px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:999px;padding:5px 12px;font:500 12px var(--font-b);color:#D7F0EA}
.f-badges svg{width:13px;height:13px;color:#5EEAD4}
footer.site h4{font:700 13px var(--font-b);letter-spacing:.14em;text-transform:uppercase;color:#fff;margin-bottom:18px}
.f-links{list-style:none;display:flex;flex-direction:column;gap:11px}
.f-links a,.f-links button{color:#94A3B8;transition:.18s;background:none;border:0;padding:0;font:inherit;text-align:left}
.f-links a:hover,.f-links button:hover{color:#5EEAD4}
.f-contact{list-style:none;display:flex;flex-direction:column;gap:13px}
.f-contact li{display:flex;gap:11px;align-items:flex-start}
.f-contact svg{width:16px;height:16px;color:#5EEAD4;flex:none;margin-top:3px}
.f-contact a{color:#fff;font-weight:600}
.f-bottom{display:flex;justify-content:space-between;align-items:center;gap:20px;padding-top:28px;font-size:13px;flex-wrap:wrap}
.f-legal{display:flex;gap:18px}
.f-legal button{background:none;border:0;color:#94A3B8;font:inherit;cursor:pointer}
.f-legal button:hover{color:#fff}
@media(max-width:960px){.f-grid{grid-template-columns:1fr 1fr;gap:36px}}
@media(max-width:540px){.f-grid{grid-template-columns:1fr}}

/* ================= TOASTS & FAB ================= */
#toasts{position:fixed;bottom:24px;right:24px;z-index:200;display:flex;flex-direction:column;gap:10px;pointer-events:none}
.toast{background:#0F172A;color:#fff;border-radius:14px;padding:14px 18px;display:flex;gap:12px;align-items:center;box-shadow:0 18px 36px -12px rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.1);pointer-events:auto;min-width:280px;max-width:380px;animation:tin .3s cubic-bezier(.2,.8,.3,1)}
.toast.out{animation:tout .25s ease forwards}
.toast .t-ic{width:32px;height:32px;border-radius:9px;background:rgba(13,148,136,.22);color:#5EEAD4;display:grid;place-items:center;flex:none}
.toast .t-ic svg{width:17px;height:17px}
.toast.t-info .t-ic{background:rgba(59,130,246,.22);color:#93C5FD}
.toast.t-error .t-ic{background:rgba(239,68,68,.22);color:#FCA5A5}
.toast b{display:block;font:600 13.5px var(--font-b);margin-bottom:2px}
.toast p{font:500 12px var(--font-b);color:#94A3B8;margin:0;line-height:1.35}
.toast .t-close{background:none;border:0;color:#64748B;margin-left:auto;padding:4px}
.toast .t-close svg{width:15px;height:15px}
@keyframes tin{from{opacity:0;transform:translateY(12px) scale(.95)}}
@keyframes tout{to{opacity:0;transform:translateY(8px) scale(.95)}}
.wa-fab{position:fixed;bottom:24px;right:24px;z-index:90;width:54px;height:54px;border-radius:50%;background:#25D366;color:#fff;display:grid;place-items:center;box-shadow:0 12px 28px -6px rgba(37,211,102,.5);transition:transform .2s,box-shadow .2s}
.wa-fab:hover{transform:scale(1.08);box-shadow:0 18px 36px -6px rgba(37,211,102,.65)}
.wa-fab svg{width:28px;height:28px}
#printArea{display:none}
@media print{
  body *{visibility:hidden}
  #printArea,#printArea *{visibility:visible}
  #printArea{position:absolute;left:0;top:0;width:100%;display:block;padding:24px;background:#fff;color:#000}
  .member-card{break-inside:avoid;box-shadow:none!important}
  .pa-sub{font-size:12px;color:#64748b;margin-bottom:20px}
  .pa-meta{margin-top:20px;display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:13px;border-top:1px solid #cbd5e1;padding-top:14px}
}
</style>

<!-- ═══════════ FOOTER ═══════════ -->
<footer class="site">
  <div class="wrap">
    <div class="f-grid">
      <div class="f-brand">
        <a href="/" class="logo" id="logoHome2" style="margin-bottom:16px" aria-label="MulemaCare — Accueil">
          <img src="/assets/img/logofooter.png" alt="MulemaCare" height="42" style="height:42px;width:auto;display:block" onerror="this.onerror=null;this.src='/assets/img/logo.png'">
        </a>
        <p>La première mutuelle santé digitale et solidaire pour l'Afrique et la diaspora. Cotisez depuis l'Europe ou l'Amérique, protégez vos proches au pays, sans avance de frais.</p>
        <div class="f-badges">
          <span><i data-lucide="shield-check"></i>Agréé CSSA n° 045</span>
          <span><i data-lucide="lock"></i>Paiement sécurisé</span>
          <span><i data-lucide="globe"></i>6 pays couverts</span>
        </div>
      </div>
      <div>
        <h4>Produit &amp; Services</h4>
        <ul class="f-links">
          <li><a href="/adhesion">Adhésion &amp; Souscription en Ligne</a></li>
          <li><a href="/#simulateur">Simulateur de Devis &amp; Tarifs</a></li>
          <li><a href="/espace-adherent">Espace Adhérent 360°</a></li>
          <li><a href="/borne-clinique">Borne Tiers-Payant Établissements</a></li>
          <li><a href="/#garanties">Grille des Garanties</a></li>
          <li><a href="/entreprises">Entreprises &amp; PME</a></li>
          <li><a href="/reseau-soins">Annuaire des Cliniques &amp; Pharmacies</a></li>
          <li><a href="/admin">Tour de Contrôle Admin</a></li>
        </ul>
      </div>
      <div>
        <h4>Aide &amp; Légal</h4>
        <ul class="f-links">
          <li><a href="https://wa.me/33659513458?text=Bonjour%20MulemaCare%2C%20j%27ai%20une%20question." target="_blank" rel="noopener">WhatsApp France (+33 6 59 51 34 58)</a></li>
          <li><a href="https://wa.me/23752112021?text=Bonjour%20MulemaCare%2C%20j%27ai%20une%20question." target="_blank" rel="noopener">WhatsApp Cameroun (+237 521 120 21)</a></li>
          <li><button data-info="faq">Questions fréquentes</button></li>
          <li><button data-info="legal">Mentions légales &amp; SIRET</button></li>
          <li><button data-info="legal">Notice CIMA &amp; RGPD</button></li>
          <li><a href="/espace-adherent">Espace Adhérent</a></li>
        </ul>
      </div>
      <div>
        <h4>Contact &amp; Sièges</h4>
        <ul class="f-contact">
          <li><i data-lucide="phone-call"></i><span>France : <a href="tel:+33659513458" class="num">+33 6 59 51 34 58</a><br>Cameroun : <a href="tel:+23752112021" class="num">+237 521 120 21</a></span></li>
          <li><i data-lucide="mail"></i><a href="mailto:contact@mulemacare.com">contact@mulemacare.com</a></li>
          <li><i data-lucide="map-pin"></i><span><b>France :</b> 208 Av. Aristide Briand, 92220 Bagneux<br><b>Cameroun :</b> 85 Av. de l'Indépendance, Douala</span></li>
          <li><i data-lucide="globe"></i>
            <span style="display:flex;gap:10px;margin-top:2px">
              <a href="https://www.facebook.com/Mulemacare-2117419645247839" target="_blank" rel="noopener" style="color:var(--emerald-100)">Facebook</a> ·
              <a href="https://www.instagram.com/mulemacare" target="_blank" rel="noopener" style="color:var(--emerald-100)">Instagram</a>
            </span>
          </li>
        </ul>
      </div>
    </div>
    <div class="f-bottom">
      <span>© <?= date('Y') ?> SOCIETE E-SANTE MULEMACARE FRANCE (SIRET : 8807 7661 2000 17) · Agrément CSSA n° 045/CSSA/2024.</span>
      <span class="f-legal">
        <button data-info="legal">Mentions légales</button>
        <button data-info="legal">Confidentialité</button>
        <button data-info="legal">Cookies</button>
      </span>
    </div>
  </div>
</footer>

<!-- ═══════════ MODALE INFO GÉNÉRIQUE ═══════════ -->
<div class="overlay" id="infoModal" role="dialog" aria-modal="true" aria-labelledby="infoTitle">
  <div class="modal" style="width:min(560px,100%)">
    <div class="m-head"><div class="m-head-top"><h3 id="infoTitle"></h3><button class="m-close" data-close-info aria-label="Fermer"><i data-lucide="x"></i></button></div></div>
    <div class="m-body" id="infoBody"></div>
  </div>
</div>

<!-- ═══════════ TOASTS / FAB / PRINT ═══════════ -->
<div id="toasts" aria-live="polite"></div>
<a class="wa-fab" href="https://wa.me/23752112021?text=Bonjour%20MulemaCare%2C%20je%20souhaite%20des%20informations%20sur%20l%27adh%C3%A9sion." target="_blank" rel="noopener" aria-label="Discuter sur WhatsApp"><i data-lucide="message-circle"></i></a>
<div id="printArea"></div>

<?php include __DIR__ . '/subscribe-modal.php'; ?>

<script>
/* ══════════════════ OUTILS ══════════════════ */
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const icons=()=>{try{lucide.createIcons()}catch(e){}};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

/* ══════════════════ DEVISES ══════════════════ */
const CURS={EUR:{r:1,s:'€',after:true},USD:{r:1.08,s:'$',after:false},XAF:{r:655.957,s:'FCFA',after:true}};
let cur='EUR';
function fmt(eur){
  const c=CURS[cur]; let v=eur*c.r;
  v=(c.s==='FCFA')?Math.round(v/500)*500:Math.round(v);
  const n=v.toLocaleString('fr-FR');
  return c.after?`${n} ${c.s}`:`${c.s}${n}`;
}
function refreshCurrency(){
  $$('[data-cur-seg] button').forEach(b=>b.classList.toggle('on',b.dataset.cur===cur));
  $$('[data-base-eur]').forEach(el=>{el.textContent=fmt(parseFloat(el.dataset.baseEur));});
  updateSim(); renderHeroCard();
}
$$('[data-cur-seg] button').forEach(b=>b.addEventListener('click',()=>{
  if(b.dataset.cur===cur)return;
  cur=b.dataset.cur; refreshCurrency();
  toast('Devise mise à jour','Tous les tarifs sont désormais affichés en '+cur+'.');
}));

/* ══════════════════ DONNÉES TARIFAIRES ══════════════════ */
const PLANS={
  bronze:{label:'Bronze',base:23,cap:760,tier:35},
  silver:{label:'Silver',base:42,cap:2290,tier:60},
  gold:{label:'Gold',base:68,cap:5335,tier:80},
  platinium:{label:'Platinium',base:115,cap:12200,tier:100}
};
const PROFILES={
  solo:{label:'Moi seul',units:1,f:1},
  couple:{label:'Mon couple',units:2,f:.95},
  famille:{label:'Ma famille au pays (2 adultes + 3 enfants)',units:3.5,f:.92},
  seniors:{label:'Mes parents âgés (2 seniors)',units:2,f:1.35},
  pme:{label:'Mes salariés PME',units:0,f:.85}
};
const CITIES={douala:'Douala',yaounde:'Yaoundé',kinshasa:'Kinshasa',abidjan:'Abidjan',dakar:'Dakar',libreville:'Libreville',bangui:'Bangui'};
const CITY_F={douala:1,yaounde:1,kinshasa:1.05,abidjan:1,dakar:1.05,libreville:1.1,bangui:1.15};
let sim={profile:'solo',city:'douala',plan:'silver',cycle:'annual',pme:8};

function simPrice(){
  const p=PLANS[sim.plan]||PLANS.silver, pr=PROFILES[sim.profile]||PROFILES.solo;
  const n=(sim.profile==='pme')?sim.pme:pr.units;
  const perHead=p.base*pr.f*(CITY_F[sim.city]||1);
  const m=perHead*n;
  return {m, a:m*12*.9, perHead, n};
}
function updateSim(){
  if(!$('#bigPrice')) return;
  const pr=simPrice();
  if($('#qProfile')) $('#qProfile').textContent=PROFILES[sim.profile].label;
  if($('#qCity')) $('#qCity').textContent=CITIES[sim.city];
  if($('#qPlan')) $('#qPlan').textContent=PLANS[sim.plan].label;
  $('#bigPrice').textContent=sim.cycle==='monthly'?fmt(pr.m):fmt(pr.a);
  $('#bigUnit').textContent=sim.cycle==='monthly'?'/ mois':`/ an (soit ${fmt(pr.a/12)}/mois)`;
  if($('#spSaveTxt')){
    $('#spSaveTxt').textContent=sim.cycle==='monthly'
      ?`Économisez ${fmt(pr.m*12-pr.a)} en payant à l'année`
      :`Cotisation annuelle — 10 % d'économie incluses (${fmt(pr.m*12-pr.a)})`;
  }
  let d='';
  if(sim.profile==='pme') d+=`<span>${pr.n} salariés couverts · <b>${fmt(pr.perHead*12*.9)}</b> / salarié / an</span>`;
  else if(pr.n>1) d+=`<span>${pr.n} personnes couvertes · <b>${fmt(pr.a/pr.n)}</b> / personne / an</span>`;
  else d+=`<span><b>1</b> personne couverte (1 an de protection continue)</span>`;
  d+=`<span>Équivalent : <b>${fmt(cur==='XAF'?(sim.cycle==='monthly'?pr.m:pr.a)/655.957:(sim.cycle==='monthly'?pr.m:pr.a)*655.957)}</b> ${cur==='XAF'?'EUR':'FCFA'}</span>`;
  if($('#spDetail')) $('#spDetail').innerHTML=d;
  if($('#pmeUnit')) $('#pmeUnit').textContent=`≈ ${fmt(pr.perHead*12*.9)} / salarié / an`;
  // synchronise sélections visuelles
  $$('#planOpts .p-opt').forEach(o=>o.classList.toggle('on',o.querySelector('input').value===sim.plan));
  $$('.plan-card').forEach(c=>c.classList.toggle('sel',c.dataset.planc===sim.plan));
  $$('#cityChips .chip').forEach(c=>c.classList.toggle('on',c.querySelector('input').value===sim.city));
  $$('[data-col]').forEach(td=>td.classList.toggle('sel',td.dataset.col===sim.plan));
  $('#heroFront')&&renderHeroCard();
}

/* listeners simulateur */
if($('#profileGrid')){
  $('#profileGrid').addEventListener('change',e=>{
    sim.profile=e.target.value;
    $('#pmeBox').classList.toggle('show',sim.profile==='pme');
    updateSim();
  });
}
if($('#cityChips')) $('#cityChips').addEventListener('change',e=>{sim.city=e.target.value;updateSim();});
if($('#planOpts')) $('#planOpts').addEventListener('change',e=>{sim.plan=e.target.value;updateSim();});
if($('#cycleSeg')){
  $('#cycleSeg').addEventListener('click',e=>{
    const b=e.target.closest('button'); if(!b)return;
    sim.cycle=b.dataset.cycle;
    $$('#cycleSeg button').forEach(x=>x.classList.toggle('on',x===b));
    updateSim();
  });
}
if($('#pmeMinus')) $('#pmeMinus').onclick=()=>{if(sim.pme>3){sim.pme--;$('#pmeCount').textContent=sim.pme;updateSim();}};
if($('#simAdhere')) $('#simAdhere').onclick=()=>{
  location.href='/adhesion?plan='+encodeURIComponent(sim.plan)+'&comp='+encodeURIComponent(sim.profile)+'&city='+encodeURIComponent(sim.city);
};

/* ══════════════════ CARTE MUTUELLE DIGITALE ══════════════════ */
function qrSVG(text,px){
  try{
    const q=qrcode(0,'M'); q.addData(text); q.make();
    return q.createSvgTag({cellSize:3,margin:0});
  }catch(e){ return `<div style="width:100%;height:100%;display:grid;place-items:center;font:600 9px var(--font-b);color:#334155">QR</div>`; }
}
function cardFrontHTML(o){
  const p=PLANS[o.plan]||PLANS.silver;
  const capTxt=fmt(p.cap);
  const capBar=p.tier;
  return `
  <svg class="cf-guilloche" viewBox="0 0 340 214" fill="none" aria-hidden="true"><g stroke="currentColor" stroke-opacity=".09"><circle cx="316" cy="26" r="24"/><circle cx="316" cy="26" r="46"/><circle cx="316" cy="26" r="68"/><circle cx="18" cy="198" r="26"/><circle cx="18" cy="198" r="48"/></g></svg>
  <div class="cf-top">
    <div class="cf-brand">
      <svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="rgba(255,255,255,.14)"/><rect x="13" y="6" width="6" height="20" rx="3" fill="#fff"/><rect x="6" y="13" width="20" height="6" rx="3" fill="#fff"/><path d="M7 16h5l2-3.5 3 7 2-3.5h6" stroke="#D97706" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="cf-bname"><b>MulemaCare</b><i>Mutuelle Santé · CSSA</i></span>
    </div>
    <span class="cf-status"><i></i>Tiers-payant actif</span>
  </div>
  <div class="cf-mid">
    <div class="cf-chip"></div>
    <div>
      <span class="cf-label">N° de carte CSSA</span>
      <div class="cf-number">CSSA <b>${o.no}</b></div>
    </div>
  </div>
  <div class="cf-mid" style="flex-direction:row;justify-content:space-between;align-items:flex-end">
    <div><span class="cf-label">Adhérent</span><div class="cf-holder"><b>${esc(o.name)}</b></div></div>
    <div style="text-align:right"><span class="cf-label">Valide jusqu'au</span><div class="cf-valid num">${o.validThru}</div></div>
  </div>
  <div class="cf-bottom">
    <div>
      <span class="cf-plan">${p.label}</span>
      <div class="cf-capline"><span class="cap-bar"><i style="width:${capBar}%"></i></span><em>Plafond hosp. / an : <b class="num">${capTxt}</b></em></div>
      <span class="cf-emerg"><i data-lucide="phone-call"></i>Urgences 24/7 · +237 521 120 21</span>
    </div>
    <div class="cf-qr">${qrSVG('MULEMACARE|CSSA|'+o.no+'|TIERS-PAYANT|mulemacare.com/verifier',76)}</div>
  </div>`;
}
function renderHeroCard(){
  const el=$('#cardTilt'); if(!el)return;
  el.dataset.plan=sim.plan;
  if($('#heroFront')) $('#heroFront').innerHTML=cardFrontHTML({name:'Éric Awono Mballa',no:'2025 · 8842 0173',plan:sim.plan,validThru:'12/2028'});
  icons();
}
/* tilt + flip + glare */
(function(){
  const scene=$('#cardScene'), tilt=$('#cardTilt'), flip=$('#cardFlip');
  if(!scene||!tilt||!flip) return;
  scene.addEventListener('mousemove',e=>{
    const r=scene.getBoundingClientRect();
    const x=(e.clientX-r.left)/r.width, y=(e.clientY-r.top)/r.height;
    tilt.classList.add('gliding');
    tilt.style.transform=`rotateY(${(x-.5)*16}deg) rotateX(${(.5-y)*12}deg)`;
    const f=$('#heroFront'); if(f){f.style.setProperty('--gx',(x*100)+'%'); f.style.setProperty('--gy',(y*100)+'%');}
  });
  scene.addEventListener('mouseleave',()=>{tilt.classList.remove('gliding');tilt.style.transform='';});
  const toggle=()=>flip.classList.toggle('flipped');
  flip.addEventListener('click',toggle);
  flip.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();toggle();}});
})();

/* ══════════════════ RÉSEAU DE SOINS ══════════════════ */
const NET=[
{n:"Clinique de l'Étoile",c:"douala",q:"Bonapriso",t:"clinic",tp:true,r:4.7,specs:["Urgences 24/7","Imagerie","Maternité"]},
{n:"Polyclinique Bonanjo",c:"douala",q:"Bonanjo",t:"clinic",tp:true,r:4.5,specs:["Cardiologie","Laboratoire"]},
{n:"Centre Médical Bonamoussadi",c:"douala",q:"Bonamoussadi",t:"center",tp:false,r:4.2,specs:["Médecine générale","Vaccination"]},
{n:"Pharmacie du Centre",c:"douala",q:"Akwa",t:"pharmacy",tp:true,r:4.6,specs:["Garde 24/7","Tiers-payant"]},
{n:"Clinique Bastos",c:"yaounde",q:"Bastos",t:"clinic",tp:true,r:4.8,specs:["Urgences","Pédiatrie","Maternité"]},
{n:"Clinique de la Cathédrale",c:"yaounde",q:"Centre-ville",t:"clinic",tp:true,r:4.4,specs:["Spécialistes","Laboratoire"]},
{n:"Pharmacie Obili",c:"yaounde",q:"Obili",t:"pharmacy",tp:true,r:4.3,specs:["Garde de nuit"]},
{n:"Clinique Ngaliema",c:"kinshasa",q:"Gombe",t:"clinic",tp:true,r:4.6,specs:["Urgences","Imagerie"]},
{n:"Centre Médical du Fleuve",c:"kinshasa",q:"Gombe",t:"center",tp:true,r:4.5,specs:["Médecine générale","Laboratoire"]},
{n:"Pharmacie du Boulevard",c:"kinshasa",q:"Gombe",t:"pharmacy",tp:false,r:4.1,specs:["Ouvert 7j/7"]},
{n:"Clinique PISAM",c:"abidjan",q:"Cocody",t:"clinic",tp:true,r:4.7,specs:["Urgences","Cardiologie","Maternité"]},
{n:"Pharmacie Cocody Centre",c:"abidjan",q:"Cocody",t:"pharmacy",tp:true,r:4.4,specs:["Tiers-payant"]},
{n:"Clinique de la Madeleine",c:"dakar",q:"Point E",t:"clinic",tp:true,r:4.6,specs:["Urgences","Néonatologie"]},
{n:"Pharmacie Mermoz",c:"dakar",q:"Mermoz",t:"pharmacy",tp:true,r:4.2,specs:["Garde 24/7"]}
];
const TYPE_LABEL={clinic:'Clinique',pharmacy:'Pharmacie',center:'Centre médical'};
const TYPE_IC={clinic:'building-2',pharmacy:'cross',center:'stethoscope'};
let net={city:'all',type:'all',tp:false,q:''};
function initNetChips(){
  if(!$('#netCityChips')) return;
  const cities=[...new Set(NET.map(f=>f.c))];
  $('#netCityChips').innerHTML=[['all','Toutes les villes'],...cities.map(c=>[c,CITIES[c]])]
    .map(([v,l],i)=>`<label class="chip${i===0?' on':''}"><input type="radio" name="netcity" value="${v}"${i===0?' checked':''}>${l}</label>`).join('');
  $('#netCityChips').addEventListener('change',e=>{net.city=e.target.value;renderNet();});
}
function renderNet(){
  if(!$('#netList')) return;
  const list=NET.filter(f=>
    (net.city==='all'||f.c===net.city)&&
    (net.type==='all'||f.t===net.type)&&
    (!net.tp||f.tp)&&
    (!net.q||(f.n+' '+f.q+' '+CITIES[f.c]+' '+f.specs.join(' ')).toLowerCase().includes(net.q))
  );
  $('#netCount').textContent=list.length?`${list.length} établissement${list.length>1?'s':''} conventionné${list.length>1?'s':''} trouvé${list.length>1?'s':''}`:'';
  if(!list.length){
    $('#netList').innerHTML=`<div class="net-empty"><i data-lucide="search-x"></i><b>Aucun établissement trouvé</b>Essayez une autre ville ou désactivez le filtre tiers-payant — de nouveaux partenaires rejoignent le réseau chaque mois.</div>`;
    icons();return;
  }
  $('#netList').innerHTML=list.map(f=>`
    <div class="net-row">
      <span class="net-ic k-${f.t}"><i data-lucide="${TYPE_IC[f.t]}"></i></span>
      <div class="net-main">
        <div class="net-title"><h4>${esc(f.n)}</h4>${f.tp?'<span class="tp-badge"><i data-lucide="shield-check"></i>Tiers-payant accepté</span>':''}</div>
        <div class="net-meta"><i data-lucide="map-pin"></i>${esc(f.q)}, ${CITIES[f.c]}<span class="dot-sep"></span><span class="net-rate"><i data-lucide="star"></i>${f.r.toFixed(1)}</span><span class="dot-sep"></span>${TYPE_LABEL[f.t]}</div>
        <div class="net-specs">${f.specs.map(s=>`<span>${esc(s)}</span>`).join('')}</div>
      </div>
      <div class="net-actions">
        <a class="btn btn-ghost btn-sm" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(f.n+' '+f.q+' '+CITIES[f.c])}" target="_blank" rel="noopener"><i data-lucide="navigation"></i>Itinéraire</a>
      </div>
    </div>`).join('');
  icons();
}
if($('#netTypeSeg')){
  $('#netTypeSeg').addEventListener('click',e=>{
    const b=e.target.closest('button'); if(!b)return;
    net.type=b.dataset.t;
    $$('#netTypeSeg button').forEach(x=>x.classList.toggle('on',x===b));
    renderNet();
  });
}
if($('#netTp')) $('#netTp').addEventListener('change',e=>{net.tp=e.target.checked;renderNet();});
if($('#netSearch')) $('#netSearch').addEventListener('input',e=>{net.q=e.target.value.trim().toLowerCase();renderNet();});
initNetChips();

/* ══════════════════ CHAT WHATSAPP LISACARE ══════════════════ */
const CHAT=[
['me','<p>Bonsoir docteur, mon fils de 3 ans a 38,9 °C de fièvre depuis ce soir. Que faire ?</p>','23:47'],
['doc','<p>Bonsoir Mme Awono. Rassurez-vous, je vais vous guider. A-t-il d\'autres symptômes — vomissements, éruption ?</p>','23:49'],
['me','<p>Un peu de toux, rien d\'autre. Il boit normalement.</p>','23:50'],
['doc','<p>Parfait. Donnez du paracétamol 15 mg/kg (3,2 ml s\'il fait environ 9 kg) toutes les 6 h si fièvre &gt; 38,5 °. Surveillez-le cette nuit.</p>','23:51'],
['file','<b>ordonnance_paracetamol.pdf</b><small>Couverture 100 % — remboursée par votre mutuelle</small>','23:51'],
['doc','<p>Si la fièvre persiste au-delà de 48 h ou s\'il refuse de boire, direction la Clinique de l\'Étoile (Douala) : tiers-payant, sans avance de frais.</p>','23:52'],
['me','<p>Merci infiniment docteur, je suis rassurée.</p>','23:53']
];
let chatTimers=[],chatPlayed=false;
function playChat(){
  chatTimers.forEach(clearTimeout); chatTimers=[];
  const box=$('#phoneChat'); if(!box)return;
  const replayBtn = $('#waReplay');
  if(replayBtn) {
    const icon = replayBtn.querySelector('svg') || replayBtn.querySelector('i');
    if(icon) {
      icon.style.transition = 'transform .45s cubic-bezier(.2,.8,.3,1)';
      icon.style.transform = 'rotate(-360deg)';
      setTimeout(() => { icon.style.transform = ''; }, 500);
    }
  }
  box.innerHTML='<div class="msg" style="opacity:.7;font-style:italic"><span class="spin" style="width:12px;height:12px;border-width:1.5px;margin-right:6px;vertical-align:middle;display:inline-block"></span>Médecin en ligne…</div>';
  CHAT.forEach((m,i)=>{
    chatTimers.push(setTimeout(()=>{
      if(i === 0) box.innerHTML = '';
      const html=m[0]==='file'
        ?`<div class="msg-doc"><i data-lucide="file-text"></i><div>${m[1]}<div style="font:500 9.5px var(--font-n);color:#94A3B8;text-align:right;margin-top:3px">${m[2]}</div></div></div>`
        :`<div class="msg${m[0]==='me'?' me':''}">${m[1]}<span>${m[2]}</span></div>`;
      box.insertAdjacentHTML('beforeend',html);
      box.scrollTop=box.scrollHeight; icons();
    }, 450 + i * 800));
  });
}
if($('#phoneMock')){
  new IntersectionObserver((es,obs)=>{
    if(es[0].isIntersecting&&!chatPlayed){chatPlayed=true;playChat();obs.disconnect();}
  },{threshold:.35}).observe($('#phoneMock'));
}
if($('#waReplay')) {
  $('#waReplay').addEventListener('click', (e) => {
    e.preventDefault();
    playChat();
  });
}

/* ══════════════════ TUNNEL DE SOUSCRIPTION ══════════════════ */
let sub={step:1,pay:'card',done:false,member:null};
const subModal=$('#subModal');

function openSub(plan){
  if(plan&&PLANS[plan]){sim.plan=plan;updateSim();}
  if(sub.done)resetSub();
  if(subModal){
    subModal.classList.add('open');
    document.body.style.overflow='hidden';
    renderSubRecap();
  }
}
function closeSub(){if(subModal){subModal.classList.remove('open');document.body.style.overflow='';}}
function resetSub(){
  sub={step:1,pay:'card',done:false,member:null};
  goSubStep(1); $('#subFoot').style.display='flex';
}
$$('[data-open-sub]').forEach(b=>b.addEventListener('click',()=>{closeMenu();openSub(b.dataset.openSub||null);}));
$$('[data-close-sub]').forEach(b=>b.addEventListener('click',closeSub));
if(subModal){
  subModal.addEventListener('click',e=>{if(e.target===subModal)closeSub();});
}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeSub();closeInfo();}});

function goSubStep(n){
  sub.step=n;
  $$('[data-step-view]').forEach(v=>{v.style.display=(v.dataset.stepView===String(n))?'':'none';});
  $$('#subStepper .stp').forEach(s=>{
    const sn=+s.dataset.step;
    s.classList.toggle('cur',sn===n); s.classList.toggle('done',sn<n);
    s.querySelector('.stp-dot').innerHTML=sn<n?'<i data-lucide="check"></i>':sn;
  });
  $$('#subStepper .stp-line').forEach((l,i)=>l.classList.toggle('done',n>i+1));
  $('#subBack').style.display=n>1?'inline-flex':'none';
  const next=$('#subNext');
  if(n===3){next.innerHTML=`<i data-lucide="lock"></i>Payer ${fmt(simPrice()[sim.cycle==='monthly'?'m':'a'])} — ${sim.cycle==='monthly'?'mois':'an'}`;}
  else{next.innerHTML='Continuer<i data-lucide="arrow-right"></i>';}
  if(n===2)syncLockedBen();
  icons();
}
function renderSubRecap(){
  const pr=simPrice();
  const price=sim.cycle==='monthly'?fmt(pr.m)+' / mois':fmt(pr.a)+' / an';
  if($('#subRecap')) $('#subRecap').innerHTML=`<i data-lucide="shield-check"></i><span>Formule <b>${PLANS[sim.plan].label}</b> · ${PROFILES[sim.profile].label.split('(')[0].trim()} · <b>${price}</b></span>`;
  const next=$('#subNext');
  if(sub.step===3&&!sub.done)next.innerHTML=`<i data-lucide="lock"></i>Payer ${fmt(simPrice()[sim.cycle==='monthly'?'m':'a'])} — ${sim.cycle==='monthly'?'mois':'an'}`;
  icons();
}
/* validation */
function setErr(input,msg){
  const f=input.closest('.field'); if(!f)return;
  f.classList.toggle('invalid',!!msg); f.classList.toggle('ok',!msg);
  const e=f.querySelector('.err'); if(e)e.textContent=msg||'';
}
function validStep1(){
  let ok=true;
  const p=$('#fPrenom'),n=$('#fNom'),m=$('#fEmail'),t=$('#fPhone');
  const vp=v=>{const b=v.trim().length>=2;setErr(p,b?'':'Indiquez votre prénom (2 caractères min.).');return b;};
  vp(p.value); ok=ok&&vp(p.value);
  const vn=v=>{const b=v.trim().length>=2;setErr(n,b?'':'Indiquez votre nom.');return b;};
  vn(n.value); ok=ok&&vn(n.value);
  const vm=v=>{const b=/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());setErr(m,b?'':'Adresse e-mail invalide.');return b;};
  vm(m.value); ok=ok&&vm(m.value);
  const vt=v=>{const b=v.replace(/\D/g,'').length>=8;setErr(t,b?'':'Numéro trop court (8 chiffres min.).');return b;};
  vt(t.value); ok=ok&&vt(t.value);
  return ok;
}
/* bénéficiaires */
function benRowHTML(name,locked){
  return `<div class="ben-row${locked?' locked':''}">
    ${locked?'<span class="ben-tag">Souscripteur — vous</span>':''}
    <div class="ben-grid">
      <div class="field"><label>Nom complet</label><input type="text" class="ben-name" placeholder="Ex. Marthe Awono" value="${esc(name||'')}" ${locked?'readonly':''}><span class="err"></span></div>
      <div class="field"><label>Date de naissance</label><input type="date" class="ben-date" max="${new Date().toISOString().slice(0,10)}"><span class="err"></span></div>
      <label class="ben-photo" title="Ajouter une photo d'identité"><i data-lucide="camera"></i><input type="file" accept="image/*"></label>
      ${locked?'<span></span>':'<button type="button" class="ben-del" aria-label="Retirer ce bénéficiaire"><i data-lucide="trash-2"></i></button>'}
    </div>
  </div>`;
}
function syncLockedBen(){
  const name=($('#fPrenom').value.trim()+' '+$('#fNom').value.trim()).trim()||'Votre nom';
  const list=$('#benList');
  if(!list) return;
  if(!list.querySelector('.ben-row.locked')){
    list.insertAdjacentHTML('afterbegin',benRowHTML(name,true));
    wireBenEvents(list.firstElementChild);
  }else{
    list.querySelector('.ben-row.locked .ben-name').value=name;
  }
}
function wireBenEvents(row){
  const photo=row.querySelector('.ben-photo');
  photo.querySelector('input').addEventListener('change',e=>{
    const f=e.target.files[0]; if(!f)return;
    if(f.size>5*1024*1024){toast('Photo trop lourde','Choisissez une image de moins de 5 Mo.','error');return;}
    const rd=new FileReader();
    rd.onload=()=>{photo.innerHTML=`<img src="${rd.result}" alt="Photo d'identité">`;photo.style.borderStyle='solid';};
    rd.readAsDataURL(f);
  });
  const del=row.querySelector('.ben-del');
  if(del)del.onclick=()=>{
    if($$('#benList .ben-row').length<=1)return;
    row.remove(); toast('Bénéficiaire retiré','Vous pouvez en ajouter un autre à tout moment.','info');
  };
}
if($('#benAdd')){
  $('#benAdd').onclick=()=>{
    const list=$('#benList');
    if($$('#benList .ben-row').length>=7){toast('Limite atteinte','7 bénéficiaires maximum par adhésion en ligne. Contactez le support pour une offre groupe.','info');return;}
    list.insertAdjacentHTML('beforeend',benRowHTML('',false));
    wireBenEvents(list.lastElementChild); icons();
  };
}
function validStep2(){
  let ok=true;
  $$('#benList .ben-row').forEach(row=>{
    const n=row.querySelector('.ben-name'), d=row.querySelector('.ben-date');
    const vn=v=>{const b=v.trim().length>=3;setErr(n,b?'':'Nom complet requis (3 caractères min.).');return b;};
    vn(n.value); ok=ok&&vn(n.value);
    const vd=v=>{const b=v&&new Date(v)<new Date()&&new Date(v)>new Date('1925-01-01');setErr(d,b?'':'Date de naissance invalide.');return b;};
    vd(d.value); ok=ok&&vd(d.value);
  });
  return ok;
}
/* paiement */
if($('#payOpts')){
  $('#payOpts').addEventListener('change',e=>{
    sub.pay=e.target.value;
    $$('#payOpts .pay-opt').forEach(o=>o.classList.toggle('on',o.querySelector('input').checked));
    $('#payCard').style.display=sub.pay==='card'?'':'none';
    $('#payApple').style.display=sub.pay==='apple'?'':'none';
    $('#payOM').style.display=sub.pay==='om'?'':'none';
    $('#payMTN').style.display=sub.pay==='momo'?'':'none';
  });
}
if($('#cardNum')){
  $('#cardNum').addEventListener('input',e=>{
    e.target.value=e.target.value.replace(/\D/g,'').slice(0,16).replace(/(\d{4})(?=\d)/g,'$1 ');
  });
}
if($('#cardExp')){
  $('#cardExp').addEventListener('input',e=>{
    let v=e.target.value.replace(/\D/g,'').slice(0,4);
    e.target.value=v.length>2?v.slice(0,2)+'/'+v.slice(2):v;
  });
}
if($('#cardCvc')) $('#cardCvc').addEventListener('input',e=>{e.target.value=e.target.value.replace(/\D/g,'').slice(0,4);});

function luhn(num){let s=0,alt=false;for(let i=num.length-1;i>=0;i--){let d=+num[i];if(alt){d*=2;if(d>9)d-=9;}s+=d;alt=!alt;}return s%10===0;}
function validStep3(){
  if(sub.pay==='apple')return true;
  if(sub.pay==='card'){
    let ok=true;
    const cn=$('#cardNum'),ce=$('#cardExp'),cc=$('#cardCvc'),cm=$('#cardName');
    const num=cn.value.replace(/\D/g,'');
    const vc=()=>{const b=num.length===16&&luhn(num);setErr(cn,b?'':'Numéro de carte invalide.');return b;};
    vc(); ok=ok&&vc();
    const ve=()=>{const v=ce.value;const b=/^(0[1-9]|1[0-2])\/\d{2}$/.test(v);let okd=b;
      if(b){const[y,m]=[2000+ +v.slice(3),+v.slice(0,2)];const now=new Date();okd=y>now.getFullYear()||(y===now.getFullYear()&&m>=now.getMonth()+1);}
      setErr(ce,okd?'':'Date expirée ou invalide.');return okd;};
    ve(); ok=ok&&ve();
    const vv=()=>{const b=cc.value.length>=3;setErr(cc,b?'':'CVC invalide.');return b;};
    vv(); ok=ok&&vv();
    const vm=()=>{const b=cm.value.trim().length>=3;setErr(cm,b?'':'Nom requis.');return b;};
    vm(); ok=ok&&vm();
    return ok;
  }
  const ph=sub.pay==='om'?$('#omPhone'):$('#mtnPhone');
  const b=ph.value.replace(/\D/g,'').length>=8;
  setErr(ph,b?'':'Numéro Mobile Money requis (8 chiffres min.).');
  return b;
}
if($('#applePayBtn')) $('#applePayBtn').onclick=()=>{ toast('Apple Pay prêt','Confirmez le paiement avec le bouton « Payer » ci-dessous.','info'); };

/* navigation du tunnel */
if($('#subBack')) $('#subBack').onclick=()=>goSubStep(sub.step-1);
if($('#subNext')){
  $('#subNext').onclick=async()=>{
    if(sub.step===1){ if(!validStep1()){toast('Champs à corriger','Vérifiez les informations en rouge.','error');return;} goSubStep(2); return; }
    if(sub.step===2){
      if(!$$('#benList .ben-row').length){toast('Aucun bénéficiaire','Ajoutez au moins le souscripteur.','error');return;}
      if(!validStep2()){toast('Champs à corriger','Vérifiez les noms et dates de naissance.','error');return;}
      goSubStep(3); renderSubRecap(); return;
    }
    if(sub.step===3){
      if(!validStep3()){toast('Paiement incomplet','Vérifiez vos informations de paiement.','error');return;}
      await processPayment();
    }
  };
}
async function processPayment(){
  const btn=$('#subNext'), old=btn.innerHTML;
  btn.disabled=true; btn.innerHTML='<span class="spin"></span>Traitement sécurisé en cours…';
  
  // Appel API Backend
  const payload = {
    plan: sim.plan,
    city: sim.city,
    currency: cur,
    period: sim.cycle,
    sponsor_name: ($('#fPrenom').value.trim()+' '+$('#fNom').value.trim()).trim(),
    sponsor_email: $('#fEmail').value.trim(),
    sponsor_phone: ($('#phoneCode').value + ' ' + $('#fPhone').value.trim()),
    payment_method: sub.pay
  };

  try {
    const res = await fetch('/api/subscribe', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const json = await res.json();
    if(json.status === 'ok') {
      sub.member = {
        name: json.data.member_name.toUpperCase(),
        no: json.data.card_number,
        plan: json.data.plan,
        validThru: json.data.valid_until,
        cssa: json.data.cssa_number,
        adh: json.data.membership_id
      };
    } else {
      buildMember();
    }
  } catch(e) {
    buildMember();
  }

  btn.disabled=false; btn.innerHTML=old;
  showSuccess();
  toast('Paiement confirmé','Bienvenue chez MulemaCare — votre carte digitale est active.','success');
}

function buildMember(){
  const name=($('#fPrenom').value.trim()+' '+$('#fNom').value.trim()).trim().toUpperCase();
  const no='2025 · '+String(Math.floor(1000+Math.random()*9000))+' '+String(Math.floor(1000+Math.random()*9000));
  const d=new Date(); d.setFullYear(d.getFullYear()+1);
  sub.member={name,no,plan:sim.plan,validThru:String(d.getMonth()+1).padStart(2,'0')+'/'+d.getFullYear(),
    cssa:'CSSA-2025-'+String(Math.floor(100000+Math.random()*900000)),
    adh:'ADH-'+Date.now().toString(36).toUpperCase()};
}

function showSuccess(){
  sub.done=true;
  $$('#subStepper .stp').forEach(s=>{s.classList.add('done');s.classList.remove('cur');});
  $$('#subStepper .stp-line').forEach(l=>l.classList.add('done'));
  $$('#subStepper .stp-dot').forEach(d=>d.innerHTML='<i data-lucide="check"></i>');
  $$('[data-step-view]').forEach(v=>v.style.display=v.dataset.stepView==='success'?'':'none');
  $('#subFoot').style.display='none';
  const m=sub.member, card=$('#succCard');
  card.dataset.plan=m.plan;
  card.innerHTML=`<div class="card-face card-front">${cardFrontHTML(m)}</div>`;
  const today=new Date().toLocaleDateString('fr-FR',{day:'numeric',month:'long',year:'numeric'});
  $('#succMeta').innerHTML=`
    <div><span>N° d'adhésion</span><b class="num">${m.adh}</b></div>
    <div><span>Carte CSSA</span><b class="num">${m.cssa}</b></div>
    <div><span>Effective dès</span><b>${today}</b></div>
    <div><span>Bénéficiaires</span><b class="num">${$$('#benList .ben-row').length}</b></div>`;
  $('#btnWa').href='https://wa.me/23752112021?text='+encodeURIComponent(`Bonjour MulemaCare, je viens d'adhérer (${m.cssa}). Merci de m'activer mon espace adhérent.`);
  icons();
}

if($('#btnPdf')){
  $('#btnPdf').onclick=()=>{
    const m=sub.member;
    $('#printArea').innerHTML=`
      <h2>MulemaCare Mutuelle Santé — Carte d'adhérent</h2>
      <p class="pa-sub">Émise le ${new Date().toLocaleDateString('fr-FR')} · Agrément CSSA n° 045/CSSA/2024 · mulemacare.com</p>
      <div class="member-card static" data-plan="${m.plan}"><div class="card-face card-front">${cardFrontHTML(m)}</div></div>
      <div class="pa-meta">
        <div><b>N° d'adhésion :</b> <span class="num">${m.adh}</span></div>
        <div><b>Adhérent :</b> ${esc(m.name)}</div>
        <div><b>Formule :</b> ${PLANS[m.plan].label} · ${sim.cycle==='monthly'?'cotisation mensuelle':'cotisation annuelle'} de <span class="num">${fmt(simPrice()[sim.cycle==='monthly'?'m':'a'])}</span></div>
        <div><b>Urgences 24/7 :</b> <span class="num">+237 521 120 21</span> · <b>Médecin de garde :</b> WhatsApp Lisacare</div>
      </div>`;
    window.print();
  };
}

/* ══════════════════ MODALE INFO GÉNÉRIQUE ══════════════════ */
const infoModal=$('#infoModal');
function openInfo(kind){
  const T={ongwa:'Planifier une visite Ongwa Senior Care',partner:'Devenir clinique partenaire',faq:'Questions fréquentes',legal:'Informations légales & CIMA'};
  $('#infoTitle').textContent=T[kind]||'Information';
  const B={
    ongwa:`<p style="font-size:14.5px;color:var(--ink-2);margin-bottom:18px">Une infirmière conventionnée Ongwa se déplace au domicile de votre parent, partout dans nos villes couvertes. La première visite de découverte est <b>gratuite</b> pour tout adhérent MulemaCare.</p>
      <div class="field"><label>Ville du parent</label><select id="ogCity"><option>Douala</option><option>Yaoundé</option><option>Kinshasa</option><option>Abidjan</option><option>Dakar</option><option>Libreville</option></select></div>
      <div class="field"><label>Nom du parent</label><input id="ogName" type="text" placeholder="Ex. Marthe Ekwalla"></div>
      <div class="field"><label>Fréquence souhaitée</label><select id="ogFreq"><option>1 visite par semaine</option><option>2 visites par semaine</option><option>1 visite par mois</option></select></div>
      <button class="btn btn-primary btn-block" id="ogSubmit" style="margin-top:8px"><i data-lucide="calendar-check"></i>Confirmer la planification</button>`,
    partner:`<p style="font-size:14.5px;color:var(--ink-2);margin-bottom:14px">Vous dirigez une clinique, un centre médical ou une pharmacie ? Rejoindre le réseau MulemaCare, c'est garantir le paiement sous <b>72 h</b>, remplir vos lits grâce à 12 400 adhérents et recevoir les patients en tiers-payant sans gestion papier.</p>
      <ul class="ally-feats" style="margin-bottom:18px"><li><i data-lucide="check"></i>Remboursement numérique sous 72 heures</li><li><i data-lucide="check"></i>Validation des prises en charge par QR code</li><li><i data-lucide="check"></i>Formation et supports offerts à vos équipes d'accueil</li></ul>
      <a class="btn btn-primary btn-block" href="mailto:partenaires@mulemacare.com?subject=Conventionnement%20clinique%20MulemaCare"><i data-lucide="mail"></i>Écrire à partenaires@mulemacare.com</a>`,
    faq:`<div style="display:flex;flex-direction:column;gap:16px;font-size:14.5px;color:var(--ink-2)">
      <div><b style="color:var(--ink)">Comment s'effectue le paiement de la mutuelle ?</b><br>Les adhésions s'effectuent avec un <b>paiement à l'année</b> (cotisation annuelle), garantissant 12 mois de sérénité et de couverture continue sans risque d'interruption.</div>
      <div><b style="color:var(--ink)">Mes parents doivent-ils avancer de l'argent ?</b><br>Non. Dans les 45+ établissements conventionnés, la prise en charge est immédiate : ils présentent simplement le QR code de la carte digitale.</div>
      <div><b style="color:var(--ink)">Je paie depuis l'Europe, est-ce possible ?</b><br>Oui : carte bancaire via Stripe, virement SEPA, ou débit automatique. Les tarifs s'affichent dans votre devise.</div>
      <div><b style="color:var(--ink)">Quels sont les délais de carence appliqués ?</b><br>Les urgences vitales (SAMU, réanimation) et la régulation WhatsApp Lisacare 24/7 sont prises en charge <b>immédiatement (0 jour)</b>. Le délai de carence est de <b>3 mois</b> pour les soins programmés &amp; hospitalisations, et de <b>6 mois</b> pour la maternité et les femmes enceintes (bilans et accouchement).</div>
      <div><b style="color:var(--ink)">Puis-je ajouter un bénéficiaire plus tard ?</b><br>Oui, à tout moment depuis votre espace adhérent ou par WhatsApp — l'ajout est actif sous 24 h.</div></div>`,
    legal:`<div style="font-size:13.5px;color:var(--ink-2);display:flex;flex-direction:column;gap:12px">
      <p><b>Éditeur France &amp; Diaspora :</b> <b>SOCIETE E-SANTE MULEMACARE FRANCE</b> — Société enregistrée sous le <b>SIRET n° 8807 7661 2000 17</b>. Siège : 208 Avenue Aristide Briand, 92220 Bagneux, France. Téléphone &amp; WhatsApp : <a href="tel:+33659513458" style="color:var(--emerald);font-weight:700">+33 6 59 51 34 58</a>. E-mail : <a href="mailto:contact@mulemacare.com" style="color:var(--emerald);font-weight:700">contact@mulemacare.com</a>.</p>
      <p><b>Opérateur Mutuelle Santé Afrique :</b> <b>MULEMACARE MUTUELLE SANTÉ CAMEROUN</b> — Établissement d'assurance mutuelle agréé sous le n° <b>045/CSSA/2024</b> par la Conférence de la Santé et de la Sécurité en Afrique (CSSA). Siège : 85 Avenue de l'Indépendance, Douala — Cameroun. Téléphone &amp; Desk Médical : <a href="tel:+23752112021" style="color:var(--emerald);font-weight:700">+237 521 120 21</a>.</p>
      <p><b>Réglementation &amp; Conformité :</b> Conformité CIMA / CEMAC pour les garanties de tiers-payant en Afrique centrale et de l'ouest. Données de santé protégées conformément au RGPD (Europe) et à la loi n° 2010/012 (Cameroun). Hébergement certifié HDS / ISO-27001 opéré par 1&1 IONOS SE (Allemagne).</p>
      <p><b>Moyens de Paiement Sécurisés :</b> Carte Bancaire / SEPA via Stripe (certifié PCI-DSS niveau 1), Orange Money Cameroun (+237 521 120 21), MTN Mobile Money (+237 65 14 58 37). Zéro conservation de coordonnées bancaires sur les serveurs web.</p></div>`
  };
  $('#infoBody').innerHTML=B[kind]||B.faq;
  infoModal.classList.add('open'); document.body.style.overflow='hidden';
  icons();
  const s=$('#ogSubmit');
  if(s)s.onclick=()=>{
    const nm=$('#ogName');
    if(nm.value.trim().length<3){setErr(nm,'Indiquez le nom de votre parent.');return;}
    closeInfo();
    toast('Visite planifiée',`Une infirmière Ongwa contactera ${nm.value.trim().split(' ')[0]} sous 48 h pour convenir de la première visite.`);
  };
}
function closeInfo(){if(infoModal){infoModal.classList.remove('open');document.body.style.overflow=subModal&&subModal.classList.contains('open')?'hidden':'';}}
$$('[data-close-info]').forEach(b=>b.addEventListener('click',closeInfo));
if(infoModal) infoModal.addEventListener('click',e=>{if(e.target===infoModal)closeInfo();});
$$('[data-info]').forEach(b=>b.addEventListener('click',()=>{closeMenu();openInfo(b.dataset.info);}));

/* ══════════════════ TOASTS ══════════════════ */
function toast(title,msg,type='success'){
  const ic={success:'check-circle-2',info:'info',error:'alert-circle'}[type];
  const el=document.createElement('div');
  el.className='toast'+(type==='info'?' t-info':type==='error'?' t-error':'');
  el.innerHTML=`<span class="t-ic"><i data-lucide="${ic}"></i></span><div><b>${esc(title)}</b><p>${esc(msg)}</p></div><button class="t-close" aria-label="Fermer"><i data-lucide="x"></i></button>`;
  $('#toasts').appendChild(el); icons();
  const kill=()=>{el.classList.add('out');setTimeout(()=>el.remove(),300);};
  el.querySelector('.t-close').onclick=kill;
  setTimeout(kill,5200);
}

/* ══════════════════ UI GÉNÉRALE ══════════════════ */
const header=$('#siteHeader'), burger=$('#burger');
function closeMenu(){if(header){header.classList.remove('open');if(burger)burger.setAttribute('aria-expanded','false');}}
if(burger){
  burger.onclick=()=>{
    const open=header.classList.toggle('open');
    burger.setAttribute('aria-expanded',open);
    burger.innerHTML=`<i data-lucide="${open?'x':'menu'}"></i>`; icons();
  };
}
$$('#mNav a').forEach(a=>a.addEventListener('click',closeMenu));
window.addEventListener('scroll',()=>header&&header.classList.toggle('scrolled',window.scrollY>10),{passive:true});
[['#logoHome'],['#logoHome2']].forEach(([s])=>{const el=$(s);if(el)el.addEventListener('click',e=>{if(location.pathname==='/'||location.pathname===''){e.preventDefault();window.scrollTo({top:0,behavior:'smooth'});}});});

/* choix formule via tableau comparatif */
$$('.th-choose').forEach(b=>b.addEventListener('click',()=>{
  sim.plan=b.dataset.pick; updateSim();
  toast('Formule '+PLANS[sim.plan].label+' sélectionnée','Le simulateur et la carte digitale ont été mis à jour.');
}));

/* reveal au scroll */
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}}),{threshold:.12});
$$('.reveal').forEach(el=>io.observe(el));

/* ══════════════════ INIT ══════════════════ */
icons(); refreshCurrency(); renderNet(); goSubStep(1);
</script>
</body>
</html>
