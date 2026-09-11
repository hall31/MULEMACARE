<?php
declare(strict_types=1);

/**
 * Dry-run / commit de l'export CRM legacy vers le contrat MembershipService.
 *
 *   php site/tools/legacy_ingest.php --file=/chemin/mulemacare-ingest.json
 *   php site/tools/legacy_ingest.php --file=... --commit
 *
 * Jamais d'ACTIVE automatique. --commit écrit un preview horodaté, pas members.json.
 */

$args = [];
foreach (array_slice($argv, 1) as $arg) {
    if (str_starts_with($arg, '--file=')) {
        $args['file'] = substr($arg, 7);
    } elseif ($arg === '--commit') {
        $args['commit'] = true;
    } elseif ($arg === '--dry-run') {
        $args['dry'] = true;
    } elseif ($arg === '--help' || $arg === '-h') {
        fwrite(STDOUT, "Usage: php site/tools/legacy_ingest.php --file=mulemacare-ingest.json [--commit]\n");
        exit(0);
    }
}

$file = $args['file'] ?? '';
if ($file === '' || !is_readable($file)) {
    fwrite(STDERR, "Fichier ingest JSON manquant ou illisible. Passez --file=\n");
    exit(1);
}

$raw = file_get_contents($file);
$payload = json_decode($raw ?: 'null', true);
if (!is_array($payload) || !isset($payload['records']) || !is_array($payload['records'])) {
    fwrite(STDERR, "JSON invalide : attendu { records: [...] }\n");
    exit(1);
}

$allowedPlans = ['bronze', 'silver', 'gold', 'platinium'];
$allowedComp = ['solo', 'couple', 'family'];
$allowedStatus = ['PENDING_REVIEW', 'PENDING_PAYMENT', 'SUSPENDED'];

$ok = 0;
$skip = 0;
$blocked = 0;
$errors = [];
$preview = [];

foreach ($payload['records'] as $i => $row) {
    if (!is_array($row)) {
        $blocked++;
        $errors[] = "ligne $i : pas un objet";
        continue;
    }
    $decision = (string) ($row['decision'] ?? 'pending');
    if ($decision === 'skip') {
        $skip++;
        continue;
    }
    $email = strtolower(trim((string) ($row['subscriber_email'] ?? '')));
    $plan = (string) ($row['plan_id'] ?? '');
    $comp = (string) ($row['composition'] ?? '');
    $status = (string) ($row['status_target'] ?? 'PENDING_REVIEW');
    $flag = (string) ($row['ingest_flag'] ?? '');
    $problems = [];
    if ($email === '' || !str_contains($email, '@')) {
        $problems[] = 'email';
    }
    if (!in_array($plan, $allowedPlans, true)) {
        $problems[] = 'plan_id';
    }
    if (!in_array($comp, $allowedComp, true)) {
        $problems[] = 'composition';
    }
    if ($status === 'ACTIVE') {
        $problems[] = 'ACTIVE interdit à l’ingest (HITL)';
        $status = 'PENDING_REVIEW';
    }
    if (!in_array($status, $allowedStatus, true)) {
        $status = 'PENDING_REVIEW';
    }
    if ($flag === 'blocked' && $decision !== 'approve') {
        $problems[] = 'blocked';
    }
    if ($problems !== []) {
        $blocked++;
        $errors[] = ($row['legacy_user_id'] ?? "ligne $i") . ' : ' . implode(',', $problems);
        continue;
    }
    if ($decision !== 'approve' && $flag !== 'ready') {
        $skip++;
        continue;
    }

    $preview[] = [
        'legacy_user_id'     => $row['legacy_user_id'] ?? null,
        'legacy_unique_id'   => $row['legacy_unique_id'] ?? null,
        'subscriber_name'    => $row['subscriber_name'] ?? '',
        'subscriber_email'   => $email,
        'subscriber_phone'   => $row['subscriber_phone'] ?? '',
        'subscriber_country' => $row['subscriber_country'] ?? '',
        'subscriber_origin'  => $row['subscriber_origin'] ?? 'Diaspora',
        'plan_id'            => $plan,
        'composition'        => $comp,
        'currency'           => $row['currency'] ?? 'XAF',
        'cycle'              => $row['cycle'] ?? 'annual',
        'status'             => $status,
        'force_active'       => false,
        'valid_from'         => $row['valid_from'] ?? null,
        'valid_until'        => $row['valid_until'] ?? null,
        'preserve_carence'   => !empty($row['preserve_carence']),
        'beneficiaries'      => $row['beneficiaries'] ?? [],
        'note'               => $row['note'] ?? '',
    ];
    $ok++;
}

$report = [
    'file'    => $file,
    'ok'      => $ok,
    'skip'    => $skip,
    'blocked' => $blocked,
    'errors'  => array_slice($errors, 0, 40),
];
fwrite(STDOUT, json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE) . PHP_EOL);

if (!empty($args['commit'])) {
    $dir = dirname(__DIR__) . '/data';
    if (!is_dir($dir)) {
        mkdir($dir, 0775, true);
    }
    $out = $dir . '/members.ingest-' . date('Ymd-His') . '.json';
    file_put_contents($out, json_encode($preview, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    fwrite(STDOUT, "Preview écrit : $out\n");
    fwrite(STDOUT, "members.json n'a PAS été modifié. Branche HITL ensuite.\n");
}

exit($blocked > 0 ? 2 : 0);
