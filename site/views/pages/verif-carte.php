<!-- ================= PAGE VÉRIFICATION CARTE MUTUELLE CSSA ================= -->
<section style="padding:60px 0;background:#F8FAFC;min-height:70vh">
  <div class="container" style="max-width:680px">
    
    <div style="background:#fff;border-radius:24px;border:1.5px solid var(--line);box-shadow:var(--shadow-lg);overflow:hidden">
      
      <!-- Top Card Banner -->
      <div style="background:linear-gradient(135deg,#064A43,#097268);color:#fff;padding:28px 32px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
          <img src="/assets/img/logofooter.png" alt="MulemaCare" height="28" style="height:28px;width:auto;display:block;filter:brightness(0) invert(1)" onerror="this.onerror=null;this.src='/assets/img/logo.png'">
          <span style="background:#10B981;color:#fff;padding:4px 12px;border-radius:999px;font-size:11.5px;font-weight:800;display:inline-flex;align-items:center;gap:6px">
            <i data-lucide="shield-check" style="width:14px;height:14px"></i> ACTIF
          </span>
        </div>
        <h1 style="font-size:24px;font-weight:800;color:#fff;margin-bottom:4px">Carte Mutuelle Digitale CSSA</h1>
        <div style="font-family:var(--font-num);font-size:18px;color:#FCD34D;letter-spacing:.08em;font-weight:700">
          N° <?= htmlspecialchars($memberId) ?>
        </div>
      </div>

      <!-- Card Verification Body -->
      <div style="padding:32px">
        <div style="display:flex;align-items:center;gap:16px;background:#F8FAFC;border-radius:16px;padding:16px 20px;margin-bottom:20px;border:1px solid #E2E8F0">
          <div style="width:54px;height:54px;border-radius:14px;overflow:hidden;border:2px solid var(--emerald);flex:none;box-shadow:0 4px 10px rgba(0,0,0,.1)">
            <img src="/assets/img/member-avatar.jpg" alt="<?= htmlspecialchars($cardData['subscriber_name'] ?? 'Adhérent') ?>" style="width:100%;height:100%;object-fit:cover;display:block" onerror="this.src='/assets/img/member-photo.jpg'">
          </div>
          <div>
            <span style="color:var(--muted);font-size:12px;text-transform:uppercase;font-weight:700;display:block">Titulaire Assuré</span>
            <strong style="color:var(--ink);font-size:17px"><?= htmlspecialchars($cardData['subscriber_name'] ?? 'Adhérent MulemaCare') ?></strong>
          </div>
        </div>

        <div style="display:grid;gap:14px;margin-bottom:28px">

          <div style="background:#F8FAFC;border-radius:12px;padding:16px;display:flex;justify-content:space-between">
            <span style="color:var(--muted);font-size:14px">Formule de Garantie :</span>
            <strong style="color:var(--primary);font-size:15px"><?= htmlspecialchars($cardData['plan_name'] ?? 'Mulema Silver (Famille)') ?></strong>
          </div>

          <div style="background:#F8FAFC;border-radius:12px;padding:16px;display:flex;justify-content:space-between">
            <span style="color:var(--muted);font-size:14px">Statut Tiers-Payant :</span>
            <strong style="color:#047857;font-size:15px">✅ 100% SANS AVANCE DE FRAIS</strong>
          </div>

          <div style="background:#F8FAFC;border-radius:12px;padding:16px;display:flex;justify-content:space-between">
            <span style="color:var(--muted);font-size:14px">Validité des Droits :</span>
            <strong style="color:var(--ink);font-size:15px">Jusqu'au <?= htmlspecialchars($cardData['valid_until'] ?? date('d/m/Y', strtotime('+1 month'))) ?></strong>
          </div>
        </div>

        <!-- Clinic Instructions -->
        <div style="border-left:4px solid var(--primary);padding:14px 18px;background:#F0FDFA;border-radius:0 12px 12px 0;margin-bottom:28px;font-size:13.5px;color:#065F53;line-height:1.6">
          <strong>Instruction pour la clinique / pharmacie :</strong> Les actes couverts par cette formule doivent être facturés directement à <em>MulemaCare Health Group</em> selon la convention tiers-payant. Aucune caution ne doit être exigée de l'assuré pour les soins garantis.
        </div>

        <div style="display:flex;gap:12px;flex-wrap:wrap">
          <a href="https://wa.me/23752112021?text=<?= rawurlencode('Bonjour, confirmation de prise en charge pour carte #' . $memberId) ?>" target="_blank" rel="noopener" class="btn royal" style="flex:1">
            <i data-lucide="message-circle"></i> Desk Médical WhatsApp
          </a>
          <a href="/" class="btn outline" style="flex:1">
            &larr; Retour à l'accueil
          </a>
        </div>

      </div>
    </div>

  </div>
</section>
