<?php
declare(strict_types=1);

/**
 * MulemaCare Health Group — Front Controller & Routeur PSR-4
 */

if (!headers_sent()) {
    http_response_code(200);
}

// Autoloader PSR-4 natif sans dépendance externe
spl_autoload_register(function (string $class) {
    $prefix = 'App\\';
    $baseDir = __DIR__ . '/app/';

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

use App\Core\Router;
use App\Controllers\HomeController;
use App\Controllers\ApiController;

$router = new Router();

// Routes Frontend & Pages
$router->get('/', [HomeController::class, 'index']);
$router->get('/mutuelle-sante', [HomeController::class, 'mutuelle']);
$router->get('/entreprises', [HomeController::class, 'entreprises']);
$router->get('/reseau-soins', [HomeController::class, 'reseau']);
$router->get('/annuaire', [HomeController::class, 'reseau']);
$router->get('/partenaires', [HomeController::class, 'partenaires']);
$router->get('/devenir-partenaire', [HomeController::class, 'partenaires']);
$router->get('/pays/{slug}', [HomeController::class, 'pays']);
$router->get('/diaspora/{slug}', [HomeController::class, 'diaspora']);
$router->get('/espace-adherent', [HomeController::class, 'adherent']);
$router->get('/admin', [HomeController::class, 'admin']);
$router->get('/carte/{memberId}', [HomeController::class, 'carte']);

// Routes SEO & AI Search
$router->get('/sitemap.xml', [HomeController::class, 'sitemap']);
$router->get('/robots.txt', [HomeController::class, 'robots']);
$router->get('/llms.txt', [HomeController::class, 'llmsTxt']);

// Routes API & Tiers-Payant Fast Check
$router->post('/api/quote', [ApiController::class, 'quote']);
$router->post('/api/subscribe', [ApiController::class, 'subscribe']);
$router->get('/api/verify-card/{code}', [ApiController::class, 'verifyCard']);
$router->post('/api/webhook', [ApiController::class, 'webhook']);

// Dispatch
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$uri = $_SERVER['REQUEST_URI'] ?? '/';

$router->dispatch($method, $uri);
