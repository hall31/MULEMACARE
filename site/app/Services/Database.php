<?php

namespace App\Services;

use PDO;
use PDOException;

class Database
{
    private static ?PDO $pdo = null;
    private static bool $connectionAttempted = false;

    public static function getConnection(): ?PDO
    {
        if (self::$pdo !== null) {
            return self::$pdo;
        }

        if (self::$connectionAttempted) {
            return null;
        }

        self::$connectionAttempted = true;
        $config = require __DIR__ . '/../../config.php';
        $db = $config['db'] ?? [];

        if (empty($db['host']) || empty($db['database'])) {
            return null;
        }

        $dsn = sprintf(
            'mysql:host=%s;port=%s;dbname=%s;charset=%s',
            $db['host'],
            $db['port'] ?? 3306,
            $db['database'],
            $db['charset'] ?? 'utf8mb4'
        );

        try {
            self::$pdo = new PDO($dsn, $db['username'], $db['password'], [
                PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES   => false,
                PDO::ATTR_TIMEOUT            => 3,
            ]);
            return self::$pdo;
        } catch (PDOException $e) {
            error_log('[MulemaCare DB Error] ' . $e->getMessage());
            return null;
        }
    }

    public static function isConnected(): bool
    {
        return self::getConnection() !== null;
    }
}
