/**
 * Hub admin — shell sidebar + vues API /api/admin/hub
 */
(function () {
  const viewEl = document.getElementById('adm-view');
  const titleEl = document.getElementById('adm-title');
  const nav = document.querySelectorAll('[data-adm-nav]');
  let hub = null;

  const titles = {
    dash: ['Tableau de bord', 'KPIs mutuelle & file HITL'],
    members: ['Adhérents', 'Registre CSSA'],
    payments: ['Paiements', 'File PENDING WhatsApp / Qonto / MoMo'],
    claims: ['Sinistres', 'File revue humaine'],
    hitl: ['ActionCenter', 'Proposals agents OS'],
    network: ['Réseau', 'Établissements conventionnés'],
    plans: ['Formules', 'Lecture catalogue'],
    audit: ['Audit', 'Journal append-only'],
  };

  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  async function load() {
    viewEl.innerHTML = '<div class="mc-empty">Chargement…</div>';
    const r = await MC.api('/api/admin/hub');
    if (!r.ok) {
      viewEl.innerHTML = MC.emptyHtml('Auth requise — <a href="/login/admin">connexion admin</a>');
      return;
    }
    hub = r.data;
    window.MC_CSRF = hub.csrf || window.MC_CSRF;
    const v = new URLSearchParams(location.search).get('v') || 'dash';
    render(v);
  }

  function setNav(v) {
    nav.forEach((b) => b.classList.toggle('on', b.dataset.admNav === v));
    const t = titles[v] || titles.dash;
    if (titleEl) {
      titleEl.querySelector('h1').textContent = t[0];
      titleEl.querySelector('.sub').textContent = t[1];
    }
    const u = new URL(location.href);
    u.searchParams.set('v', v);
    history.replaceState({}, '', u);
    const badge = document.getElementById('clCount');
    if (badge) badge.textContent = String(hub.pending_claims || 0);
    const payBadge = document.getElementById('payCount');
    if (payBadge) payBadge.textContent = String(hub.pending_payments_count || 0);
  }

  function render(v) {
    setNav(v);
    if (v === 'members') return renderMembers();
    if (v === 'payments') return renderPayments();
    if (v === 'claims') return renderClaims();
    if (v === 'hitl') return renderHitl();
    if (v === 'network') return renderNetwork();
    if (v === 'plans') return renderPlans();
    if (v === 'audit') return renderAudit();
    return renderDash();
  }

  function renderDash() {
    const s = hub.stats || {};
    viewEl.innerHTML = `
      <div class="adm-kpis">
        <div class="adm-kpi"><span>Adhérents actifs</span><b class="num">${esc(s.active_subscribers)}</b></div>
        <div class="adm-kpi"><span>ARR</span><b>${esc(s.arr_eur)}</b></div>
        <div class="adm-kpi"><span>Paiements pending</span><b class="num">${esc(hub.pending_payments_count)}</b></div>
        <div class="adm-kpi"><span>Sinistres pending</span><b class="num">${esc(hub.pending_claims)}</b></div>
      </div>
      <section class="adm-card"><p>Ops : <b>${esc(hub.ops_email)}</b> · Tarif v${esc(hub.tariff_version || '—')} · HITL sans JWT navigateur.</p>
        <button type="button" class="mc-btn mc-btn-sm" data-go="payments">File paiements</button>
        <button type="button" class="mc-btn mc-btn-g mc-btn-sm" data-go="claims" style="margin-left:8px">File sinistres</button>
      </section>`;
    viewEl.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', (e) => render(e.currentTarget.dataset.go)));
  }

  function renderPayments() {
    const rows = (hub.pending_payments || []).map((p) => `
      <tr>
        <td><b>${esc(p.cssa_id)}</b><br><small>${esc(p.nss_display || '')}</small></td>
        <td>${esc(p.subscriber_name)}<br><small>${esc(p.subscriber_phone)}</small></td>
        <td><span class="mc-badge">${esc(p.payment_channel || p.payment_method)}</span></td>
        <td class="num">${esc(p.amount_due_label)}</td>
        <td>
          <button type="button" class="mc-btn mc-btn-sm btn-pay-ok" data-cssa="${esc(p.cssa_id)}" data-ch="${esc(p.payment_method)}">Confirmer paiement</button>
          ${p.whatsapp_url ? `<a class="mc-btn mc-btn-g mc-btn-sm" href="${esc(p.whatsapp_url)}" target="_blank" rel="noopener">WA</a>` : ''}
        </td>
      </tr>`).join('');
    viewEl.innerHTML = `<section class="adm-card">
      <p>Clients déjà enregistrés (PENDING). Confirmez uniquement après preuve Stripe webhook, virement Qonto ou MoMo.</p>
      ${(hub.pending_payments||[]).length
        ? `<table class="adm-table"><thead><tr><th>CSSA</th><th>Client</th><th>Canal</th><th>Montant</th><th>HITL</th></tr></thead><tbody>${rows}</tbody></table>`
        : MC.emptyHtml('Aucun paiement en attente')}
    </section>`;
    viewEl.querySelectorAll('.btn-pay-ok').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const ref = window.prompt('Référence paiement (MoMo / virement) — optionnel') || '';
        const r = await MC.api('/api/admin/payments/confirm', {
          method: 'POST',
          body: { cssa_id: btn.dataset.cssa, channel: btn.dataset.ch, payment_ref: ref },
        });
        if (r.data.success) { MC.toast('Carte ACTIVE', 'ok'); load(); }
        else MC.toast(r.data.error || 'Échec', 'err');
      });
    });
  }

  function renderMembers() {
    const rows = (hub.members || []).map((m) => `
      <tr>
        <td><b>${esc(m.cssa_id)}</b></td>
        <td class="num">${esc(m.nss_display || m.nss_id || '—')}</td>
        <td>${esc(m.subscriber_name)}<br><small>${esc(m.subscriber_email)}</small></td>
        <td><span class="mc-badge">${esc(m.plan_name || m.plan_id)}</span></td>
        <td><span class="mc-badge ${m.status==='ACTIVE'?'mc-badge-ok':'mc-badge-pending'}">${esc(m.status)}</span></td>
        <td>
          <button type="button" class="mc-btn mc-btn-g mc-btn-sm btn-toggle" data-cssa="${esc(m.cssa_id)}" data-st="${esc(m.status)}">${m.status==='ACTIVE'?'Suspendre':'Activer'}</button>
        </td>
      </tr>`).join('');
    viewEl.innerHTML = `<section class="adm-card">
      <input id="mQ" type="search" placeholder="Filtrer…" style="margin-bottom:12px;padding:8px 12px;border:1.5px solid #334155;border-radius:10px;background:#0F172A;color:#fff;width:min(320px,100%)">
      ${(hub.members||[]).length ? `<table class="adm-table" id="mTable"><thead><tr><th>Carte CSSA</th><th>NSS-MC</th><th>Souscripteur</th><th>Formule</th><th>Statut</th><th></th></tr></thead><tbody>${rows}</tbody></table>` : MC.emptyHtml('Aucun adhérent')}
    </section>`;
    document.getElementById('mQ')?.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll('#mTable tbody tr').forEach((tr) => {
        tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    });
    viewEl.querySelectorAll('.btn-toggle').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const next = btn.dataset.st === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
        const r = await MC.api('/api/admin/toggle-status', {
          method: 'POST',
          body: { cssa_id: btn.dataset.cssa, status: next },
        });
        if (r.data.success) { MC.toast('Statut → ' + next, 'ok'); load(); }
        else MC.toast(r.data.error || 'Échec', 'err');
      });
    });
  }

  function renderClaims() {
    const rows = (hub.claims || []).map((c) => `
      <tr>
        <td>${esc(c.claim_ref)}</td>
        <td>${esc(c.cssa_id)}</td>
        <td>${esc(c.clinic_name)}</td>
        <td class="num">${Number(c.amount_invoiced||0).toLocaleString('fr-FR')}</td>
        <td><span class="mc-badge ${c.status==='APPROVED'?'mc-badge-ok':c.status==='REJECTED'?'mc-badge-bad':'mc-badge-pending'}">${esc(c.status)}</span></td>
        <td>
          ${c.status==='PENDING_REVIEW' ? `
            <button type="button" class="mc-btn mc-btn-sm btn-c" data-ref="${esc(c.claim_ref)}" data-d="approved">Valider</button>
            <button type="button" class="mc-btn mc-btn-g mc-btn-sm btn-c" data-ref="${esc(c.claim_ref)}" data-d="info">Pièces</button>
            <button type="button" class="mc-btn mc-btn-d mc-btn-sm btn-c" data-ref="${esc(c.claim_ref)}" data-d="rejected">Refuser</button>
          ` : '—'}
        </td>
      </tr>`).join('');
    viewEl.innerHTML = `<section class="adm-card">
      ${(hub.claims||[]).length ? `<table class="adm-table"><thead><tr><th>Réf</th><th>CSSA</th><th>Clinique</th><th>Montant</th><th>Statut</th><th>HITL</th></tr></thead><tbody>${rows}</tbody></table>` : MC.emptyHtml('Aucun sinistre')}
    </section>`;
    viewEl.querySelectorAll('.btn-c').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const r = await MC.api('/api/admin/claims/' + encodeURIComponent(btn.dataset.ref) + '/decide', {
          method: 'POST',
          body: { decision: btn.dataset.d },
        });
        if (r.ok) { MC.toast('Décision enregistrée', 'ok'); load(); }
        else MC.toast(r.data.error || 'Échec', 'err');
      });
    });
  }

  async function renderHitl() {
    viewEl.innerHTML = '<section class="adm-card"><p>Chargement ActionCenter…</p></section>';
    const r = await MC.api('/api/os/proposals?status=pending');
    const rows = r.data.proposals || [];
    viewEl.innerHTML = `<section class="adm-card">
      <div class="adh-card-head"><h2>Proposals pending</h2><button type="button" class="mc-btn mc-btn-g mc-btn-sm" id="hitlRef">Rafraîchir</button></div>
      ${rows.length ? `<table class="adm-table"><thead><tr><th>Agent</th><th>Action</th><th>CSSA</th><th>Résumé</th><th></th></tr></thead><tbody>${
        rows.map((p) => `<tr>
          <td>${esc(p.agent_name)}</td><td>${esc(p.action_type)}</td><td>${esc(p.cssa_id)}</td><td>${esc((p.summary||'').slice(0,80))}</td>
          <td>
            <button type="button" class="mc-btn mc-btn-sm hitl-d" data-id="${esc(p.id)}" data-d="approved">Approve</button>
            <button type="button" class="mc-btn mc-btn-d mc-btn-sm hitl-d" data-id="${esc(p.id)}" data-d="rejected">Reject</button>
          </td></tr>`).join('')
      }</tbody></table>` : MC.emptyHtml(r.data.error || 'File vide ou OS désactivé')}
    </section>`;
    document.getElementById('hitlRef')?.addEventListener('click', () => renderHitl());
    viewEl.querySelectorAll('.hitl-d').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const res = await MC.api('/api/os/proposals/' + btn.dataset.id + '/decide', {
          method: 'POST',
          body: { decision: btn.dataset.d, note: 'admin hub' },
        });
        if (res.ok || res.data.proposal) { MC.toast('OK', 'ok'); renderHitl(); }
        else MC.toast(res.data.error || 'Échec', 'err');
      });
    });
  }

  function renderNetwork() {
    const rows = (hub.network || []).slice(0, 50).map((n) =>
      `<tr><td>${esc(n.name)}</td><td>${esc(n.city)}</td><td>${esc(n.type)}</td></tr>`).join('');
    viewEl.innerHTML = `<section class="adm-card"><table class="adm-table"><thead><tr><th>Nom</th><th>Ville</th><th>Type</th></tr></thead><tbody>${rows}</tbody></table></section>`;
  }

  function renderPlans() {
    const plans = hub.plans || {};
    const rows = Object.entries(plans).map(([id, p]) =>
      `<tr><td><b>${esc(id)}</b></td><td>${esc(p.label || p.name || '')}</td><td>${esc(JSON.stringify(p.pricing || p.price || {}).slice(0, 80))}</td></tr>`
    ).join('');
    viewEl.innerHTML = `<section class="adm-card"><p>Formules = garanties (plafond / tarif). Ce n’est pas la carte CSSA, ni le NSS-MC.</p><table class="adm-table"><thead><tr><th>ID</th><th>Label</th><th>Pricing</th></tr></thead><tbody>${rows}</tbody></table></section>`;
  }

  function renderAudit() {
    const rows = (hub.audit || []).map((e) =>
      `<tr><td>${esc(e.ts)}</td><td>${esc(e.action)}</td><td>${esc(e.actor)}</td><td>${esc(e.cssa_id || '—')}</td></tr>`
    ).join('');
    viewEl.innerHTML = `<section class="adm-card">${rows ? `<table class="adm-table"><thead><tr><th>TS</th><th>Action</th><th>Acteur</th><th>CSSA</th></tr></thead><tbody>${rows}</tbody></table>` : MC.emptyHtml('Journal vide')}</section>`;
  }

  nav.forEach((b) => b.addEventListener('click', () => render(b.dataset.admNav)));
  load();
})();
