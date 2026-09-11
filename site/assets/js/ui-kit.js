/**
 * MulemaCare UI kit — toasts, modal, fetch JSON helpers (FE0)
 */
(function (global) {
  function ensureToasts() {
    let el = document.getElementById('mc-toasts');
    if (!el) {
      el = document.createElement('div');
      el.id = 'mc-toasts';
      el.setAttribute('aria-live', 'polite');
      document.body.appendChild(el);
    }
    return el;
  }

  function toast(message, type) {
    const wrap = ensureToasts();
    const t = document.createElement('div');
    t.className = 'mc-toast ' + (type || '');
    t.textContent = message;
    wrap.appendChild(t);
    setTimeout(() => t.remove(), 4200);
  }

  function ensureModal() {
    let ov = document.getElementById('mc-overlay');
    if (ov) return ov;
    ov = document.createElement('div');
    ov.className = 'mc-overlay';
    ov.id = 'mc-overlay';
    ov.innerHTML = '<div class="mc-modal" role="dialog" aria-modal="true"><div class="mc-modal-h"><h3 id="mc-m-title"></h3><button type="button" class="mc-btn mc-btn-g mc-btn-sm" id="mc-m-close" aria-label="Fermer">✕</button></div><div class="mc-modal-b" id="mc-m-body"></div></div>';
    document.body.appendChild(ov);
    ov.addEventListener('click', (e) => { if (e.target === ov) closeModal(); });
    ov.querySelector('#mc-m-close').addEventListener('click', closeModal);
    return ov;
  }

  function openModal(title, html) {
    const ov = ensureModal();
    ov.querySelector('#mc-m-title').textContent = title;
    ov.querySelector('#mc-m-body').innerHTML = html;
    ov.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    const ov = document.getElementById('mc-overlay');
    if (ov) ov.classList.remove('open');
    document.body.style.overflow = '';
  }

  async function api(url, opts) {
    const csrf = global.MC_CSRF || '';
    const options = Object.assign({ credentials: 'same-origin', headers: {} }, opts || {});
    options.headers = Object.assign({
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrf,
    }, options.headers || {});
    if (options.body && typeof options.body === 'object') {
      if (!options.body.csrf_token) options.body.csrf_token = csrf;
      options.body = JSON.stringify(options.body);
    }
    const res = await fetch(url, options);
    let data = {};
    try { data = await res.json(); } catch (e) { data = {}; }
    return { ok: res.ok, status: res.status, data };
  }

  function emptyHtml(msg) {
    return '<div class="mc-empty">' + (msg || 'Aucune donnée') + '</div>';
  }

  global.MC = { toast, openModal, closeModal, api, emptyHtml };
})(window);
