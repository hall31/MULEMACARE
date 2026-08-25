<style>
/* ================= HERO ================= */
.hero{position:relative;background:var(--bg);background-image:radial-gradient(rgba(9,114,104,.07) 1px,transparent 1px);background-size:22px 22px;border-bottom:1px solid var(--line);padding:72px 0 84px}
.hero-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center}
.badge-agr{display:inline-flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);border-radius:999px;padding:7px 15px;font:600 12.5px var(--font-b);color:var(--emerald);box-shadow:var(--shadow-1)}
.badge-agr svg{width:15px;height:15px}
.hero h1{font-size:clamp(2.3rem,4.6vw,3.7rem);font-weight:700;margin:22px 0 18px}
.hero h1 .hl{background:linear-gradient(transparent 62%,var(--gold-100) 62%);border-radius:3px;padding:0 3px;white-space:nowrap}
.hero-sub{font-size:17px;color:var(--ink-2);max-width:34rem;margin-bottom:30px}
.hero-cta{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:26px}
.cur-mod{display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:14px;color:var(--ink-3)}
.cur-mod b{color:var(--ink-2);font-weight:600}
.hero-proof{display:flex;align-items:center;gap:20px;flex-wrap:wrap;margin-top:32px;padding-top:24px;border-top:1px solid var(--line)}
.stars{display:inline-flex;gap:2px}
.stars svg{width:15px;height:15px;fill:var(--gold-600);stroke:var(--gold-600)}
.proof-it{font-size:13.5px;color:var(--ink-3)}
.proof-it b{color:var(--ink);font-family:var(--font-n)}
.proof-sep{width:1px;height:26px;background:var(--line)}

/* ---- Carte d'assuré 3D ---- */
.card-scene{position:relative;perspective:1300px;width:min(420px,100%);margin:0 auto}
.card-tilt{transform-style:preserve-3d;transition:transform .6s cubic-bezier(.2,.75,.3,1)}
.card-tilt.gliding{transition:transform .07s linear}
.card-flip{position:relative;transform-style:preserve-3d;transition:transform .75s cubic-bezier(.25,.8,.3,1);cursor:pointer;aspect-ratio:1.586}
.card-flip.flipped{transform:rotateY(180deg)}
.card-face{position:absolute;inset:0;border-radius:20px;backface-visibility:hidden;-webkit-backface-visibility:hidden;transform-style:preserve-3d;background:var(--card-bg);color:var(--card-ink);padding:22px 24px;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;box-shadow:0 30px 60px -22px rgba(6,74,67,.5),inset 0 1px 0 rgba(255,255,255,.14)}
.card-back{transform:rotateY(180deg)}
.card-front::after{content:"";position:absolute;inset:0;border-radius:inherit;background:radial-gradient(240px circle at var(--gx,72%) var(--gy,20%),rgba(255,255,255,.15),transparent 62%);pointer-events:none;transition:opacity .3s}
.member-card[data-plan="bronze"]{--card-bg:#7A4A21;--card-ink:#FFF7EC;--card-accent:#F0C987}
.member-card[data-plan="silver"]{--card-bg:#064A43;--card-ink:#ECFDF8;--card-accent:#5EEAD4}
.member-card[data-plan="gold"]{--card-bg:#141B2B;--card-ink:#F5F1E6;--card-accent:#E8B54D}
.member-card[data-plan="platinium"]{--card-bg:#414C5C;--card-ink:#F8FAFC;--card-accent:#DDE5EE}
.cf-guilloche{position:absolute;inset:0;width:100%;height:100%;color:#fff;pointer-events:none}
.cf-top{display:flex;justify-content:space-between;align-items:flex-start;position:relative;z-index:2}
.cf-brand{display:flex;align-items:center;gap:10px}
.cf-brand>svg{width:34px;height:34px}
.cf-bname b{display:block;font:700 15.5px var(--font-h);letter-spacing:-.01em;line-height:1.1}
.cf-bname i{font:600 8.5px var(--font-b);font-style:normal;letter-spacing:.2em;text-transform:uppercase;opacity:.72}
.cf-status{display:inline-flex;align-items:center;gap:7px;background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.22);border-radius:999px;padding:5.5px 12px;font:600 10.5px var(--font-b);letter-spacing:.06em;text-transform:uppercase;transform:translateZ(26px)}
.cf-status i{width:6.5px;height:6.5px;border-radius:50%;background:#34D399;box-shadow:0 0 0 3px rgba(52,211,153,.25);animation:blink 2.4s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.cf-mid{position:relative;z-index:2;display:flex;flex-direction:column;gap:12px}
.cf-chip{width:42px;height:31px;border-radius:7px;background:linear-gradient(135deg,#E2A93E,#F6D58A 55%,#D9932C);position:relative;transform:translateZ(24px);flex:none}
.cf-chip::before,.cf-chip::after{content:"";position:absolute;background:rgba(90,60,10,.35);border-radius:2px}
.cf-chip::before{left:0;right:0;top:13px;height:4px}
.cf-chip::after{top:6px;bottom:6px;left:18px;width:4px}
.cf-label{display:block;font:600 8.5px var(--font-b);letter-spacing:.18em;text-transform:uppercase;opacity:.66;margin-bottom:3px}
.cf-number{font:600 15px var(--font-n);letter-spacing:.08em}
.cf-number b{font-weight:800;color:var(--card-accent)}
.cf-holder b{font:700 17px var(--font-h);letter-spacing:.05em;text-transform:uppercase}
.cf-valid{font:600 11px var(--font-n);opacity:.75;margin-top:2px}
.cf-bottom{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;position:relative;z-index:2}
.cf-plan{display:inline-block;background:var(--card-accent);color:rgba(12,26,22,.88);font:700 10px var(--font-b);letter-spacing:.1em;padding:4px 10px;border-radius:6px;margin-bottom:9px;text-transform:uppercase}
.cap-bar{width:92px;height:5px;border-radius:99px;background:rgba(255,255,255,.2);overflow:hidden;flex:none}
.cap-bar i{display:block;height:100%;background:var(--card-accent);border-radius:99px}
.cf-capline{display:flex;align-items:center;gap:9px;margin-bottom:9px}
.cf-capline em{font:500 10.5px var(--font-b);font-style:normal;opacity:.78}
.cf-emerg{display:inline-flex;align-items:center;gap:7px;font:600 11px var(--font-b);opacity:.86}
.cf-emerg svg{width:12.5px;height:12.5px}
.cf-qr{background:#fff;border-radius:10px;padding:6px;width:76px;height:76px;flex:none;transform:translateZ(30px)}
.cf-qr svg{width:100%;height:100%}
.scene-hint{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:22px;font:500 12.5px var(--font-b);color:var(--ink-3)}
.scene-hint svg{width:14px;height:14px}
.float-tag{position:absolute;background:#fff;border:1px solid var(--line);border-radius:12px;padding:9px 14px;font:600 12.5px var(--font-b);color:var(--ink-2);box-shadow:var(--shadow-1);display:flex;align-items:center;gap:9px;z-index:3}
.float-tag svg{width:15px;height:15px;color:var(--emerald)}
.ft-1{top:-16px;left:-26px;animation:floaty 5.5s ease-in-out infinite}
.ft-2{bottom:14px;right:-30px;animation:floaty 6.5s ease-in-out 1.2s infinite}
@keyframes floaty{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}
@media(max-width:1080px){.ft-1,.ft-2{display:none}}
@media(max-width:960px){.hero{padding:52px 0 64px}.hero-grid{grid-template-columns:1fr;gap:52px}.hero-sub{font-size:16px}}
.member-card.static .card-face{position:relative;width:100%}

/* ================= BANDE STATS ================= */
.stats-band{background:#fff;border-bottom:1px solid var(--line)}
.stats-list{display:flex;flex-wrap:wrap;padding:30px 0}
.stat{flex:1 1 150px;padding:6px 26px;display:flex;flex-direction:column;gap:2px;border-left:1px solid var(--line)}
.stat:first-child{border-left:0;padding-left:0}
.stat b{font:700 30px var(--font-h);color:var(--emerald);letter-spacing:-.03em;line-height:1.1}
.stat span{font:500 13px var(--font-b);color:var(--ink-3)}
@media(max-width:860px){.stat{flex:1 1 40%;padding:12px 20px;border-left:0}.stat:nth-child(even){border-left:1px solid var(--line)}}

/* ================= EN-TÊTES DE SECTION ================= */
.sec{padding:88px 0}
.sec-head{display:flex;gap:26px;align-items:flex-start;margin-bottom:52px}
.sec-index{font:800 52px var(--font-h);color:var(--line);line-height:.9;flex:none;letter-spacing:-.04em}
.eyebrow{display:flex;align-items:center;gap:10px;font:700 12.5px var(--font-b);letter-spacing:.16em;text-transform:uppercase;color:var(--emerald);margin-bottom:12px}
.eyebrow::before{content:"";width:26px;height:2.5px;background:var(--gold-600);border-radius:2px}
.sec-head h2{font-size:clamp(1.7rem,3.1vw,2.5rem);font-weight:700;margin-bottom:12px}
.sec-sub{color:var(--ink-3);font-size:16px;max-width:44rem}
@media(max-width:640px){.sec{padding:60px 0}.sec-index{font-size:38px}.sec-head{gap:16px;margin-bottom:36px}}

/* ================= SIMULATEUR ================= */
#simulateur{background:#fff;border-bottom:1px solid var(--line)}
.sim-grid{display:grid;grid-template-columns:1fr 380px;gap:44px;align-items:start}
.step-f{border:0;margin-bottom:38px}
.step-f legend{font:700 12px var(--font-b);letter-spacing:.14em;text-transform:uppercase;color:var(--emerald);margin-bottom:16px;display:flex;align-items:center;gap:10px}
.stno{display:inline-grid;place-items:center;width:24px;height:24px;border-radius:7px;background:var(--emerald-050);color:var(--emerald);font:800 11.5px var(--font-n)}
.opt-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.opt{display:flex;gap:13px;align-items:center;padding:14px;border:1.5px solid var(--line);border-radius:var(--r-md);background:#fff;cursor:pointer;transition:.18s;position:relative}
.opt input{position:absolute;opacity:0;pointer-events:none}
.opt:hover{border-color:rgba(13,148,136,.55)}
.opt.on{border-color:var(--emerald);background:var(--emerald-050);box-shadow:0 0 0 3px rgba(9,114,104,.08)}
.o-ic{width:40px;height:40px;border-radius:11px;background:#F1F5F9;display:grid;place-items:center;color:var(--emerald);flex:none;transition:.18s}
.o-ic svg{width:19px;height:19px}
.opt.on .o-ic{background:var(--emerald);color:#fff}
.opt b{display:block;font:600 14.5px var(--font-b)}
.opt small{display:block;font:500 12px var(--font-b);color:var(--ink-3);line-height:1.35}
.chips{display:flex;flex-wrap:wrap;gap:9px}
.chip{padding:9.5px 17px;border:1.5px solid var(--line);border-radius:999px;font:600 13.5px var(--font-b);color:var(--ink-2);cursor:pointer;transition:.16s;position:relative;background:#fff}
.chip input{position:absolute;opacity:0;pointer-events:none}
.chip:hover{border-color:rgba(13,148,136,.55)}
.chip.on{background:var(--emerald);border-color:var(--emerald);color:#fff}
.chip.on small{color:rgba(255,255,255,.72)}
.chip small{font:500 11px var(--font-n);color:var(--ink-3);margin-left:6px}
.pme-box{margin-top:14px;display:none;align-items:center;gap:16px;flex-wrap:wrap;background:var(--emerald-050);border:1.5px solid var(--emerald-100);border-radius:var(--r-md);padding:14px 18px}
.pme-box.show{display:flex}
.pme-box label{font:600 13.5px var(--font-b);color:var(--ink-2)}
.stepper{display:inline-flex;align-items:center;gap:4px;background:#fff;border:1.5px solid var(--line);border-radius:11px;padding:5px}
.stepper button{width:32px;height:32px;border-radius:8px;border:0;background:#F1F5F9;display:grid;place-items:center;color:var(--ink-2);transition:.15s}
.stepper button:hover{background:var(--emerald);color:#fff}
.stepper button svg{width:15px;height:15px}
.stepper b{font:700 17px var(--font-n);min-width:44px;text-align:center}
.pme-unit{font:600 13px var(--font-b);color:var(--emerald)}
.p-opts{display:grid;grid-template-columns:repeat(auto-fill,minmax(165px,1fr));gap:12px}
.p-opt{padding:14px;border:1.5px solid var(--line);border-radius:var(--r-md);cursor:pointer;transition:.18s;background:#fff;position:relative}
.p-opt input{position:absolute;opacity:0;pointer-events:none}
.p-opt:hover{border-color:rgba(13,148,136,.55)}
.p-opt.on{border-color:var(--emerald);background:var(--emerald-050);box-shadow:0 0 0 3px rgba(9,114,104,.08)}
.p-dot{width:12px;height:12px;border-radius:50%;background:var(--c);margin-bottom:9px;box-shadow:0 0 0 3.5px color-mix(in srgb,var(--c) 18%,transparent)}
.p-opt b{display:block;font:700 15px var(--font-h)}
.p-opt span{font:500 12px var(--font-b);color:var(--ink-3);display:block;margin-bottom:5px}
.p-opt em{font:600 12.5px var(--font-n);font-style:normal;color:var(--emerald)}
.sim-panel{background:var(--emerald-900);color:#ECFDF8;border-radius:22px;padding:28px;position:sticky;top:104px;box-shadow:var(--shadow-2)}
.sp-live{display:flex;align-items:center;gap:9px;font:700 11.5px var(--font-b);letter-spacing:.16em;text-transform:uppercase;color:#8BE0D2;margin-bottom:20px}
.sp-rows{display:flex;flex-direction:column;gap:11px;padding-bottom:20px;border-bottom:1px solid rgba(255,255,255,.14);margin-bottom:20px}
.sp-row{display:flex;justify-content:space-between;gap:14px;font-size:14px}
.sp-row span{color:rgba(255,255,255,.62)}
.sp-row b{font-weight:600;text-align:right}
.sp-cycle{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.sp-cycle>span{font:600 13px var(--font-b);color:rgba(255,255,255,.75)}
.big-price{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}
.big-price .bp-v{font:800 clamp(2.4rem,3.4vw,3rem) var(--font-n);letter-spacing:-.03em;line-height:1;color:#fff}
.big-price .bp-u{font:600 14px var(--font-b);color:rgba(255,255,255,.66)}
.sp-save{display:inline-flex;align-items:center;gap:8px;background:var(--gold-100);color:#92400E;font:600 12.5px var(--font-b);border-radius:9px;padding:7px 12px;margin-top:14px}
.sp-save svg{width:14px;height:14px}
.sp-detail{display:flex;flex-direction:column;gap:5px;margin-top:14px;font-size:13px;color:rgba(255,255,255,.72)}
.sp-detail b{color:#fff;font-family:var(--font-n)}
.sim-panel .btn{margin-top:22px}
.panel-notes{list-style:none;margin-top:18px;display:flex;flex-direction:column;gap:7px}
.panel-notes li{display:flex;align-items:center;gap:9px;font:500 12.5px var(--font-b);color:rgba(255,255,255,.72)}
.panel-notes svg{width:13px;height:13px;color:#5EEAD4;flex:none}
@media(max-width:1020px){.sim-grid{grid-template-columns:1fr}.sim-panel{position:static}}

/* ================= FORMULES ================= */
#garanties{background:var(--bg)}
.plans-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;align-items:stretch;margin-bottom:56px}
.plan-card{background:#fff;border:1.5px solid var(--line);border-radius:var(--r-lg);padding:24px 22px;display:flex;flex-direction:column;position:relative;transition:transform .22s,box-shadow .22s,border-color .22s}
.plan-card:hover{transform:translateY(-4px);box-shadow:var(--shadow-1);border-color:#CBD5E1}
.plan-card.sel{border-color:var(--emerald);box-shadow:0 0 0 3px rgba(9,114,104,.1)}
.plan-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:6px}
.plan-name{display:flex;align-items:center;gap:9px}
.plan-dot{width:11px;height:11px;border-radius:50%;background:var(--c);flex:none;box-shadow:0 0 0 3.5px color-mix(in srgb,var(--c) 17%,transparent)}
.plan-card h3{font-size:21px;font-weight:700}
.plan-tag{font:600 12px var(--font-b);color:var(--ink-3);display:block;margin:2px 0 12px 20px}
.plan-price{font:600 12px var(--font-b);color:var(--ink-3);text-align:right;line-height:1.3;white-space:nowrap}
.plan-price b{display:block;font:700 19px var(--font-n);color:var(--ink);letter-spacing:-.02em}
.plan-desc{font-size:13.5px;color:var(--ink-2);padding-bottom:16px;border-bottom:1px solid var(--line-2);margin-bottom:16px}
.plan-feats{list-style:none;display:flex;flex-direction:column;gap:10px;flex:1;margin-bottom:22px}
.plan-feats li{display:flex;gap:10px;font:500 13.5px var(--font-b);color:var(--ink-2);align-items:flex-start}
.plan-feats svg{width:15px;height:15px;color:var(--emerald);flex:none;margin-top:3px}
.plan-feats li.muted svg{color:var(--ink-3)}
.plan-feats li.muted{color:var(--ink-3)}
.plan-card.featured{background:var(--emerald-900);border-color:var(--emerald-900);color:#ECFDF8;transform:translateY(-12px);box-shadow:0 34px 64px -26px rgba(6,74,67,.55)}
.plan-card.featured:hover{transform:translateY(-16px)}
.plan-card.featured .plan-tag,.plan-card.featured .plan-price{color:rgba(255,255,255,.66)}
.plan-card.featured .plan-price b{color:#fff}
.plan-card.featured .plan-desc{color:rgba(255,255,255,.82);border-color:rgba(255,255,255,.15)}
.plan-card.featured .plan-feats li{color:rgba(255,255,255,.9)}
.plan-card.featured .plan-feats svg{color:#5EEAD4}
.plan-ribbon{position:absolute;top:-14px;left:50%;transform:translateX(-50%);background:var(--gold-600);color:#FFF7E6;font:700 11px var(--font-b);letter-spacing:.08em;text-transform:uppercase;padding:6px 14px;border-radius:999px;white-space:nowrap;box-shadow:0 6px 16px -4px rgba(217,119,6,.5)}
.plan-stars{display:flex;align-items:center;gap:8px;margin:-4px 0 12px 20px}
.plan-stars .stars svg{width:13px;height:13px}
.plan-stars span{font:500 11.5px var(--font-b);color:rgba(255,255,255,.66)}
.plan-card.gold{background:var(--gold-050);border-color:#EAD9A8}
.plan-card.gold .plan-price b{color:#8A5A10}
.plan-card.dark{background:#0F172A;border-color:#0F172A;color:#F1F5F9}
.plan-card.dark .plan-tag,.plan-card.dark .plan-price{color:rgba(255,255,255,.6)}
.plan-card.dark .plan-price b{color:#fff}
.plan-card.dark .plan-desc{color:rgba(255,255,255,.78);border-color:rgba(255,255,255,.13)}
.plan-card.dark .plan-feats li{color:rgba(255,255,255,.88)}
.plan-card.dark .plan-feats svg{color:#5EEAD4}
@media(max-width:1080px){.plans-grid{grid-template-columns:repeat(2,1fr)}.plan-card.featured{transform:none}.plan-card.featured:hover{transform:translateY(-4px)}}
@media(max-width:660px){.plans-grid{grid-template-columns:1fr}}

.cmp-title{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:20px}
.cmp-title h3{font-size:22px}
.cmp-title p{font-size:14px;color:var(--ink-3)}
.cmp-wrap{overflow-x:auto;border:1.5px solid var(--line);border-radius:var(--r-lg);background:#fff;box-shadow:var(--shadow-1)}
.cmp-wrap table{border-collapse:collapse;width:100%;min-width:820px}
.cmp-wrap th,.cmp-wrap td{padding:13px 18px;border-bottom:1px solid var(--line-2);text-align:center;font:500 13.5px var(--font-b);color:var(--ink-2);transition:background .2s}
.cmp-wrap tr:last-child td{border-bottom:0}
.cmp-wrap td:first-child,.cmp-wrap th:first-child{text-align:left;position:sticky;left:0;background:#fff;font-weight:600;color:var(--ink);min-width:210px;z-index:2;box-shadow:1px 0 0 var(--line-2)}
.cmp-wrap thead th{vertical-align:top;padding-top:20px;padding-bottom:18px;background:#FBFDFC}
.th-plan{display:flex;align-items:center;justify-content:center;gap:8px;font:700 16px var(--font-h);color:var(--ink)}
.th-plan i{width:9px;height:9px;border-radius:50%;background:var(--c)}
.th-tag{display:block;font:600 11px var(--font-b);color:var(--ink-3);margin:3px 0 8px}
.th-price{display:block;font:700 14px var(--font-n);color:var(--emerald);margin-bottom:12px}
.th-choose{border:1.5px solid var(--line);background:#fff;color:var(--ink-2);border-radius:9px;padding:7px 16px;font:600 12.5px var(--font-b);transition:.16s}
.th-choose:hover{border-color:var(--emerald);color:var(--emerald)}
th[data-col="silver"] .th-choose{background:var(--emerald);border-color:var(--emerald);color:#fff}
th[data-col="silver"] .th-choose:hover{background:var(--emerald-500)}
th[data-col="silver"] .th-plan small{font:700 9px var(--font-b);letter-spacing:.1em;color:#92400E;background:var(--gold-100);padding:3px 8px;border-radius:99px;text-transform:uppercase}
td[data-col].sel,th[data-col].sel{background:rgba(13,148,136,.075)}
td[data-col="silver"].sel,th[data-col="silver"].sel{background:#E2F3EE}
.v-no{color:#B4BFCB}
.v-inc{color:var(--emerald);font-weight:600}
.v-strong{font-family:var(--font-n);font-weight:600;color:var(--ink)}

/* ================= ALLIANCE ================= */
#services{background:#fff;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.ally-grid{display:grid;grid-template-columns:1.18fr .82fr;gap:22px}
.ally-card{border:1.5px solid var(--line);border-radius:24px;padding:34px;display:flex;flex-direction:column;gap:18px}
.ally-tag{display:inline-flex;align-items:center;gap:9px;align-self:flex-start;font:700 11.5px var(--font-b);letter-spacing:.14em;text-transform:uppercase;border-radius:999px;padding:7px 14px}
.ally-tag.a1{background:var(--emerald-050);color:var(--emerald)}
.ally-tag.a2{background:var(--gold-100);color:#92400E}
.ally-tag svg{width:14px;height:14px}
.ally-card h3{font-size:clamp(1.35rem,2vw,1.7rem)}
.ally-card>p{font-size:15px;color:var(--ink-2)}
.ally-feats{list-style:none;display:flex;flex-direction:column;gap:11px}
.ally-feats li{display:flex;gap:11px;font:500 14px var(--font-b);color:var(--ink-2);align-items:flex-start}
.ally-feats svg{width:16px;height:16px;color:var(--emerald);flex:none;margin-top:3px}
.ally-feats li.strong{font-weight:600;color:var(--ink)}
.lisa-body{display:grid;grid-template-columns:1fr 300px;gap:32px;align-items:center;flex:1}
.lisa-actions{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.lisa-note{font:500 12.5px var(--font-b);color:var(--ink-3);display:flex;align-items:center;gap:7px}
.lisa-note svg{width:14px;height:14px;color:var(--emerald)}
.phone{background:#0F172A;border-radius:30px;padding:10px;box-shadow:0 24px 44px -18px rgba(15,23,42,.5);width:100%;max-width:300px;justify-self:center}
.phone-scr{background:#EFEAE2;border-radius:21px;overflow:hidden;display:flex;flex-direction:column;height:430px}
.ph-head{background:var(--emerald-900);color:#fff;padding:12px 14px;display:flex;align-items:center;gap:11px;flex:none}
.ph-av{width:36px;height:36px;border-radius:50%;background:var(--emerald-500);display:grid;place-items:center;font:700 14px var(--font-h);flex:none}
.ph-head b{display:block;font:600 13.5px var(--font-b);line-height:1.2}
.ph-head span{display:flex;align-items:center;gap:5px;font:500 11px var(--font-b);color:#A7E8DA}
.ph-head span i{width:6px;height:6px;border-radius:50%;background:#34D399}
.chat{flex:1;overflow-y:auto;padding:14px 12px;display:flex;flex-direction:column;gap:9px;scrollbar-width:none}
.chat::-webkit-scrollbar{display:none}
.msg{max-width:84%;border-radius:11px;padding:8px 11px 6px;font:500 12.5px var(--font-b);line-height:1.45;animation:msgin .4s cubic-bezier(.2,.8,.3,1);align-self:flex-start;background:#fff;box-shadow:0 1px 1px rgba(15,23,42,.08)}
.msg.me{align-self:flex-end;background:#D9FDD3}
.msg span{display:block;font:500 9.5px var(--font-n);color:#94A3B8;text-align:right;margin-top:3px}
.msg-doc{align-self:flex-start;background:#fff;border-radius:11px;padding:9px 12px;display:flex;gap:10px;align-items:center;max-width:88%;animation:msgin .4s cubic-bezier(.2,.8,.3,1);box-shadow:0 1px 1px rgba(15,23,42,.08)}
.msg-doc svg{width:20px;height:20px;color:var(--emerald);flex:none}
.msg-doc b{display:block;font:600 12px var(--font-b)}
.msg-doc small{font:500 10.5px var(--font-b);color:var(--emerald)}
@keyframes msgin{from{opacity:0;transform:translateY(9px) scale(.95)}}
.ongwa-card{background:var(--gold-050);border-color:#EAD9A8}
.ongwa-inner{display:flex;flex-direction:column;gap:16px;flex:1}
.visit-report{background:#fff;border:1.5px solid #EAD9A8;border-radius:var(--r-md);padding:18px}
.vr-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}
.vr-head b{font:700 13.5px var(--font-b)}
.vr-head span{font:500 11.5px var(--font-n);color:var(--ink-3)}
.vr-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-bottom:13px}
.vr-m{background:#FFFDF4;border:1px solid #F3E8C8;border-radius:10px;padding:9px 10px}
.vr-m span{display:block;font:600 10px var(--font-b);letter-spacing:.05em;text-transform:uppercase;color:#A16207}
.vr-m b{font:700 15px var(--font-n);color:var(--ink)}
.vr-note{font:500 13px var(--font-b);color:var(--ink-2);font-style:italic;margin-bottom:13px}
.vr-stamp{display:inline-flex;align-items:center;gap:8px;background:var(--emerald-050);color:var(--emerald);border-radius:9px;padding:7px 12px;font:600 12px var(--font-b)}
.vr-stamp svg{width:14px;height:14px}
.ongwa-next{display:flex;align-items:center;gap:13px;background:#fff;border:1.5px solid #EAD9A8;border-radius:var(--r-md);padding:14px 16px}
.ongwa-next .o-ic{background:var(--gold-100);color:#92400E}
.ongwa-next b{display:block;font:600 13.5px var(--font-b)}
.ongwa-next small{font:500 12px var(--font-b);color:var(--ink-3)}
@media(max-width:1020px){.ally-grid{grid-template-columns:1fr}.lisa-body{grid-template-columns:1fr}}

/* ================= RÉSEAU ================= */
#reseau{background:#F2F9F7}
.net-tools{display:flex;flex-direction:column;gap:16px;margin-bottom:26px}
.net-search{display:flex;align-items:center;gap:12px;background:#fff;border:1.5px solid var(--line);border-radius:14px;padding:4px 16px;box-shadow:var(--shadow-1)}
.net-search svg{width:19px;height:19px;color:var(--ink-3);flex:none}
.net-search input{flex:1;border:0;outline:0;font:500 15px var(--font-b);padding:13px 0;background:transparent;color:var(--ink)}
.net-search input::placeholder{color:#94A3B8}
.net-filters{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.net-filters .chip{padding:8px 14px;font-size:13px}
.tp-switch{display:inline-flex;align-items:center;gap:10px;font:600 13px var(--font-b);color:var(--ink-2);cursor:pointer;user-select:none;margin-left:auto}
.tp-switch input{position:absolute;opacity:0}
.tp-track{width:40px;height:23px;border-radius:99px;background:#CBD5E1;position:relative;transition:.2s;flex:none}
.tp-track::after{content:"";position:absolute;top:2.5px;left:2.5px;width:18px;height:18px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(15,23,42,.25);transition:.2s}
.tp-switch input:checked+.tp-track{background:var(--blue-800)}
.tp-switch input:checked+.tp-track::after{transform:translateX(17px)}
.net-count{font:600 13.5px var(--font-b);color:var(--ink-3);margin-bottom:16px;display:block}
.net-list{display:flex;flex-direction:column;gap:12px}
.net-row{display:flex;gap:16px;padding:18px 20px;background:#fff;border:1.5px solid var(--line);border-radius:16px;align-items:center;transition:.18s}
.net-row:hover{border-color:rgba(13,148,136,.5);box-shadow:var(--shadow-1);transform:translateY(-1.5px)}
.net-ic{width:48px;height:48px;border-radius:13px;display:grid;place-items:center;flex:none}
.net-ic svg{width:21px;height:21px}
.net-ic.k-clinic{background:var(--emerald-050);color:var(--emerald)}
.net-ic.k-pharmacy{background:var(--gold-100);color:#92400E}
.net-ic.k-center{background:var(--blue-050);color:var(--blue-800)}
.net-main{flex:1;min-width:0}
.net-title{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:5px}
.net-title h4{font-size:16.5px;font-weight:700}
.tp-badge{display:inline-flex;align-items:center;gap:6px;background:var(--blue-050);color:var(--blue-800);border:1px solid #C7D7FE;border-radius:999px;padding:3.5px 11px;font:600 11.5px var(--font-b)}
.tp-badge svg{width:12.5px;height:12.5px}
.net-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font:500 13px var(--font-b);color:var(--ink-3)}
.net-meta svg{width:13.5px;height:13.5px}
.dot-sep{width:3px;height:3px;border-radius:50%;background:#CBD5E1}
.net-rate{display:inline-flex;align-items:center;gap:5px;color:var(--ink-2);font-family:var(--font-n);font-weight:600}
.net-rate svg{width:13.5px;height:13.5px;fill:var(--gold-600);stroke:var(--gold-600)}
.net-specs{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.net-specs span{font:500 11.5px var(--font-b);color:var(--ink-3);background:#F1F5F9;border-radius:6px;padding:3px 9px}
.net-actions{display:flex;gap:9px;flex:none}
.net-empty{background:#fff;border:1.5px dashed var(--line);border-radius:16px;padding:46px 24px;text-align:center;color:var(--ink-3)}
.net-empty svg{width:34px;height:34px;margin:0 auto 12px;color:#B4BFCB}
.net-empty b{display:block;font:600 16px var(--font-b);color:var(--ink-2);margin-bottom:6px}
@media(max-width:760px){.net-row{flex-wrap:wrap}.net-actions{width:100%}.net-actions .btn{flex:1}.tp-switch{margin-left:0}}

/* ================= CTA FINAL ================= */
.cta-final{background:var(--emerald-900);color:#fff;padding:92px 0;position:relative;overflow:hidden}
.cta-final .cf-guilloche{z-index:0}
.cta-in{position:relative;z-index:1;text-align:center;max-width:660px;margin:0 auto}
.cta-in h2{font-size:clamp(1.9rem,3.6vw,2.9rem);margin-bottom:16px}
.cta-in p{color:rgba(255,255,255,.78);font-size:16.5px;margin-bottom:34px}
.cta-btns{display:flex;gap:14px;justify-content:center;flex-wrap:wrap}
.cta-note{margin-top:30px;font:500 13px var(--font-b);color:rgba(255,255,255,.55);display:flex;align-items:center;justify-content:center;gap:9px;flex-wrap:wrap}
.cta-note svg{width:14px;height:14px;color:#5EEAD4}
</style>

<!-- ═══════════ HERO ═══════════ -->
<section class="hero">
  <div class="wrap hero-grid">
    <div>
      <span class="badge-agr"><i data-lucide="shield-check"></i>Établissement agréé CSSA · n° 045/CSSA/2024 · Cameroun</span>
      <h1>La mutuelle santé qui protège votre famille au pays et en entreprise, <span class="hl">sans avance de frais</span>.</h1>
      <p class="hero-sub">Adhérez en ligne depuis Paris, Bruxelles ou Montréal — ou directement depuis Douala. Tiers-payant intégral dans plus de 45 cliniques partenaires, médecin de garde 24/7 sur WhatsApp et infirmières à domicile pour vos parents, dès <b class="num" data-base-eur="23">23 €</b> par mois.</p>
      <div class="hero-cta">
        <a class="btn btn-primary" href="#simulateur"><i data-lucide="heart-pulse"></i>Simuler ma cotisation</a>
        <a class="btn btn-ghost" href="#garanties"><i data-lucide="shield"></i>Explorer les garanties</a>
      </div>
      <div class="cur-mod">
        <b>Vous cotisez depuis l'étranger ?</b>
        <div class="seg" data-cur-seg role="group" aria-label="Choix de la devise">
          <button type="button" data-cur="EUR" class="on">€ EUR</button>
          <button type="button" data-cur="USD">$ USD</button>
          <button type="button" data-cur="XAF">FCFA</button>
        </div>
      </div>
      <div class="hero-proof">
        <span class="proof-it"><span class="stars" aria-label="Note 4,8 sur 5"><i data-lucide="star"></i><i data-lucide="star"></i><i data-lucide="star"></i><i data-lucide="star"></i><i data-lucide="star"></i></span>&nbsp;<b>4,8/5</b> — 1 234 avis</span>
        <span class="proof-sep"></span>
        <span class="proof-it"><b>45+</b> cliniques conventionnées</span>
        <span class="proof-sep"></span>
        <span class="proof-it"><b>12 400</b> familles protégées</span>
      </div>
    </div>
    <div class="card-scene" id="cardScene">
      <span class="float-tag ft-1"><i data-lucide="shield-check"></i>Zéro avance de frais</span>
      <span class="float-tag ft-2"><i data-lucide="qr-code"></i>QR scanné en clinique</span>
      <div class="card-tilt member-card" id="cardTilt" data-plan="silver">
        <div class="card-flip" id="cardFlip" role="button" tabindex="0" aria-label="Carte Mutuelle Digitale — cliquer pour la retourner">
          <div class="card-face card-front" id="heroFront"></div>
          <div class="card-face card-back">
            <svg class="cf-guilloche" viewBox="0 0 340 214" fill="none" aria-hidden="true"><g stroke="currentColor" stroke-opacity=".09"><circle cx="312" cy="30" r="20"/><circle cx="312" cy="30" r="42"/><circle cx="312" cy="30" r="64"/><circle cx="20" cy="196" r="30"/><circle cx="20" cy="196" r="52"/></g></svg>
            <div class="cf-top">
              <div class="cf-brand">
                <svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="rgba(255,255,255,.14)"/><rect x="13" y="6" width="6" height="20" rx="3" fill="#fff"/><rect x="6" y="13" width="20" height="6" rx="3" fill="#fff"/><path d="M7 16h5l2-3.5 3 7 2-3.5h6" stroke="#D97706" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
                <span class="cf-bname"><b>MulemaCare</b><i>Mutuelle Santé · CSSA</i></span>
              </div>
              <span class="cf-status"><i></i>Carte active</span>
            </div>
            <div style="position:relative;z-index:2">
              <div style="height:38px;background:rgba(0,0,0,.55);margin:6px -24px 18px"></div>
              <b style="font:700 13px var(--font-b);letter-spacing:.06em;text-transform:uppercase;display:block;margin-bottom:8px;color:var(--card-accent)">Conditions d'utilisation</b>
              <p style="font:500 12px var(--font-b);line-height:1.55;opacity:.85;margin-bottom:18px">Carte nominative et strictement personnelle. Présentez-la à l'accueil de toute clinique ou pharmacie conventionnée : la prise en charge est immédiate, sans avance de frais. En cas d'urgence, appelez avant tout déplacement.</p>
              <div style="display:flex;flex-direction:column;gap:11px">
                <div style="display:flex;gap:11px;align-items:center"><span style="width:34px;height:34px;background:rgba(255,255,255,.12);color:#fff;display:grid;place-items:center;border-radius:9px;flex:none"><i data-lucide="phone-call"></i></span><div><b style="font:600 12.5px var(--font-b);display:block">Urgences &amp; SAMU — 24/7</b><span class="num" style="font:500 12px;opacity:.8">+237 521 120 21</span></div></div>
                <div style="display:flex;gap:11px;align-items:center"><span style="width:34px;height:34px;background:rgba(255,255,255,.12);color:#fff;display:grid;place-items:center;border-radius:9px;flex:none"><i data-lucide="message-circle"></i></span><div><b style="font:600 12.5px var(--font-b);display:block">Médecin de garde Lisacare</b><span style="font:500 12px var(--font-b);opacity:.8">WhatsApp — réponse en 4 min</span></div></div>
              </div>
            </div>
            <p style="position:relative;z-index:2;display:flex;align-items:center;gap:8px;font:600 10.5px var(--font-b);opacity:.72"><i data-lucide="badge-check" style="width:13px;height:13px"></i>Authenticité vérifiable sur mulemacare.com/verifier</p>
          </div>
        </div>
      </div>
      <p class="scene-hint"><i data-lucide="mouse-pointer-click"></i>Survolez la carte — cliquez pour la retourner</p>
    </div>
  </div>
</section>

<!-- ═══════════ BANDE DE CONFIANCE ═══════════ -->
<div class="stats-band">
  <div class="wrap stats-list">
    <div class="stat"><b>45+</b><span>cliniques conventionnées</span></div>
    <div class="stat"><b>6</b><span>pays d'Afrique couverts</span></div>
    <div class="stat"><b>12 400</b><span>adhérents protégés</span></div>
    <div class="stat"><b>0 jour</b><span>d'attente sur les urgences</span></div>
    <div class="stat"><b>2 min</b><span>pour adhérer en ligne</span></div>
    <div class="stat"><b>4,8/5</b><span>de satisfaction adhérents</span></div>
  </div>
</div>

<!-- ═══════════ LOGOS PARTENAIRES OFFICIELS ═══════════ -->
<div style="background:#fff;border-bottom:1px solid var(--line);padding:24px 0;overflow:hidden">
  <div class="wrap" style="display:flex;align-items:center;gap:28px;flex-wrap:wrap;justify-content:space-between">
    <span style="font:700 11.5px var(--font-b);letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);white-space:nowrap;display:flex;align-items:center;gap:7px">
      <i data-lucide="shield-check" style="width:16px;height:16px;color:var(--emerald)"></i>Réseau &amp; Agréments Santé :
    </span>
    <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;justify-content:center;opacity:.88">
      <img src="/assets/img/partenaires/0.jpg" alt="Partenaire Santé Agréé" height="34" style="height:34px;width:auto;object-fit:contain;border-radius:6px;filter:grayscale(0.3);transition:all .2s" onmouseover="this.style.filter='none';this.style.transform='scale(1.05)'" onmouseout="this.style.filter='grayscale(0.3)';this.style.transform='none'">
      <img src="/assets/img/partenaires/1.jpg" alt="Clinique Conventionnée" height="34" style="height:34px;width:auto;object-fit:contain;border-radius:6px;filter:grayscale(0.3);transition:all .2s" onmouseover="this.style.filter='none';this.style.transform='scale(1.05)'" onmouseout="this.style.filter='grayscale(0.3)';this.style.transform='none'">
      <img src="/assets/img/partenaires/2.jpg" alt="Centre Hospitalier" height="34" style="height:34px;width:auto;object-fit:contain;border-radius:6px;filter:grayscale(0.3);transition:all .2s" onmouseover="this.style.filter='none';this.style.transform='scale(1.05)'" onmouseout="this.style.filter='grayscale(0.3)';this.style.transform='none'">
      <img src="/assets/img/partenaires/3.png" alt="Pharmacie Partenaire" height="34" style="height:34px;width:auto;object-fit:contain;border-radius:6px;filter:grayscale(0.3);transition:all .2s" onmouseover="this.style.filter='none';this.style.transform='scale(1.05)'" onmouseout="this.style.filter='grayscale(0.3)';this.style.transform='none'">
      <img src="/assets/img/partenaires/5.jpg" alt="Laboratoire Médical" height="34" style="height:34px;width:auto;object-fit:contain;border-radius:6px;filter:grayscale(0.3);transition:all .2s" onmouseover="this.style.filter='none';this.style.transform='scale(1.05)'" onmouseout="this.style.filter='grayscale(0.3)';this.style.transform='none'">
      <img src="/assets/img/partenaires/7.png" alt="Groupe Santé" height="34" style="height:34px;width:auto;object-fit:contain;border-radius:6px;filter:grayscale(0.3);transition:all .2s" onmouseover="this.style.filter='none';this.style.transform='scale(1.05)'" onmouseout="this.style.filter='grayscale(0.3)';this.style.transform='none'">
      <img src="/assets/img/partenaires/11.png" alt="MFDI Partenaire" height="34" style="height:34px;width:auto;object-fit:contain;border-radius:6px;filter:grayscale(0.3);transition:all .2s" onmouseover="this.style.filter='none';this.style.transform='scale(1.05)'" onmouseout="this.style.filter='grayscale(0.3)';this.style.transform='none'">
      <img src="/assets/img/partenaires/ivory.png" alt="Ivory Health" height="34" style="height:34px;width:auto;object-fit:contain;border-radius:6px;filter:grayscale(0.3);transition:all .2s" onmouseover="this.style.filter='none';this.style.transform='scale(1.05)'" onmouseout="this.style.filter='grayscale(0.3)';this.style.transform='none'">
      <img src="/assets/img/partenaires/medical-insurance.png" alt="Medical Insurance Network" height="34" style="height:34px;width:auto;object-fit:contain;border-radius:6px;filter:grayscale(0.3);transition:all .2s" onmouseover="this.style.filter='none';this.style.transform='scale(1.05)'" onmouseout="this.style.filter='grayscale(0.3)';this.style.transform='none'">
    </div>
  </div>
</div>

<!-- ═══════════ SIMULATEUR ═══════════ -->
<section class="sec" id="simulateur">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">01</span>
      <div>
        <p class="eyebrow">Simulateur de cotisation</p>
        <h2>Votre devis santé en trois clics, dans votre devise.</h2>
        <p class="sec-sub">Ajustez le profil, la ville et le niveau de couverture : le prix se recalcule instantanément, sans rechargement ni engagement.</p>
      </div>
    </div>
    <div class="sim-grid">
      <div>
        <fieldset class="step-f reveal">
          <legend><span class="stno">1</span>Pour qui ?</legend>
          <div class="opt-grid" id="profileGrid">
            <label class="opt on"><input type="radio" name="profile" value="solo" checked><span class="o-ic"><i data-lucide="user"></i></span><span><b>Moi seul</b><small>Ma couverture personnelle</small></span></label>
            <label class="opt"><input type="radio" name="profile" value="couple"><span class="o-ic"><i data-lucide="heart-handshake"></i></span><span><b>Mon couple</b><small>Moi et mon conjoint</small></span></label>
            <label class="opt"><input type="radio" name="profile" value="famille"><span class="o-ic"><i data-lucide="users"></i></span><span><b>Ma famille au pays</b><small>2 adultes + 3 enfants</small></span></label>
            <label class="opt"><input type="radio" name="profile" value="seniors"><span class="o-ic"><i data-lucide="heart-pulse"></i></span><span><b>Mes parents âgés</b><small>2 seniors + visites Ongwa</small></span></label>
            <label class="opt"><input type="radio" name="profile" value="pme"><span class="o-ic"><i data-lucide="building-2"></i></span><span><b>Mes salariés — PME</b><small>Tarif dégressif par tête</small></span></label>
          </div>
          <div class="pme-box" id="pmeBox">
            <label for="pmeCount">Salariés à couvrir</label>
            <div class="stepper">
              <button type="button" id="pmeMinus" aria-label="Retirer un salarié"><i data-lucide="minus"></i></button>
              <b class="num" id="pmeCount">8</b>
              <button type="button" id="pmePlus" aria-label="Ajouter un salarié"><i data-lucide="plus"></i></button>
            </div>
            <span class="pme-unit" id="pmeUnit"></span>
          </div>
        </fieldset>
        <fieldset class="step-f reveal">
          <legend><span class="stno">2</span>Ville de couverture</legend>
          <div class="chips" id="cityChips">
            <label class="chip on"><input type="radio" name="city" value="douala" checked>Douala</label>
            <label class="chip"><input type="radio" name="city" value="yaounde">Yaoundé</label>
            <label class="chip"><input type="radio" name="city" value="kinshasa">Kinshasa</label>
            <label class="chip"><input type="radio" name="city" value="abidjan">Abidjan</label>
            <label class="chip"><input type="radio" name="city" value="dakar">Dakar</label>
            <label class="chip"><input type="radio" name="city" value="libreville">Libreville</label>
            <label class="chip"><input type="radio" name="city" value="bangui">Bangui</label>
          </div>
        </fieldset>
        <fieldset class="step-f reveal">
          <legend><span class="stno">3</span>Niveau de couverture</legend>
          <div class="p-opts" id="planOpts">
            <label class="p-opt" data-planc="bronze" style="--c:#8A5A2B"><input type="radio" name="plan" value="bronze"><span class="p-dot"></span><b>Bronze</b><span>Essentielle</span><em>dès <b class="num" data-base-eur="23">23 €</b>/mois</em></label>
            <label class="p-opt on" data-planc="silver" style="--c:#0D9488"><input type="radio" name="plan" value="silver" checked><span class="p-dot"></span><b>Silver</b><span>Famille &amp; soins courants</span><em>dès <b class="num" data-base-eur="42">42 €</b>/mois</em></label>
            <label class="p-opt" data-planc="gold" style="--c:#D97706"><input type="radio" name="plan" value="gold"><span class="p-dot"></span><b>Gold</b><span>Confort &amp; tiers-payant total</span><em>dès <b class="num" data-base-eur="68">68 €</b>/mois</em></label>
            <label class="p-opt" data-planc="platinium" style="--c:#475569"><input type="radio" name="plan" value="platinium"><span class="p-dot"></span><b>Platinium</b><span>Haut de gamme &amp; diaspora</span><em>dès <b class="num" data-base-eur="115">115 €</b>/mois</em></label>
          </div>
        </fieldset>
      </div>
      <aside class="sim-panel reveal" aria-live="polite">
        <p class="sp-live"><span class="pulse-dot"></span>Devis mis à jour en direct</p>
        <div class="sp-rows">
          <div class="sp-row"><span>Profil</span><b id="qProfile">Moi seul</b></div>
          <div class="sp-row"><span>Couverture</span><b id="qCity">Douala</b></div>
          <div class="sp-row"><span>Formule</span><b id="qPlan">Silver</b></div>
        </div>
        <div class="sp-cycle">
          <span>Périodicité</span>
          <div class="seg seg-dark" id="cycleSeg" role="group" aria-label="Périodicité de paiement">
            <button type="button" data-cycle="monthly" class="on">Mensuel</button>
            <button type="button" data-cycle="annual">Annuel</button>
          </div>
        </div>
        <div class="big-price"><span class="bp-v num" id="bigPrice">—</span><span class="bp-u" id="bigUnit">/ mois</span></div>
        <div class="sp-save" id="spSave"><i data-lucide="piggy-bank"></i><span id="spSaveTxt"></span></div>
        <div class="sp-detail" id="spDetail"></div>
        <button class="btn btn-white btn-block" id="simAdhere"><i data-lucide="badge-check"></i>Adhérer avec ce devis</button>
        <ul class="panel-notes">
          <li><i data-lucide="check"></i>Sans engagement, résiliable à tout moment</li>
          <li><i data-lucide="check"></i>Carte mutuelle digitale émise immédiatement</li>
          <li><i data-lucide="check"></i>Effectif dès le lendemain de l'adhésion</li>
        </ul>
      </aside>
    </div>
  </div>
</section>

<!-- ═══════════ FORMULES ═══════════ -->
<section class="sec" id="garanties">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">02</span>
      <div>
        <p class="eyebrow">Grille des garanties</p>
        <h2>Quatre formules, une même exigence : la transparence.</h2>
        <p class="sec-sub">De l'essentiel urgentiste au haut de gamme international — chaque garantie est écrite noir sur blanc, sans astérisque ni petites lignes.</p>
      </div>
    </div>
    <div class="plans-grid">
      <article class="plan-card reveal" data-planc="bronze" style="--c:#8A5A2B">
        <div class="plan-head">
          <div class="plan-name"><span class="plan-dot"></span><h3>Bronze</h3></div>
          <p class="plan-price">à partir de<b class="num" data-base-eur="23">23 €</b>/ mois</p>
        </div>
        <span class="plan-tag">Essentielle</span>
        <p class="plan-desc">Le filet de sécurité vital : urgences couvertes à 100 % et un médecin joignable jour et nuit.</p>
        <ul class="plan-feats">
          <li><i data-lucide="check"></i>Hospitalisation d'urgence à <b>100 %</b></li>
          <li><i data-lucide="check"></i>SAMU &amp; transport d'urgence inclus</li>
          <li><i data-lucide="check"></i>Télétriage Lisacare 24/7 sur WhatsApp</li>
          <li class="muted"><i data-lucide="minus"></i>Consultations &amp; pharmacie non couvertes</li>
        </ul>
        <button class="btn btn-ghost btn-block" data-open-sub="bronze">Souscrire Bronze</button>
      </article>
      <article class="plan-card featured reveal" data-planc="silver" style="--c:#5EEAD4">
        <span class="plan-ribbon">Le plus choisi par les familles</span>
        <div class="plan-head">
          <div class="plan-name"><span class="plan-dot" style="--c:#5EEAD4"></span><h3>Silver</h3></div>
          <p class="plan-price">à partir de<b class="num" data-base-eur="42">42 €</b>/ mois</p>
        </div>
        <span class="plan-tag">Famille &amp; soins courants</span>
        <div class="plan-stars"><span class="stars"><i data-lucide="star"></i><i data-lucide="star"></i><i data-lucide="star"></i><i data-lucide="star"></i><i data-lucide="star"></i></span><span>4,9/5 — 68 % des adhésions</span></div>
        <p class="plan-desc">L'équilibre parfait pour la famille : soins courants, maternité et pharmacie pris en main.</p>
        <ul class="plan-feats">
          <li><i data-lucide="check"></i>Tout Bronze, plus :</li>
          <li><i data-lucide="check"></i>Consultations généralistes à <b>70 %</b></li>
          <li><i data-lucide="check"></i>Spécialistes &amp; examens de laboratoire</li>
          <li><i data-lucide="check"></i>Pharmacie à <b>80 %</b> en tiers-payant</li>
          <li><i data-lucide="check"></i>Maternité suivie et accompagnée</li>
        </ul>
        <button class="btn btn-white btn-block" data-open-sub="silver">Souscrire Silver</button>
      </article>
      <article class="plan-card gold reveal" data-planc="gold" style="--c:#D97706">
        <div class="plan-head">
          <div class="plan-name"><span class="plan-dot"></span><h3>Gold</h3></div>
          <p class="plan-price">à partir de<b class="num" data-base-eur="68">68 €</b>/ mois</p>
        </div>
        <span class="plan-tag">Confort &amp; tiers-payant total</span>
        <p class="plan-desc">Zéro avance de frais en clinique conventionnée, et l'ajout des soins du quotidien.</p>
        <ul class="plan-feats">
          <li><i data-lucide="check"></i>Tout Silver, plus :</li>
          <li><i data-lucide="check"></i><b>Zéro avance de frais</b> en clinique partenaire</li>
          <li><i data-lucide="check"></i>Optique &amp; dentaire inclus</li>
          <li><i data-lucide="check"></i>Pharmacie à <b>100 %</b></li>
          <li><i data-lucide="check"></i>Transport sanitaire conventionné</li>
        </ul>
        <button class="btn btn-ghost btn-block" data-open-sub="gold">Souscrire Gold</button>
      </article>
      <article class="plan-card dark reveal" data-planc="platinium" style="--c:#94A3B8">
        <div class="plan-head">
          <div class="plan-name"><span class="plan-dot" style="--c:#94A3B8"></span><h3>Platinium</h3></div>
          <p class="plan-price">à partir de<b class="num" data-base-eur="115">115 €</b>/ mois</p>
        </div>
        <span class="plan-tag">Haut de gamme &amp; diaspora</span>
        <p class="plan-desc">La couverture prestige : plafond annuel de 8 000 000 FCFA (12 200 €), suite VIP et évacuation sanitaire.</p>
        <ul class="plan-feats">
          <li><i data-lucide="check"></i>Tout Gold, plus :</li>
          <li><i data-lucide="check"></i>Plafond annuel de <b>8 000 000 FCFA</b> (12 200 €)</li>
          <li><i data-lucide="check"></i>Lit d'accompagnant pour un proche</li>
          <li><i data-lucide="check"></i>Bilan de santé annuel complet (Carence 180j)</li>
          <li><i data-lucide="check"></i>Évacuation sanitaire internationale (Plafond 8M FCFA)</li>
        </ul>
        <button class="btn btn-white btn-block" data-open-sub="platinium">Souscrire Platinium</button>
      </article>
    </div>
    <div id="comparateur" class="reveal">
      <div class="cmp-title">
        <h3>Comparateur détaillé</h3>
        <p>Cliquez sur « Choisir » pour sélectionner une formule — les prix s'adaptent à votre devise.</p>
      </div>
      <div class="cmp-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Garanties</th>
              <th scope="col" data-col="bronze"><span class="th-plan" style="--c:#8A5A2B"><i></i>Bronze</span><span class="th-tag">Essentielle</span><span class="th-price num" data-base-eur="23">23 €</span><button class="th-choose" data-pick="bronze">Choisir</button></th>
              <th scope="col" data-col="silver"><span class="th-plan" style="--c:#0D9488"><i></i>Silver <small>Vedette</small></span><span class="th-tag">Famille</span><span class="th-price num" data-base-eur="42">42 €</span><button class="th-choose" data-pick="silver">Choisir</button></th>
              <th scope="col" data-col="gold"><span class="th-plan" style="--c:#D97706"><i></i>Gold</span><span class="th-tag">Confort</span><span class="th-price num" data-base-eur="68">68 €</span><button class="th-choose" data-pick="gold">Choisir</button></th>
              <th scope="col" data-col="platinium"><span class="th-plan" style="--c:#475569"><i></i>Platinium</span><span class="th-tag">Diaspora</span><span class="th-price num" data-base-eur="115">115 €</span><button class="th-choose" data-pick="platinium">Choisir</button></th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Hospitalisation</td><td data-col="bronze"><span class="v-inc">100 %</span> urgence</td><td data-col="silver"><span class="v-inc">100 %</span> urgence</td><td data-col="gold"><span class="v-inc">100 %</span></td><td data-col="platinium"><span class="v-inc">100 %</span> suite VIP</td></tr>
            <tr><td>Plafond annuel par assuré</td><td data-col="bronze" class="num v-strong" data-base-eur="760">760 €</td><td data-col="silver" class="num v-strong" data-base-eur="2290">2 290 €</td><td data-col="gold" class="num v-strong" data-base-eur="5335">5 335 €</td><td data-col="platinium" class="num v-strong" data-base-eur="12200">12 200 €</td></tr>
            <tr><td>Délais de carence</td><td data-col="bronze"><span class="v-inc">0j</span> urgences</td><td data-col="silver"><span class="v-strong">30j</span> soins / <span class="v-strong">90j</span> hospit</td><td data-col="gold"><span class="v-strong">30j</span> / <span class="v-strong">180j</span> dentaire</td><td data-col="platinium"><span class="v-strong">30j</span> / <span class="v-strong">180j</span> évac.</td></tr>
            <tr><td>SAMU &amp; transport sanitaire</td><td data-col="bronze"><span class="v-inc">Urgences</span></td><td data-col="silver"><span class="v-inc">Urgences</span></td><td data-col="gold"><span class="v-inc">Inclus</span></td><td data-col="platinium"><span class="v-inc">Inclus + internat.</span></td></tr>
            <tr><td>Télétriage Lisacare 24/7</td><td data-col="bronze"><span class="v-inc">Inclus</span></td><td data-col="silver"><span class="v-inc">Inclus</span></td><td data-col="gold"><span class="v-inc">Inclus</span></td><td data-col="platinium"><span class="v-inc">Prioritaire</span></td></tr>
            <tr><td>Consultations généralistes</td><td data-col="bronze"><span class="v-no">—</span></td><td data-col="silver"><span class="v-strong">70 %</span></td><td data-col="gold"><span class="v-strong">80 %</span></td><td data-col="platinium"><span class="v-strong">90 %</span></td></tr>
            <tr><td>Spécialistes</td><td data-col="bronze"><span class="v-no">—</span></td><td data-col="silver"><span class="v-strong">60 %</span></td><td data-col="gold"><span class="v-strong">80 %</span></td><td data-col="platinium"><span class="v-strong">90 %</span></td></tr>
            <tr><td>Pharmacie (tiers-payant)</td><td data-col="bronze"><span class="v-strong">Urgences</span></td><td data-col="silver"><span class="v-strong">80 %</span></td><td data-col="gold"><span class="v-inc">100 %</span></td><td data-col="platinium"><span class="v-inc">100 %</span></td></tr>
            <tr><td>Examens &amp; laboratoire</td><td data-col="bronze"><span class="v-no">—</span></td><td data-col="silver"><span class="v-strong">70 %</span></td><td data-col="gold"><span class="v-strong">85 %</span></td><td data-col="platinium"><span class="v-strong">90 %</span></td></tr>
            <tr><td>Maternité</td><td data-col="bronze"><span class="v-no">—</span></td><td data-col="silver"><span class="v-strong">70 %</span></td><td data-col="gold"><span class="v-strong">85 %</span></td><td data-col="platinium"><span class="v-inc">100 %</span></td></tr>
            <tr><td>Optique &amp; dentaire</td><td data-col="bronze"><span class="v-no">—</span></td><td data-col="silver"><span class="v-no">—</span></td><td data-col="gold"><span class="v-inc">Inclus</span></td><td data-col="platinium"><span class="v-inc">Inclus</span></td></tr>
            <tr><td>Bilan de santé annuel</td><td data-col="bronze"><span class="v-no">—</span></td><td data-col="silver"><span class="v-no">—</span></td><td data-col="gold"><span class="v-no">—</span></td><td data-col="platinium"><span class="v-inc">Complet</span></td></tr>
            <tr><td>Lit d'accompagnant</td><td data-col="bronze"><span class="v-no">—</span></td><td data-col="silver"><span class="v-no">—</span></td><td data-col="gold"><span class="v-no">—</span></td><td data-col="platinium"><span class="v-inc">Inclus</span></td></tr>
            <tr><td>Visites Ongwa Seniors</td><td data-col="bronze"><span class="v-strong">Option</span></td><td data-col="silver"><span class="v-strong">Option</span></td><td data-col="gold"><span class="v-strong">-20 %</span></td><td data-col="platinium"><span class="v-inc">2 incluses/mois</span></td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════ ALLIANCE DES SERVICES ═══════════ -->
<section class="sec" id="services">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">03</span>
      <div>
        <p class="eyebrow">L'alliance des services MulemaCare</p>
        <h2>Une mutuelle connectée qui agit, pas seulement qui rembourse.</h2>
        <p class="sec-sub">Deux services partenaires intégrés à votre garantie : la télésanté Lisacare et le soin à domicile Ongwa Senior Care.</p>
      </div>
    </div>
    <div class="ally-grid">
      <article class="ally-card reveal">
        <span class="ally-tag a1"><i data-lucide="message-circle"></i>Lisacare Telehealth</span>
        <h3>Un médecin de garde en ligne 24/7 sur WhatsApp, inclus dans votre mutuelle.</h3>
        <p>Fievre nocturne d'un enfant à Yaoundé pendant que vous dormez à Bruxelles ? Le médecin de garde de Lisacare répond en moyenne en 4 minutes, prescrit et oriente vers la clinique conventionnée la plus proche si nécessaire.</p>
        <div class="lisa-body">
          <div>
            <ul class="ally-feats">
              <li class="strong"><i data-lucide="check"></i>Télétriage et téléconsultation illimités, inclus dès la formule Bronze</li>
              <li><i data-lucide="check"></i>Ordonnances numériques acceptées dans les pharmacies partenaires</li>
              <li><i data-lucide="check"></i>Orientation directe en tiers-payant dans le réseau MulemaCare</li>
              <li><i data-lucide="check"></i>Conseils prévention, carnet de vaccination et rappels de suivi</li>
            </ul>
            <div class="lisa-actions">
              <a class="btn btn-primary" href="https://wa.me/23752112021?text=Bonjour%20Lisacare%2C%20je%20souhaite%20discuter%20avec%20un%20m%C3%A9decin%20de%20garde." target="_blank" rel="noopener"><i data-lucide="message-circle"></i>Ouvrir WhatsApp Lisacare</a>
              <button class="btn btn-ghost" data-open-sub><i data-lucide="badge-check"></i>Adhérer</button>
            </div>
            <p class="lisa-note" style="margin-top:16px"><i data-lucide="clock"></i>Temps de réponse moyen constaté : 4 minutes, de jour comme à 3 h du matin.</p>
          </div>
          <div class="phone" id="phoneMock">
            <div class="phone-scr">
              <div class="ph-head">
                <span class="ph-av">L</span>
                <div><b>Lisacare — Médecin de garde</b><span><i></i>en ligne · 24/7</span></div>
              </div>
              <div class="chat" id="phoneChat"></div>
            </div>
          </div>
        </div>
        <button class="link-arrow" id="waReplay" type="button"><i data-lucide="rotate-ccw"></i>Rejouer la conversation</button>
      </article>
      <article class="ally-card ongwa-card reveal">
        <span class="ally-tag a2"><i data-lucide="heart-pulse"></i>Ongwa Senior Care</span>
        <div class="ongwa-inner">
          <div>
            <h3>Des infirmières à domicile pour vos parents âgés, couplées à votre garantie mutuelle.</h3>
            <p>Vos parents restent chez eux, à Bonamoussadi ou à Cocody. Une infirmière conventionnée Ongwa passe régulièrement : tension, traitement, petite conversation. Vous recevez le compte-rendu sur votre téléphone, où que vous soyez dans le monde.</p>
          </div>
          <div class="visit-report">
            <div class="vr-head"><b>Visite du jour — Mme Ekwalla, 78 ans</b><span class="num">Aujourd'hui · 09h40</span></div>
            <div class="vr-metrics">
              <div class="vr-m"><span>Tension</span><b class="num">13/8</b></div>
              <div class="vr-m"><span>Glycémie</span><b class="num">1,10 g/L</b></div>
              <div class="vr-m"><span>Pouls</span><b class="num">74 bpm</b></div>
            </div>
            <p class="vr-note">« Traitement bien pris, appétit correct. Douleur genou droit en baisse. À revoir dans 15 jours. »</p>
            <span class="vr-stamp"><i data-lucide="shield-check"></i>Prise en charge mutuelle appliquée — 0 F avancé</span>
          </div>
          <div class="ongwa-next">
            <span class="o-ic"><i data-lucide="calendar-check"></i></span>
            <div><b>Planifier une première visite</b><small>Gratuite et sans engagement pour tout adhérent</small></div>
          </div>
          <button class="btn btn-primary btn-block" data-info="ongwa"><i data-lucide="calendar-check"></i>Planifier une visite Ongwa</button>
        </div>
      </article>
    </div>
  </div>
</section>

<!-- ═══════════ RÉSEAU DE SOINS ═══════════ -->
<section class="sec" id="reseau">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">04</span>
      <div>
        <p class="eyebrow">Réseau conventionné</p>
        <h2>Trouvez votre clinique ou pharmacie partenaire.</h2>
        <p class="sec-sub">45+ établissements conventionnés dans 6 pays. Cherchez par ville, quartier ou spécialité — le badge bleu garantit le tiers-payant sans avance de frais.</p>
      </div>
    </div>
    <div class="net-tools reveal">
      <div class="net-search">
        <i data-lucide="search"></i>
        <input type="search" id="netSearch" placeholder="Rechercher un établissement, un quartier, une spécialité…" aria-label="Rechercher un établissement">
      </div>
      <div class="net-filters">
        <div class="chips" id="netCityChips"></div>
        <div class="seg" id="netTypeSeg" role="group" aria-label="Type d'établissement">
          <button type="button" data-t="all" class="on">Tous</button>
          <button type="button" data-t="clinic">Cliniques</button>
          <button type="button" data-t="pharmacy">Pharmacies</button>
          <button type="button" data-t="center">Centres</button>
        </div>
        <label class="tp-switch"><input type="checkbox" id="netTp"><span class="tp-track"></span>Tiers-payant uniquement</label>
      </div>
    </div>
    <span class="net-count reveal" id="netCount"></span>
    <div class="net-list reveal" id="netList"></div>
  </div>
</section>

<!-- ═══════════ TÉMOIGNAGES DIASPORA & FAMILLES AVEC PHOTOS ═══════════ -->
<section class="sec" style="background:#fff;border-top:1px solid var(--line);border-bottom:1px solid var(--line)">
  <div class="wrap">
    <div class="sec-head reveal">
      <span class="sec-index">05</span>
      <div>
        <p class="eyebrow">Avis &amp; Expériences Adhérents</p>
        <h2>La sérénité retrouvée pour plus de 12 400 familles.</h2>
        <p class="sec-sub">De Paris à Douala, de Bruxelles à Abidjan — découvrez pourquoi la diaspora fait confiance à MulemaCare pour protéger ses proches.</p>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:28px">
      
      <div class="reveal" style="background:var(--bg);border:1.5px solid var(--line);border-radius:22px;padding:32px 28px;display:flex;flex-direction:column;justify-content:space-between">
        <div>
          <div style="display:flex;gap:4px;color:var(--gold-600);margin-bottom:14px">
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
          </div>
          <p style="font-size:14.5px;color:var(--ink-2);line-height:1.6;font-style:italic;margin-bottom:24px">
            « Mon père a fait un malaise à Douala. En 15 minutes, il était admis à la Polyclinique Mermoz. La clinique a scanné sa carte CSSA et tout a été pris en charge directement. Fini le stress des transferts Western Union en pleine nuit. »
          </p>
        </div>
        <div style="display:flex;align-items:center;gap:14px">
          <div style="width:50px;height:50px;border-radius:50%;background:linear-gradient(135deg,#064E3B,#0D9488);color:#fff;display:grid;place-items:center;font:700 16px var(--font-b);border:2px solid var(--emerald-500);flex:none;box-shadow:var(--shadow-sm)">SM</div>
          <div>
            <h4 style="font-size:15px;font-weight:700;color:var(--ink);margin:0 0 2px">Sandrine Mbarga</h4>
            <span style="font-size:12.5px;color:var(--ink-3)">Adhérente Silver · Paris (France)</span>
          </div>
        </div>
      </div>

      <div class="reveal" style="background:var(--bg);border:1.5px solid var(--line);border-radius:22px;padding:32px 28px;display:flex;flex-direction:column;justify-content:space-between">
        <div>
          <div style="display:flex;gap:4px;color:var(--gold-600);margin-bottom:14px">
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
          </div>
          <p style="font-size:14.5px;color:var(--ink-2);line-height:1.6;font-style:italic;margin-bottom:24px">
            « Avec la formule Gold et les visites Ongwa, une infirmière passe chaque semaine vérifier la tension et le traitement de ma mère à Cocody. Je reçois les bilans de santé directement sur mon téléphone. C'est une vraie bénédiction. »
          </p>
        </div>
        <div style="display:flex;align-items:center;gap:14px">
          <div style="width:50px;height:50px;border-radius:50%;background:linear-gradient(135deg,#0F766E,#14B8A6);color:#fff;display:grid;place-items:center;font:700 16px var(--font-b);border:2px solid var(--emerald-500);flex:none;box-shadow:var(--shadow-sm)">MK</div>
          <div>
            <h4 style="font-size:15px;font-weight:700;color:var(--ink);margin:0 0 2px">Marc Kouassi</h4>
            <span style="font-size:12.5px;color:var(--ink-3)">Adhérent Gold · Bruxelles (Belgique)</span>
          </div>
        </div>
      </div>

      <div class="reveal" style="background:var(--bg);border:1.5px solid var(--line);border-radius:22px;padding:32px 28px;display:flex;flex-direction:column;justify-content:space-between">
        <div>
          <div style="display:flex;gap:4px;color:var(--gold-600);margin-bottom:14px">
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
            <i data-lucide="star" style="width:16px;height:16px;fill:currentColor"></i>
          </div>
          <p style="font-size:14.5px;color:var(--ink-2);line-height:1.6;font-style:italic;margin-bottom:24px">
            « Le médecin régulateur Lisacare sur WhatsApp m'a répondu à 2h du matin pour une poussée de fièvre de ma fille à Kinshasa. Ordonnance envoyée dans la minute et médicaments retirés sans payer à la pharmacie partenaire. »
          </p>
        </div>
        <div style="display:flex;align-items:center;gap:14px">
          <div style="width:50px;height:50px;border-radius:50%;background:linear-gradient(135deg,#1E293B,#334155);color:#fff;display:grid;place-items:center;font:700 16px var(--font-b);border:2px solid #64748B;flex:none;box-shadow:var(--shadow-sm)">EN</div>
          <div>
            <h4 style="font-size:15px;font-weight:700;color:var(--ink);margin:0 0 2px">Estelle Ngalula</h4>
            <span style="font-size:12.5px;color:var(--ink-3)">Adhérente Silver · Montréal (Canada)</span>
          </div>
        </div>
      </div>

    </div>
  </div>
</section>

<!-- ═══════════ CTA FINAL ═══════════ -->
<section class="cta-final">
  <svg class="cf-guilloche" viewBox="0 0 1200 400" fill="none" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><g stroke="#fff" stroke-opacity=".05"><circle cx="1050" cy="80" r="60"/><circle cx="1050" cy="80" r="120"/><circle cx="1050" cy="80" r="180"/><circle cx="150" cy="360" r="80"/><circle cx="150" cy="360" r="140"/><circle cx="150" cy="360" r="200"/></g></svg>
  <div class="wrap cta-in">
    <h2>Votre famille n'attendra pas votre prochain voyage pour être bien soignée.</h2>
    <p>Adhérez en 2 minutes depuis votre téléphone. Carte digitale et QR code de prise en charge émis immédiatement, efficaces dès demain matin.</p>
    <div class="cta-btns">
      <button class="btn btn-white" data-open-sub><i data-lucide="badge-check"></i>Adhérer maintenant</button>
      <a class="btn btn-outline-w" href="#simulateur"><i data-lucide="heart-pulse"></i>Refaire une simulation</a>
    </div>
    <p class="cta-note"><i data-lucide="shield-check"></i>Paiement sécurisé Stripe, Orange Money et MTN MoMo · Résiliation libre · Agrément CSSA n° 045</p>
  </div>
</section>
