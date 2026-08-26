<?php
declare(strict_types=1);

namespace App\Services;

/**
 * Lecture des droits d'un adhérent dans HealthOS.
 *
 * L'interface n'existe pas pour préparer un second fournisseur — il n'y en aura
 * pas. Elle existe pour que le rapprochement en mode observation soit testable
 * sans réseau : la logique de comparaison est ce qui décidera un jour d'ouvrir
 * ou non le bridge, et elle doit être vérifiée sur des cas choisis, y compris
 * ceux qu'un environnement de recette ne sait pas produire (plafond illimité,
 * gateway injoignable, carence divergente).
 *
 * Seule la lecture y figure. La préautorisation reste sur `HealthOSClient` :
 * ce que le mode observation ne peut pas appeler, il ne doit pas non plus
 * pouvoir le nommer.
 */
interface HealthOSRightsReader
{
    public function isEnabled(): bool;

    /** @return array<string,mixed>|null Les droits, ou `null` si indisponible. */
    public function eligibility(string $healthosPatientId): ?array;
}
