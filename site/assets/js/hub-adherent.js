/**
 * Hub adhérent — 5 vues câblées /api/me*
 */
(function () {
  const viewEl = document.getElementById('adh-view');
  const nav = document.querySelectorAll('[data-adh-nav]');
  let member = null;
  let claims = [];
  let coverage = null;
  let network = [];

  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function setNav(v) {
    nav.forEach((b) => b.classList.toggle('on', b.dataset.adhNav === v));
    const u = new URL(location.href);
    u.searchParams.set('v', v);
    history.replaceState({}, '', u);
  }

  async function load() {
    viewEl.innerHTML = '<div class="mc-empty"><span class="mc-spin" style="border-color:#097268;border-top-color:transparent;display:inline-block"></span> Chargement…</div>';
    const me = await MC.api('/api/me');
    if (!me.ok) {
      viewEl.innerHTML = MC.emptyHtml('Session expirée — <a href="/login/adherent">reconnectez-vous</a>');
      return;
    }
    member = me.data.member;
    MC_CSRF = me.data.csrf || MC_CSRF;
    const [c, cov, net] = await Promise.all([
      MC.api('/api/me/claims'),
      MC.api('/api/me/coverage'),
      MC.api('/api/me/network'),
    ]);
    claims = c.data.claims || [];
    coverage = cov.data;
    network = net.data.network || [];
    const v = new URLSearchParams(location.search).get('v') || 'home';
    render(v);
  }

  function render(v) {
    setNav(v);
    if (v === 'claims') return renderClaims();
    if (v === 'coverage') return renderCoverage();
    if (v === 'network') return renderNetwork();
    if (v === 'pay') return renderPay();
    return renderHome();
  }

  function renderHome() {
    const m = member;
    const pct = m.annual_cap ? Math.round((m.consumed_cap / m.annual_cap) * 100) : 0;
    const bens = (m.beneficiaries || []).map((b) => `<tr><td>${esc(b.name)}</td><td>${esc(b.relation)}</td><td>${esc(b.city || m.city)}</td></tr>`).join('') || '<tr><td colspan="3">Titulaire uniquement</td></tr>';
    viewEl.innerHTML = `
      <div class="adh-grid">
        <section class="adh-card">
          <div class="adh-card-head"><h2>Carte CSSA</h2><span class="mc-badge ${m.status==='ACTIVE'?'mc-badge-ok':'mc-badge-pending'}">${esc(m.status)}</span></div>
          <div class="cssa-face">
            <small>Carte CSSA — scan clinique</small>
            <div class="cssa-num">${esc(m.cssa_id)}</div>
            <div><small>NSS-MC · identité à vie</small><b>${esc(m.nss_display || m.nss_id || '—')}</b></div>
            <div><small>Titulaire</small><b>${esc(m.subscriber_name)}</b></div>
            <div><small>Formule (garantie, pas la carte)</small><b>${esc(m.plan_name || m.plan_id)}</b></div>
          </div>
          <div class="adh-actions">
            <a class="mc-btn mc-btn-g mc-btn-sm" href="/carte/${encodeURIComponent(m.cssa_id)}" target="_blank">Vue clinique</a>
            <a class="mc-btn mc-btn-sm" href="/mcare">Ouvrir MCare</a>
            <button type="button" class="mc-btn mc-btn-g mc-btn-sm" id="btnPrint">Attestation</button>
          </div>
          ${m.status==='PENDING_PAYMENT' ? '<p class="adh-warn">Paiement en attente — <button type="button" class="mc-btn mc-btn-sm" id="btnPay">Payer Stripe</button></p>' : ''}
        </section>
        <section class="adh-card">
          <h2>Plafond annuel</h2>
          <div class="gauge"><i style="width:${Math.max(4,pct)}%"></i></div>
          <p class="num">${esc(m.consumed_cap.toLocaleString('fr-FR'))} / ${esc(m.annual_cap.toLocaleString('fr-FR'))} FCFA · restant ${esc(m.remaining_cap.toLocaleString('fr-FR'))}</p>
          <h3 style="margin-top:18px">Bénéficiaires</h3>
          <table class="adh-table"><thead><tr><th>Nom</th><th>Rôle</th><th>Ville</th></tr></thead><tbody>${bens}</tbody></table>
        </section>
      </div>`;
    document.getElementById('btnPrint')?.addEventListener('click', () => window.print());
    document.getElementById('btnPay')?.addEventListener('click', async () => {
      const r = await MC.api('/api/checkout', { method: 'POST', body: { cssa_id: m.cssa_id } });
      if (r.data.checkout_url) location.href = r.data.checkout_url;
      else MC.toast(r.data.error || 'Paiement indisponible', 'err');
    });
  }

  function renderClaims() {
    const rows = claims.map((c) => `
      <tr data-ref="${esc(c.claim_ref)}">
        <td>${esc(c.created_at_fmt || c.created_at)}</td>
        <td>${esc(c.clinic_name)}</td>
        <td>${esc(c.act_type)}</td>
        <td class="num">${Number(c.amount_invoiced||0).toLocaleString('fr-FR')}</td>
        <td><span class="mc-badge ${c.status==='APPROVED'?'mc-badge-ok':c.status==='REJECTED'?'mc-badge-bad':'mc-badge-pending'}">${esc(c.status)}</span></td>
      </tr>`).join('');
    viewEl.innerHTML = `
      <section class="adh-card">
        <div class="adh-card-head"><h2>Sinistres & prises en charge</h2>
          <button type="button" class="mc-btn mc-btn-sm" id="btnDeclare">Déclarer</button>
        </div>
        ${claims.length ? `<table class="adh-table"><thead><tr><th>Date</th><th>Établissement</th><th>Acte</th><th>Montant</th><th>Statut</th></tr></thead><tbody>${rows}</tbody></table>` : MC.emptyHtml('Aucun sinistre — déclarez un soin hors réseau si besoin.')}
      </section>`;
    document.getElementById('btnDeclare')?.addEventListener('click', openDeclare);
  }

  function openDeclare() {
    const bens = (member.beneficiaries || [{ name: member.subscriber_name }])
      .map((b) => `<option>${esc(b.name)}</option>`).join('');
    MC.openModal('Déclarer un sinistre', `
      <div class="mc-field"><label>Type</label><select id="dcType"><option value="consultation">Consultation</option><option value="pharmacie">Pharmacie</option><option value="hospitalisation">Hospitalisation</option><option value="urgence">Urgence</option></select></div>
      <div class="mc-field"><label>Bénéficiaire</label><select id="dcBen">${bens}</select></div>
      <div class="mc-field"><label>Établissement</label><input id="dcClinic" placeholder="Clinique / pharmacie"></div>
      <div class="mc-field"><label>Montant payé (FCFA)</label><input id="dcAmt" type="number" min="1"></div>
      <div class="mc-field"><label>Notes</label><textarea id="dcNotes" rows="2"></textarea></div>
      <button type="button" class="mc-btn" id="dcSubmit">Envoyer pour revue</button>`);
    document.getElementById('dcSubmit').onclick = async () => {
      const amt = Number(document.getElementById('dcAmt').value || 0);
      if (amt < 1) { MC.toast('Montant invalide', 'err'); return; }
      const r = await MC.api('/api/me/claims', {
        method: 'POST',
        body: {
          act_type: document.getElementById('dcType').value,
          beneficiary: document.getElementById('dcBen').value,
          clinic_name: document.getElementById('dcClinic').value || 'Déclaration adhérent',
          amount_invoiced: amt,
          notes: document.getElementById('dcNotes').value,
        },
      });
      if (!r.ok) { MC.toast(r.data.error || 'Échec', 'err'); return; }
      MC.closeModal();
      MC.toast('Déclaration envoyée — revue humaine', 'ok');
      const c = await MC.api('/api/me/claims');
      claims = c.data.claims || [];
      renderClaims();
    };
  }

  function renderCoverage() {
    const caps = coverage?.caps || {};
    const plan = coverage?.plan || {};
    viewEl.innerHTML = `
      <section class="adh-card">
        <h2>Couverture — ${esc(plan.label || coverage?.plan_id || member.plan_id)}</h2>
        <p>Plafond annuel : <b class="num">${Number(caps.annual||0).toLocaleString('fr-FR')} FCFA</b> · consommé ${Number(caps.consumed||0).toLocaleString('fr-FR')} · restant ${Number(caps.remaining||0).toLocaleString('fr-FR')}</p>
        <ul class="adh-list">
          <li>Tiers-payant réseau conventionné</li>
          <li>Carences selon formule (soins / maternité)</li>
          <li>MCare chat famille (si ACTIVE)</li>
        </ul>
      </section>`;
  }

  function renderNetwork() {
    viewEl.innerHTML = `
      <section class="adh-card">
        <div class="adh-card-head"><h2>Réseau de soins</h2>
          <input id="netQ" type="search" placeholder="Clinique, ville…" style="padding:8px 12px;border:1.5px solid var(--line);border-radius:10px;min-width:200px">
        </div>
        <div id="netList"></div>
      </section>`;
    const paint = (q) => {
      const qq = (q || '').toLowerCase();
      const rows = network.filter((n) => !qq || (n.name + n.city).toLowerCase().includes(qq));
      document.getElementById('netList').innerHTML = rows.length
        ? `<table class="adh-table"><thead><tr><th>Établissement</th><th>Ville</th><th>Type</th></tr></thead><tbody>${
            rows.slice(0, 40).map((n) => `<tr><td>${esc(n.name)}</td><td>${esc(n.city)}</td><td>${esc(n.type)}</td></tr>`).join('')
          }</tbody></table>`
        : MC.emptyHtml('Aucun établissement');
    };
    paint('');
    document.getElementById('netQ').oninput = (e) => paint(e.target.value);
  }

  function renderPay() {
    viewEl.innerHTML = `
      <section class="adh-card">
        <h2>Paiements & abonnement</h2>
        <p>Statut : <span class="mc-badge ${member.status==='ACTIVE'?'mc-badge-ok':'mc-badge-pending'}">${esc(member.status)}</span></p>
        <p>Email masqué : ${esc(member.subscriber_email)} · Tél. ${esc(member.subscriber_phone)}</p>
        ${member.status !== 'ACTIVE'
          ? '<button type="button" class="mc-btn" id="btnPay2">Finaliser le paiement Stripe</button>'
          : '<p class="mc-badge mc-badge-ok">Abonnement actif — cotisation gérée via Stripe / Mobile Money.</p>'}
      </section>`;
    document.getElementById('btnPay2')?.addEventListener('click', async () => {
      const r = await MC.api('/api/checkout', { method: 'POST', body: { cssa_id: member.cssa_id } });
      if (r.data.checkout_url) location.href = r.data.checkout_url;
      else MC.toast(r.data.error || 'Indisponible', 'err');
    });
  }

  nav.forEach((b) => b.addEventListener('click', () => render(b.dataset.adhNav)));
  load();
})();
