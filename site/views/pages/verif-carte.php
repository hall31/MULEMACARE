<!-- ================= PAGE VÉRIFICATION CARTE MUTUELLE CSSA ================= -->
<section style="padding:60px 0;background:#F8FAFC;min-height:70vh">
  <div class="container" style="max-width:680px">
    
    <div style="background:#fff;border-radius:24px;border:1.5px solid var(--line);box-shadow:var(--shadow-lg);overflow:hidden">
      
      <!-- Top Card Banner -->
      <div style="background:linear-gradient(135deg,#064A43,#097268);color:#fff;padding:28px 32px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
          <span style="font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#A7F3D0">CONTRÔLE DE PRISE EN CHARGE MÉDICALE</span>
          <span style="background:#10B981;color:#fff;padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:800">✅ ACTIF</span>
        </div>
        <h1 style="font-size:26px;font-weight:800;color:#fff;margin-bottom:4px">Carte Mutuelle Digitale CSSA</h1>
        <div style="font-family:var(--font-num);font-size:18px;color:#FCD34D;letter-spacing:.08em;font-weight:700">
          N° <?= htmlspecialchars($memberId) ?>
        </div>
      </div>

      <!-- Card Verification Body -->
      <div style="padding:32px">
        <div style="display:grid;gap:18px;margin-bottom:28px">
          
          <div style="background:#F8FAFC;border-radius:12px;padding:16px;display:flex;justify-content:space-between">
            <span style="color:var(--muted);font-size:14px">Titulaire Assuré :</span>
            <strong style="color:var(--ink);font-size:15px"><?= htmlspecialchars($cardData['subscriber_name'] ?? 'Adhérent MulemaCare') ?></strong>
          </div>

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
