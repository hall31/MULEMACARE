<?php
declare(strict_types=1);

/**
 * Rapprochement en mode observation : MulemaCare contre HealthOS.
 *
 * Pour chaque numéro CSSA de la table de correspondance validée, compare la
 * décision du site et celle de HealthOS, et écrit un rapport. Rien n'est
 * modifié : ni une adhésion, ni un dossier HealthOS.
 *
 *   MULEMACARE_HEALTHOS_BRIDGE_ENABLED=true \
 *   MULEMACARE_HEALTHOS_BRIDGE_MODE=observe \
 *   HEALTHOS_BASE_URL=https://healthos.example.org \
 *   HEALTHOS_PARTNER_API_KEY=... \
 *   HEALTHOS_PILOT_TENANT=mulemacare-pilote \
 *   php site/scripts/healthos_observation_run.php [--json] [--out rapport.json]
 *
 * Sort en 0 quand le rapprochement a pu tourner, même s'il trouve des écarts :
 * trouver un écart est le but. Il sort en 1 quand il n'a pas pu tourner du
 * tout — bridge éteint, mauvais mode, table de correspondance inexploitable.
 */

require __DIR__ . '/../app/autoload.php';

use App\Services\HealthOSClient;
use App\Services\HealthOSIdentityMap;
use App\Services\HealthOSObservation;
use App\Services\MembershipService;

$options = getopt('', ['json', 'out:']);
$asJson = array_key_exists('json', $options);
$outPath = isset($options['out']) ? (string) $options['out'] : null;

$config = require __DIR__ . '/../config.php';

$observation = new HealthOSObservation(
    $config,
    new MembershipService($config),
    new HealthOSClient($config),
    new HealthOSIdentityMap($config)
);

$result = $observation->run();

if ($result['blockers'] !== []) {
    fwrite(STDERR, "Rapprochement impossible :\n");
    foreach ($result['blockers'] as $blocker) {
        fwrite(STDERR, '  - ' . $blocker . "\n");
    }
    exit(1);
}

if ($outPath !== null) {
    file_put_contents($outPath, json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    fwrite(STDERR, 'Rapport écrit : ' . $outPath . "\n");
}

if ($asJson) {
    echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE), "\n";
    exit(0);
}

$labels = [
    HealthOSObservation::VERDICT_MATCH => 'concordants',
    HealthOSObservation::VERDICT_DIVERGENT => 'divergents',
    HealthOSObservation::VERDICT_UNREACHABLE => 'HealthOS injoignable',
    HealthOSObservation::VERDICT_UNMAPPED => 'non rapprochés',
    HealthOSObservation::VERDICT_NOT_A_RECORD => 'adhésion de démonstration, écartée',
    HealthOSObservation::VERDICT_UNKNOWN_TO_SITE => 'inconnus du site',
];

echo "Rapprochement MulemaCare <-> HealthOS (observation, aucune écriture)\n";
echo str_repeat('-', 68), "\n";
foreach ($result['summary'] as $verdict => $count) {
    printf("%-40s %d\n", $labels[$verdict] ?? $verdict, $count);
}
echo "\n";

foreach ($result['reports'] as $report) {
    if ($report['divergences'] === []) {
        continue;
    }
    printf("%s -> %s\n", $report['cssa_number'], (string) $report['patient_id']);
    foreach ($report['divergences'] as $divergence) {
        printf(
            "  %-15s site=%s  healthos=%s\n      %s\n",
            $divergence['field'],
            var_export($divergence['site'], true),
            var_export($divergence['healthos'], true),
            $divergence['explanation']
        );
    }
}

exit(0);
