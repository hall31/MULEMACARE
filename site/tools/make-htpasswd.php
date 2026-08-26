<?php
declare(strict_types=1);

/**
 * Génère le fichier `.htpasswd` qui ferme les surfaces d'administration.
 *
 * Le fichier lui-même n'est pas versionné : c'est une empreinte de mot de passe
 * de production. Ce script l'est, pour que la fermeture soit reproductible sans
 * que personne n'ait à se souvenir de la commande.
 *
 *   php site/tools/make-htpasswd.php <utilisateur> [mot-de-passe]
 *
 * Sans mot de passe, un mot de passe fort est tiré au sort et affiché une seule
 * fois. bcrypt est reconnu par Apache 2.4 ; `crypt()` historique ne l'est plus
 * partout et MD5 Apache ne vaut rien.
 */

$user = $argv[1] ?? '';
if ($user === '' || !preg_match('/^[A-Za-z0-9._-]{2,32}$/', $user)) {
    fwrite(STDERR, "Usage : php site/tools/make-htpasswd.php <utilisateur> [mot-de-passe]\n");
    exit(2);
}

$password = $argv[2] ?? null;
$generated = false;

if ($password === null || $password === '') {
    // 24 caractères sans ambiguïté visuelle : ni 0/O, ni 1/l/I.
    $alphabet = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    $password = '';
    for ($i = 0; $i < 24; $i++) {
        $password .= $alphabet[random_int(0, strlen($alphabet) - 1)];
    }
    $generated = true;
}

$hash = password_hash($password, PASSWORD_BCRYPT);
if (!is_string($hash)) {
    fwrite(STDERR, "Échec du hachage.\n");
    exit(1);
}

$target = dirname(__DIR__) . '/.htpasswd';
if (file_put_contents($target, $user . ':' . $hash . "\n", LOCK_EX) === false) {
    fwrite(STDERR, "Écriture impossible : {$target}\n");
    exit(1);
}
chmod($target, 0640);

echo "Écrit : {$target}\n";
echo "Utilisateur : {$user}\n";
if ($generated) {
    echo "Mot de passe : {$password}\n";
    echo "\nIl n'est pas stocké en clair : notez-le maintenant.\n";
}
