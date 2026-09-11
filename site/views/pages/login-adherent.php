<?php
declare(strict_types=1);
/** @var bool $authDebug */
?>
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex,nofollow">
<title>Connexion adhérent — MulemaCare</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--em:#097268;--em9:#064A43;--ink:#0F172A;--ink3:#64748B;--line:#E2E8F0;--fh:'Outfit',sans-serif;--fb:'Plus Jakarta Sans',sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--fb);color:var(--ink);min-height:100dvh}
#gate{display:grid;grid-template-columns:1.1fr 1fr;min-height:100dvh}
.g-l{background:var(--em9);color:#fff;padding:52px;display:flex;flex-direction:column;justify-content:space-between}
.g-l h1{font:800 clamp(1.7rem,2.6vw,2.3rem)/1.15 var(--fh);max-width:14ch}
.g-l p{color:#8BD9CD;margin-top:14px;max-width:36ch;font-size:14.5px}
.g-r{display:grid;place-items:center;padding:32px;background:#F6F9FB}
.card{width:min(400px,100%);background:#fff;border:1.5px solid var(--line);border-radius:18px;padding:28px}
.card h2{font:800 22px var(--fh);margin-bottom:6px}
.card>p{color:var(--ink3);font-size:14px;margin-bottom:22px}
label{display:block;font:600 12.5px var(--fb);margin:0 0 6px;color:var(--ink3)}
input{width:100%;padding:12px 14px;border:1.5px solid var(--line);border-radius:11px;font:500 14.5px var(--fb);margin-bottom:14px}
.btn{width:100%;padding:12px;border:0;border-radius:11px;background:var(--em);color:#fff;font:700 14px var(--fb);cursor:pointer}
.btn:disabled{opacity:.55}
.msg{margin-top:12px;font-size:13px;color:var(--ink3);min-height:1.2em}
.msg.err{color:#B91C1C}.msg.ok{color:var(--em)}
@media(max-width:820px){#gate{grid-template-columns:1fr}.g-l{display:none}}
</style>
</head>
<body>
<div id="gate">
  <div class="g-l">
    <div>
      <b style="font:700 20px var(--fh)">Mulema<em style="font-style:normal;color:#5EEAD4">Care</em></b>
      <span style="display:block;font:600 9.5px var(--fb);letter-spacing:.2em;text-transform:uppercase;color:#8BD9CD;margin-top:4px">Espace adhérent</span>
    </div>
    <div>
      <h1>Accédez à votre carte CSSA en toute sécurité</h1>
      <p>Un code à usage unique est envoyé à l’email de votre adhésion. Aucun mot de passe à retenir.</p>
    </div>
    <p style="font-size:12px;opacity:.6">Session HttpOnly · pas de JWT navigateur</p>
  </div>
  <div class="g-r">
    <div class="card">
      <h2>Connexion</h2>
      <p>Email d’adhésion ou N° CSSA</p>
      <form id="f-req">
        <label for="identifier">Identifiant</label>
        <input id="identifier" name="identifier" autocomplete="username" required placeholder="vous@email.com ou CSSA-…">
        <button class="btn" type="submit" id="btn-req">Recevoir un code</button>
      </form>
      <form id="f-ver" style="display:none;margin-top:18px">
        <label for="code">Code à 6 chiffres</label>
        <input id="code" name="code" inputmode="numeric" pattern="\d{6}" maxlength="6" required>
        <input type="hidden" id="challenge_id">
        <button class="btn" type="submit">Ouvrir mon espace</button>
      </form>
      <div class="msg" id="msg"></div>
    </div>
  </div>
</div>
<script>
const msg = document.getElementById('msg');
const debug = <?= !empty($authDebug) ? 'true' : 'false' ?>;
document.getElementById('f-req').addEventListener('submit', async (e) => {
  e.preventDefault();
  msg.className = 'msg'; msg.textContent = 'Envoi…';
  const identifier = document.getElementById('identifier').value.trim();
  const res = await fetch('/api/auth/adherent/request', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({identifier})
  });
  const j = await res.json();
  if (!j.ok) { msg.className='msg err'; msg.textContent = j.error || 'Erreur'; return; }
  document.getElementById('f-ver').style.display = 'block';
  document.getElementById('challenge_id').value = j.challenge_id || '';
  msg.className = 'msg ok';
  msg.textContent = j.message + (debug && j.dev_code ? (' · code test: ' + j.dev_code) : '');
});
document.getElementById('f-ver').addEventListener('submit', async (e) => {
  e.preventDefault();
  msg.className = 'msg'; msg.textContent = 'Vérification…';
  const res = await fetch('/api/auth/adherent/verify', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      challenge_id: document.getElementById('challenge_id').value,
      code: document.getElementById('code').value.trim()
    })
  });
  const j = await res.json();
  if (!j.ok) { msg.className='msg err'; msg.textContent = 'Code invalide ou expiré'; return; }
  location.href = '/espace-adherent';
});
</script>
</body>
</html>
