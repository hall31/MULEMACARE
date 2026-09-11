<?php
declare(strict_types=1);

namespace App\Services;

/**
 * Journal d'audit append-only (JSONL).
 */
final class AuditService
{
    private string $path;

    public function __construct(array $config)
    {
        $dataDir = rtrim((string) ($config['data_dir'] ?: (__DIR__ . '/../../data')), '/');
        if (!is_dir($dataDir)) {
            mkdir($dataDir, 0775, true);
        }
        $this->path = $dataDir . '/audit.jsonl';
    }

    /** @param array<string,mixed> $meta */
    public function record(string $actor, string $action, ?string $cssaId = null, array $meta = []): void
    {
        $row = [
            'ts' => gmdate('c'),
            'actor' => $actor,
            'action' => $action,
            'cssa_id' => $cssaId,
            'ip' => (string) ($_SERVER['REMOTE_ADDR'] ?? ''),
            'meta' => $meta,
        ];
        file_put_contents($this->path, json_encode($row, JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND | LOCK_EX);
    }

    /** @return list<array<string,mixed>> */
    public function tail(int $limit = 100): array
    {
        if (!is_file($this->path)) {
            return [];
        }
        $lines = file($this->path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [];
        $slice = array_slice($lines, -$limit);
        $out = [];
        foreach ($slice as $line) {
            $j = json_decode($line, true);
            if (is_array($j)) {
                $out[] = $j;
            }
        }
        return array_reverse($out);
    }
}
