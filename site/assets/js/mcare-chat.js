/**
 * MCare chat — FE3
 */
(function () {
  const thread = document.getElementById('mcare-thread');
  const form = document.getElementById('mcare-form');
  const input = document.getElementById('mcare-input');
  const ben = document.getElementById('mcare-ben');
  let conversationId = null;
  let member = null;

  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function bubble(role, html, tags) {
    const div = document.createElement('div');
    div.className = 'mc-msg ' + role;
    div.innerHTML = html + (tags && tags.length
      ? `<div class="mc-tags">${tags.map((t) => `<span class="mc-badge mc-badge-warn">${esc(t)}</span>`).join('')}</div>`
      : '');
    thread.appendChild(div);
    thread.scrollTop = thread.scrollHeight;
  }

  async function boot() {
    const me = await MC.api('/api/me');
    if (!me.ok) {
      thread.innerHTML = MC.emptyHtml('Connectez-vous — <a href="/login/adherent">espace adhérent</a>');
      form.style.display = 'none';
      return;
    }
    member = me.data.member;
    window.MC_CSRF = me.data.csrf || window.MC_CSRF;
    if (member.status !== 'ACTIVE') {
      bubble('assistant', '<p>MCare Family nécessite une carte <b>ACTIVE</b> (paiement Stripe confirmé).</p><p><a class="mc-btn mc-btn-sm" href="/espace-adherent?v=pay">Finaliser le paiement</a></p>');
      form.style.display = 'none';
      return;
    }
    const opts = (member.beneficiaries || [{ name: member.subscriber_name }])
      .map((b) => `<option>${esc(b.name)}</option>`).join('');
    ben.innerHTML = opts;
    bubble('assistant', `<p>Bonjour — je suis <b>MCare</b>. Posez une question sur la couverture, le réseau, la carte CSSA, ou décrivez des symptômes pour une orientation (jamais un diagnostic final).</p>`, ['IA', 'Hypothèses non validées']);
  }

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    bubble('user', `<p>${esc(message)}</p>`);
    input.value = '';
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    const r = await MC.api('/api/mcare/chat', {
      method: 'POST',
      body: {
        message,
        beneficiary_name: ben.value,
        conversation_id: conversationId,
      },
    });
    btn.disabled = false;
    if (!r.ok) {
      MC.toast(r.data.error || 'MCare indisponible', 'err');
      bubble('assistant', `<p>Erreur : ${esc(r.data.error || r.status)}</p>`);
      return;
    }
    conversationId = r.data.conversation_id || conversationId;
    const tags = r.data.tags || (r.data.clin_card && r.data.clin_card.tags) || ['IA', 'Hypothèses non validées'];
    bubble('assistant', `<p>${esc(r.data.reply || '')}</p>`, tags);
    if (r.data.intent === 'symptoms' || (tags || []).includes('IA')) {
      const bar = document.createElement('div');
      bar.className = 'mc-transmit-bar';
      bar.innerHTML = '<button type="button" class="mc-btn mc-btn-sm" id="btnTx">Transmettre au médecin (HITL)</button>';
      thread.appendChild(bar);
      document.getElementById('btnTx').onclick = async () => {
        const tx = await MC.api('/api/mcare/transmit', {
          method: 'POST',
          body: { conversation_id: conversationId },
        });
        if (tx.ok) MC.toast(tx.data.message || 'Transmission envoyée', 'ok');
        else MC.toast(tx.data.error || 'Quota / erreur', 'err');
        bar.remove();
      };
    }
  });

  boot();
})();
