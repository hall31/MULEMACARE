<?php
declare(strict_types=1);
/** @var bool $needsTotp */
/** @var bool $authDebug */
$stepTotp = !empty($needsTotp) || (($_GET['step'] ?? '') === 'totp');
?>
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex,nofollow">
<title>Admin sécurisé — MulemaCare</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--em:#097268;--dark:#0F172A;--ink:#0F172A;--ink3:#64748B;--line:#E2E8F0;--fh:'Outfit',sans-serif;--fb:'Plus Jakarta Sans',sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--fb);min-height:100dvh}
#gate{display:grid;grid-template-columns:1.1fr 1fr;min-height:100dvh}
.g-l{background:var(--dark);color:#fff;padding:52px;display:flex;flex-direction:column;justify-content:space-between}
.g-l h1{font:800 clamp(1.7rem,2.6vw,2.2rem)/1.15 var(--fh);max-width:16ch}
.g-l p{color:#94A3B8;margin-top:14px;max-width:36ch;font-size:14.5px}
.g-r{display:grid;place-items:center;padding:32px;background:#fff}
.card{width:min(390px,100%)}
.card h2{font:800 22px var(--fh);margin-bottom:6px}
.card>p{color:var(--ink3);font-size:14px;margin-bottom:22px}
label{display:block;font:600 12.5px var(--fb);margin:0 0 6px;color:var(--ink3)}
input{width:100%;padding:12px 14px;border:1.5px solid var(--line);border-radius:11px;font:500 14.5px var(--fb);margin-bottom:14px}
.btn{width:100%;padding:12px;border:0;border-radius:11px;background:var(--em);color:#fff;font:700 14px var(--fb);cursor:pointer}
.msg{margin-top:12px;font-size:13px;color:var(--ink3);min-height:1.2em}
.msg.err{color:#B91C1C}.msg.ok{color:var(--em)}
.hint{margin-top:14px;padding:12px;background:#EFF6FF;border:1.5px solid #C7D7FE;border-radius:11px;font-size:12.5px;color:#1E40AF;display:none}
@media(max-width:820px){#gate{grid-template-columns:1fr}.g-l{display:none}}
</style>
</head>
<body>
<div id="gate">
  <div class="g-l">
    <div>
      <b style="font:700 20px var(--fh)">Mulema<em style="font-style:normal;color:#5EEAD4">Care</em></b>
      <span style="display:block;font:600 9.5px var(--fb);letter-spacing:.2em;text-transform:uppercase;color:#64748B;margin-top:4px">Back-office sécurisé</span>
    </div>
    <div>
      <h1>Accès ops avec 2FA obligatoire</h1>
      <p>Argon2id + TOTP. Les actions HITL passent par le serveur — aucun token collé dans le navigateur.</p>
    </div>
    <p style="font-size:12px;opacity:.5">Idle 30 min · absolute 8 h · CSRF · CSP</p>
  </div>
  <div class="g-r">
    <div class="card">
      <h2>Connexion admin</h2>
      <p id="lead"><?= $stepTotp ? 'Validez votre code authenticator' : 'Email ops + mot de passe' ?></p>
      <form id="f-login" style="<?= $stepTotp ? 'display:none' : '' ?>">
        <label>Email</label>
        <input type="email" id="email" autocomplete="username" required>
        <label>Mot de passe</label>
        <input type="password" id="password" autocomplete="current-password" required>
        <button class="btn" type="submit">Continuer</button>
      </form>
      <form id="f-totp" style="<?= $stepTotp ? '' : 'display:none' ?>">
        <label>Code TOTP (6 chiffres)</label>
        <input id="totp" inputmode="numeric" maxlength="6" pattern="\d{6}" required>
        <input type="hidden" id="enroll" value="0">
        <button class="btn" type="submit">Valider 2FA</button>
      </form>
      <div class="hint" id="enrollHint"></div>
      <div class="msg" id="msg"></div>
    </div>
  </div>
</div>
<script>
const msg = document.getElementById('msg');
const debug = <?= !empty($authDebug) ? 'true' : 'false' ?>;
document.getElementById('f-login').addEventListener('submit', async (e) => {
  e.preventDefault();
  msg.textContent = 'Auth…';
  const res = await fetch('/api/auth/admin/login', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      email: document.getElementById('email').value.trim(),
      password: document.getElementById('password').value
    })
  });
  const j = await res.json();
  if (!j.ok) { msg.className='msg err'; msg.textContent = j.error || 'Échec'; return; }
  document.getElementById('f-login').style.display = 'none';
  document.getElementById('f-totp').style.display = 'block';
  document.getElementById('lead').textContent = j.needs_totp_enroll ? 'Enrôlez votre authenticator puis validez' : 'Code TOTP';
  if (j.needs_totp_enroll) {
    document.getElementById('enroll').value = '1';
    const h = document.getElementById('enrollHint');
    h.style.display = 'block';
    h.textContent = 'Scannez : ' + (j.otpauth || '') + (debug && j.totp_secret ? (' · secret=' + j.totp_secret) : '');
  }
  msg.className='msg ok'; msg.textContent = 'Mot de passe OK — 2FA requis';
});
document.getElementById('f-totp').addEventListener('submit', async (e) => {
  e.preventDefault();
  const res = await fetch('/api/auth/admin/totp', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      code: document.getElementById('totp').value.trim(),
      enroll: document.getElementById('enroll').value === '1'
    })
  });
  const j = await res.json();
  if (!j.ok) { msg.className='msg err'; msg.textContent = 'TOTP invalide'; return; }
  location.href = '/espace-admin';
});
</script>
</body>
</html>
