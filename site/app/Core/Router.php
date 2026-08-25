<?php
declare(strict_types=1);

namespace App\Core;

/**
 * Routeur ultra-rapide et résilient avec Mappage SEO 301 Permanent pour MulemaCare Health Group
 */
class Router {
    private array $routes = [];

    /**
     * Matrice des 35+ redirections 301 permanentes pour conserver 100% de l'autorité Google (2020 - 2026)
     */
    private const LEGACY_301_MAP = [
        '/accueil'                                => '/',
        '/a-propos-de-nous'                       => '/',
        '/la-mutuelle-sante-particulier'          => '/mutuelle-sante',
        '/assurance-sante-entreprise'             => '/entreprises',
        '/assurance-sante-entreprise/tarifs'      => '/entreprises',
        '/assurance-sante-universelle-afrique'    => '/mutuelle-sante',
        '/assurance-chomage-afrique'              => '/mutuelle-sante',
        '/assurance-chomage-afrique/inscription'  => '/#simulateur',
        '/carte-paiement-sante/carecard'          => '/espace-adherent',
        '/mutuelle-e-sante/tarifs/nos-formules'   => '/#garanties',
        '/diaspora/nouveau'                       => '/#simulateur',
        '/annuaire'                               => '/reseau-soins',
        '/annuaire/inscription'                   => '/#reseau',
        '/medecin/inscription'                    => '/#services',
        '/medecin/tarifs'                         => '/#garanties',
        '/espace-pro'                             => '/entreprises',
        '/inscription'                            => '/#simulateur',
        '/inscription/cssa'                       => '/#simulateur',
        '/contactez-nous'                         => '/#services',
        '/pages/coronavirus'                      => '/#services',
        '/pages/partenaires'                      => '/reseau-soins',
        '/pages/investisseurs'                    => '/entreprises',
        '/pages/pays'                             => '/reseau-soins',
        '/pages/conditions'                       => '/#garanties',
        '/pages/mentions'                         => '/#garanties',
        '/vie-privee'                             => '/#garanties',
        '/assurance-sante/pays/cameroun'          => '/pays/cameroun',
        '/assurance-sante/pays/congordc'          => '/pays/rdc',
        '/assurance-sante/pays/congorepublique'   => '/pays/congo',
        '/assurance-sante/pays/coteivoire'        => '/pays/cote-divoire',
        '/assurance-sante/pays/senegal'           => '/pays/senegal',
        '/assurance-sante/pays/benin'             => '/pays/benin',
        '/assurance-sante/pays/gabon'             => '/pays/gabon',
        '/assurance-sante/pays/madagascar'        => '/pays/madagascar',
        '/assurance-sante/pays/france'            => '/diaspora/france',
        '/assurance-sante/pays/belgique'          => '/diaspora/belgique',
        '/assurance-sante/pays/suisse'            => '/diaspora/suisse',
        '/assurance-sante/pays/allemagne'         => '/diaspora/allemagne',
        '/assurance-sante/pays/canada'            => '/diaspora/canada',
        '/assurance-sante/pays/haiti'             => '/diaspora/haiti',
    ];

    public function get(string $path, array $handler): void {
        $this->addRoute('GET', $path, $handler);
    }

    public function post(string $path, array $handler): void {
        $this->addRoute('POST', $path, $handler);
    }

    private function addRoute(string $method, string $path, array $handler): void {
        $this->routes[] = [
            'method'  => $method,
            'path'    => $path,
            'handler' => $handler,
        ];
    }

    public function dispatch(string $method, string $uri): void {
        if ($method === 'HEAD') {
            $method = 'GET';
        }
        $parsedUri = parse_url($uri, PHP_URL_PATH) ?: '/';
        
        // Retirer le script name s'il est présent
        if (str_starts_with($parsedUri, '/index.php')) {
            $parsedUri = substr($parsedUri, strlen('/index.php')) ?: '/';
        }

        // Retirer les préfixes d'hébergement mutualisé 1&1 IONOS
        $prefixes = [
            '/services/mulemacare/mulemacarev2',
            '/www/services/mulemacare/mulemacarev2',
            '/mulemacarev2',
            '/services/mulemacare/mulemacare',
            '/www/services/mulemacare/mulemacare',
            '/services/mulemacare',
            '/mulemacare'
        ];
        $detectedPrefix = '';
        foreach ($prefixes as $prefix) {
            if (str_starts_with($parsedUri, $prefix)) {
                $detectedPrefix = $prefix;
                $parsedUri = substr($parsedUri, strlen($prefix)) ?: '/';
                break;
            }
        }

        $cleanUri = rtrim($parsedUri, '/');
        if (empty($cleanUri)) {
            $cleanUri = '/';
        }
        if (!str_starts_with($cleanUri, '/')) {
            $cleanUri = '/' . $cleanUri;
        }

        // 1. Contrôle & Exécution des Redirections 301 Legacy SEO
        $lowerUri = strtolower($cleanUri);
        if (isset(self::LEGACY_301_MAP[$lowerUri])) {
            $target = self::LEGACY_301_MAP[$lowerUri];
            if (!empty($detectedPrefix) && !str_starts_with($target, 'http')) {
                $target = rtrim($detectedPrefix, '/') . $target;
            }
            if (!headers_sent()) {
                header('Location: ' . $target, true, 301);
                exit;
            }
        }

        // 2. Traitement des Routes Déclarées
        foreach ($this->routes as $route) {
            if ($route['method'] !== $method) {
                continue;
            }

            // Transformation des paramètres d'URL en regex
            $pattern = preg_replace('#\{([a-zA-Z0-9_]+)\}#', '(?P<$1>[^/]+)', $route['path']);
            $pattern = '#^' . $pattern . '$#';

            if (preg_match($pattern, $cleanUri, $matches)) {
                $params = array_filter($matches, 'is_string', ARRAY_FILTER_USE_KEY);
                [$controllerClass, $action] = $route['handler'];

                if (class_exists($controllerClass)) {
                    $controller = new $controllerClass();
                    if (method_exists($controller, $action)) {
                        if (!headers_sent()) {
                            http_response_code(200);
                        }
                        call_user_func_array([$controller, $action], array_values($params));
                        return;
                    }
                }
            }
        }

        // 404 Fallback
        if (!headers_sent()) {
            http_response_code(404);
        }
        echo '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>Page non trouvée — MulemaCare</title><link rel="stylesheet" href="/"></head><body style="font-family:sans-serif;text-align:center;padding:80px 20px;background:#F8FAFC"><h1>Page introuvable (404)</h1><p>La page demandée n\'existe pas ou a été déplacée.</p><a href="/" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#097268;color:#fff;border-radius:10px;text-decoration:none">Retour à l\'accueil MulemaCare &rarr;</a></body></html>';
    }
}
