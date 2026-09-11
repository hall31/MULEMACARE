<?php
declare(strict_types=1);
/** @var string $csrf */
$csrf = $csrf ?? '';
?>
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex,nofollow">
<title>MCare — Chat famille diaspora</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/mulema-tokens.css">
<style>
html,body{height:100%;margin:0}
body{font-family:var(--fb);background:var(--bg);color:var(--ink);display:flex;flex-direction:column}
.mc-head{height:64px;border-bottom:1px solid var(--line);background:#fff;display:flex;align-items:center;gap:12px;padding:0 16px}
.mc-head b{font:800 20px var(--fh)}.mc-head b i{font-style:normal;color:var(--em)}
.mc-head .sp{flex:1}
#mcare-thread{flex:1;overflow:auto;padding:20px 16px;max-width:820px;width:100%;margin:0 auto}
.mc-msg{margin-bottom:14px;max-width:92%}
.mc-msg.user{margin-left:auto}
.mc-msg.user p{background:var(--em);color:#fff;border-radius:14px 14px 4px 14px;padding:12px 14px}
.mc-msg.assistant p{background:#fff;border:1.5px solid var(--line);border-radius:14px 14px 14px 4px;padding:12px 14px}
.mc-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.mc-composer{border-top:1px solid var(--line);background:#fff;padding:12px 16px}
.mc-composer form{max-width:820px;margin:0 auto;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.mc-composer select,.mc-composer input{flex:1;min-width:140px;padding:12px;border:1.5px solid var(--line);border-radius:12px;font:500 14px var(--fb)}
.mc-transmit-bar{margin:8px 0 16px}
</style>
</head>
<body>
<header class="mc-head">
  <b>M<i>Care</i></b>
  <span style="font:600 12px var(--fb);color:var(--ink3)">Chat famille diaspora</span>
  <div class="sp"></div>
  <a class="mc-btn mc-btn-g mc-btn-sm" href="/espace-adherent">Mon espace</a>
  <a class="mc-btn mc-btn-g mc-btn-sm" href="/logout">Déconnexion</a>
</header>
<div id="mcare-thread"></div>
<div class="mc-composer">
  <form id="mcare-form">
    <select id="mcare-ben" aria-label="Bénéficiaire"></select>
    <input id="mcare-input" type="text" placeholder="Ex. Fièvre depuis 2 jours, ou couverture maternité…" autocomplete="off" required>
    <button class="mc-btn" type="submit">Envoyer</button>
  </form>
</div>
<script>window.MC_CSRF = <?= json_encode($csrf) ?>;</script>
<script src="/assets/js/ui-kit.js"></script>
<script src="/assets/js/mcare-chat.js"></script>
</body>
</html>
