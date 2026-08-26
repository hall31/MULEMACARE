<?php
declare(strict_types=1);

/**
 * Lanceur de tests du site MulemaCare — bibliothèque standard uniquement.
 *
 * Le site n'a ni `composer.json`, ni `vendor/`, et la CI ne lui demandait
 * jusqu'ici qu'un `php -l`. Le lot d'observation du bridge HealthOS apporte une
 * logique de décision — rapprochement d'identités, comparaison de droits — dont
 * une erreur se paierait en droits de santé montrés à la mauvaise personne. Un
 * contrôle de syntaxe ne dit rien de ça.
 *
 * Introduire PHPUnit aurait voulu dire introduire Composer, un `vendor/`, un
 * verrou de dépendances et une étape d'installation dans la CI, pour un site
 * qui n'en a aucun. Ce lanceur tient en une page et fait ce qu'il faut :
 * découvrir les classes `*Test.php`, appeler leurs méthodes `test*`, compter.
 *
 *   php site/tests/run.php
 *
 * Sortie 0 si tout passe, 1 sinon.
 */

require __DIR__ . '/../app/autoload.php';

final class AssertionFailed extends RuntimeException
{
}

/** Compare en identité stricte : `0`, `'0'`, `false` et `null` ne sont pas la même chose. */
function assertSame(mixed $expected, mixed $actual, string $message = ''): void
{
    if ($expected !== $actual) {
        throw new AssertionFailed(sprintf(
            "%s\n      attendu : %s\n      obtenu  : %s",
            $message !== '' ? $message : 'Valeurs différentes',
            var_export($expected, true),
            var_export($actual, true)
        ));
    }
}

function assertTrue(bool $condition, string $message = ''): void
{
    assertSame(true, $condition, $message !== '' ? $message : 'Condition fausse');
}

function assertFalse(bool $condition, string $message = ''): void
{
    assertSame(false, $condition, $message !== '' ? $message : 'Condition vraie');
}

function assertContainsString(string $needle, string $haystack, string $message = ''): void
{
    if (!str_contains($haystack, $needle)) {
        throw new AssertionFailed(sprintf(
            "%s\n      introuvable : %s\n      dans        : %s",
            $message !== '' ? $message : 'Fragment absent',
            $needle,
            $haystack
        ));
    }
}

$files = glob(__DIR__ . '/*Test.php') ?: [];
sort($files);
foreach ($files as $file) {
    require $file;
}

$passed = 0;
$failures = [];

foreach (get_declared_classes() as $class) {
    if (!str_ends_with($class, 'Test')) {
        continue;
    }
    $reflection = new ReflectionClass($class);
    if ($reflection->isAbstract() || $reflection->getFileName() === false
        || !str_starts_with((string) $reflection->getFileName(), __DIR__)) {
        continue;
    }
    foreach ($reflection->getMethods(ReflectionMethod::IS_PUBLIC) as $method) {
        if (!str_starts_with($method->getName(), 'test')) {
            continue;
        }
        $instance = $reflection->newInstance();
        try {
            $method->invoke($instance);
            $passed++;
            echo '.';
        } catch (Throwable $error) {
            $failures[] = sprintf("%s::%s\n    %s", $class, $method->getName(), $error->getMessage());
            echo 'F';
        }
    }
}

echo "\n\n";
if ($failures !== []) {
    foreach ($failures as $failure) {
        echo $failure, "\n\n";
    }
    printf("%d réussis, %d échoués\n", $passed, count($failures));
    exit(1);
}

printf("%d réussis\n", $passed);
exit(0);
