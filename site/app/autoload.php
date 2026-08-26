<?php
declare(strict_types=1);

/**
 * Autoloader PSR-4 natif, sans dépendance externe.
 *
 * Il vivait dans `index.php`. Il en sort parce que le front controller n'est
 * plus le seul point d'entrée : le lot d'observation du bridge HealthOS
 * apporte un script d'exécution et une suite de tests, et recopier
 * l'autoloader dans chacun aurait fait diverger trois copies de la même règle.
 */

spl_autoload_register(function (string $class): void {
    $prefix = 'App\\';
    $baseDir = __DIR__ . '/';

    $len = strlen($prefix);
    if (strncmp($prefix, $class, $len) !== 0) {
        return;
    }

    $relativeClass = substr($class, $len);
    $file = $baseDir . str_replace('\\', '/', $relativeClass) . '.php';

    if (file_exists($file)) {
        require $file;
    }
});
