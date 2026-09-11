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
$router->get('/devis/{id}', [HomeController::class, 'devis']);
$router->get('/devis', [HomeController::class, 'devis']);
$router->get('/adhesion', [HomeController::class, 'adhesion']);
$router->get('/souscription', [HomeController::class, 'adhesion']);
$router->get('/borne-clinique', [HomeController::class, 'borneClinique']);
$router->get('/verifier', [HomeController::class, 'borneClinique']);
$router->get('/espace-adherent', [HomeController::class, 'adherent']);
$router->get('/login/adherent', [HomeController::class, 'loginAdherent']);
$router->get('/login/admin', [HomeController::class, 'loginAdmin']);
$router->get('/admin', [HomeController::class, 'admin']);
$router->get('/espace-admin', [HomeController::class, 'admin']);
$router->get('/mcare', [HomeController::class, 'mcare']);
$router->get('/mcare/about', [HomeController::class, 'mcareAbout']);
$router->get('/carte/{memberId}', [HomeController::class, 'carte']);

// Routes SEO & AI Search
$router->get('/sitemap.xml', [HomeController::class, 'sitemap']);
$router->get('/robots.txt', [HomeController::class, 'robots']);
$router->get('/llms.txt', [HomeController::class, 'llmsTxt']);

// Routes API & Tiers-Payant Fast Check
$router->post('/api/quote', [ApiController::class, 'quote']);
$router->post('/api/express', [ApiController::class, 'express']);
$router->post('/api/subscribe', [ApiController::class, 'subscribe']);
$router->post('/api/checkout', [ApiController::class, 'checkout']);
$router->get('/api/verify-card/{code}', [ApiController::class, 'verifyCard']);
$router->get('/api/adherent/lookup', [ApiController::class, 'lookupAdherent']);
$router->post('/api/claim', [ApiController::class, 'createClaim']);
$router->post('/api/admin/payments/confirm', [ApiController::class, 'confirmManualPayment']);
$router->post('/api/admin/toggle-status', [ApiController::class, 'toggleMemberStatus']);
$router->post('/api/webhook', [ApiController::class, 'webhook']);
$router->post('/api/stripe/webhook', [ApiController::class, 'webhook']);
$router->get('/api/os/proposals', [ApiController::class, 'osProposals']);
$router->post('/api/os/proposals/{id}/decide', [ApiController::class, 'osDecideProposal']);

// Auth
use App\Controllers\AuthController;
use App\Controllers\HubApiController;
$router->post('/api/auth/adherent/request', [AuthController::class, 'requestAdherent']);
$router->post('/api/auth/adherent/verify', [AuthController::class, 'verifyAdherent']);
$router->post('/api/auth/admin/login', [AuthController::class, 'loginAdmin']);
$router->post('/api/auth/admin/totp', [AuthController::class, 'verifyAdminTotp']);
$router->post('/api/auth/logout', [AuthController::class, 'logout']);
$router->get('/api/auth/csrf', [AuthController::class, 'csrf']);
$router->get('/logout', [AuthController::class, 'logout']);

// Hub APIs
$router->get('/api/me', [HubApiController::class, 'me']);
$router->get('/api/me/claims', [HubApiController::class, 'myClaims']);
$router->post('/api/me/claims', [HubApiController::class, 'declareClaim']);
$router->get('/api/me/coverage', [HubApiController::class, 'myCoverage']);
$router->get('/api/me/network', [HubApiController::class, 'myNetwork']);
$router->get('/api/admin/hub', [HubApiController::class, 'adminHub']);
$router->post('/api/admin/claims/{ref}/decide', [HubApiController::class, 'decideClaim']);
$router->post('/api/mcare/chat', [HubApiController::class, 'mcareChat']);
$router->post('/api/mcare/transmit', [HubApiController::class, 'mcareTransmit']);
// Dispatch
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$uri = $_SERVER['REQUEST_URI'] ?? '/';

$router->dispatch($method, $uri);
