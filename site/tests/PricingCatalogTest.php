<?php
declare(strict_types=1);

use App\Services\PricingCatalog;

/**
 * La grille tarifaire Diaspora.
 *
 * Ce qui est vérifié ici n'est pas de la cosmétique. Une cotisation est un
 * engagement opposable : si le simulateur, le devis et le contrat ne disent pas
 * le même montant, c'est la mutuelle qui perd l'arbitrage. Et le plafond
 * actuariel « prime annuelle ≤ 56 % du plafond » n'est pas une préférence :
 * c'est la marge technique du produit. Le profil Collégien A y est exactement,
 * au franc près — donc toute dérive de prix ou de plafond doit faire rougir
 * cette suite, pas passer inaperçue.
 */
final class PricingCatalogTest
{
    private function catalogPath(): string
    {
        return __DIR__ . '/../pricing/diaspora-2026.json';
    }

    private function catalog(): PricingCatalog
    {
        return PricingCatalog::load();
    }

    public function testLaGrilleSeChargeAvecSaVersion(): void
    {
        $c = $this->catalog();
        assertSame('6.1.0', $c->version(), 'Version de grille inattendue');
        assertSame('2026-08-23', $c->effectiveDate(), "Date d'effet inattendue");
    }

    /**
     * La grille en vigueur est validée, et la validation est tracée.
     *
     * Un tarif opposable doit pouvoir dire qui l'a arrêté et quand. Sans cette
     * trace, plus personne ne sait six mois plus tard si les montants publiés
     * ont été validés ou simplement copiés.
     */
    public function testLaGrilleEnVigueurEstValideeEtTracee(): void
    {
        $c = $this->catalog();
        assertFalse($c->isProvisional(), 'La grille v6.1.0 est validée depuis le 26/08/2026');
        assertSame('Dajan', $c->validatedBy(), 'Auteur de la validation');
        assertSame('2026-08-26', $c->validatedAt(), 'Date de la validation');
    }

    /**
     * Le drapeau reste un garde-fou opérant, pas une constante décorative.
     *
     * Une grille future arrivera provisoire ; ce test vérifie sur une grille
     * jetable que le drapeau se lève encore, sinon la protection disparaîtrait
     * le jour où elle redevient utile.
     */
    public function testUneGrilleNonValideeEstSignaleeProvisoire(): void
    {
        $source = json_decode((string) file_get_contents($this->catalogPath()), true);
        $source['status'] = 'provisional';
        $source['status_note'] = 'Validation actuarielle et réglementaire requise avant publication.';
        unset($source['validated_by'], $source['validated_at']);

        $path = sys_get_temp_dir() . '/mulemacare_pricing_' . bin2hex(random_bytes(6)) . '.json';
        file_put_contents($path, json_encode($source, JSON_UNESCAPED_UNICODE));

        try {
            $draft = PricingCatalog::load($path);
            assertTrue($draft->isProvisional(), 'Une grille non validée doit être signalée provisoire');
            assertSame(null, $draft->validatedBy(), 'Pas de validateur sur une grille provisoire');
            assertContainsString('actuarielle', $draft->statusNote(), 'La note doit dire ce qui manque');
        } finally {
            @unlink($path);
        }
    }

    public function testLesQuatreOffresEuropeSontPresentes(): void
    {
        $ids = array_column($this->catalog()->europeOffers(), 'id');
        assertSame(['essentiel', 'famille_plus', 'chronique', 'premium'], $ids, 'Gamme Europe incomplète');
    }

    public function testLesSixProfilsFamilleAuPaysSontPresents(): void
    {
        $ids = array_column($this->catalog()->homeProfiles(), 'id');
        assertSame(
            ['collegien', 'etudiant', 'celibataire', 'couple', 'famille', 'senior'],
            $ids,
            'Gamme famille au pays incomplète'
        );
    }

    /** Un montant de la grille, relu tel quel : si quelqu'un l'édite, il doit le faire exprès. */
    public function testUnTarifEuropeEstFidele(): void
    {
        $premium = $this->catalog()->europeOffer('premium');
        assertSame(9999, $premium['monthly_cents'], 'Premium : cotisation mensuelle');
        assertSame(119988, $premium['annual_cents'], 'Premium : cotisation annuelle');
        assertSame(80, $premium['coverage_rate_pct'], 'Premium : taux de remboursement');
        assertSame(240000, $premium['ceiling_cents'], 'Premium : plafond annuel');
    }

    public function testUnTarifFamilleAuPaysEstFidele(): void
    {
        $tier = $this->catalog()->homeTier('senior', 'C');
        assertSame(5799, $tier['monthly_cents'], 'Senior C : cotisation mensuelle');
        assertSame(80, $tier['coverage_rate_pct'], 'Senior C : taux');
        assertSame(900000, $tier['ceiling_xaf'], 'Senior C : plafond');
    }

    /**
     * Le profil Étudiant n'a pas de formule A.
     *
     * Un appelant qui boucle sur A/B/C en supposant les trois partout produit
     * une cotisation nulle ou une erreur au moment de la souscription.
     */
    public function testEtudiantNaPasDeFormuleA(): void
    {
        $c = $this->catalog();
        assertSame(null, $c->homeTier('etudiant', 'A'), 'Étudiant ne doit pas avoir de formule A');
        assertSame(['B', 'C'], $c->homeFormulas('etudiant'), 'Formules proposées pour Étudiant');
        assertSame(['A', 'B', 'C'], $c->homeFormulas('collegien'), 'Formules proposées pour Collégien');
    }

    public function testUnProfilInconnuNeLevePas(): void
    {
        $c = $this->catalog();
        assertSame(null, $c->homeProfile('inexistant'), 'Profil inconnu');
        assertSame(null, $c->homeTier('inexistant', 'A'), 'Formule d\'un profil inconnu');
        assertSame([], $c->homeFormulas('inexistant'), 'Formules d\'un profil inconnu');
    }

    /**
     * La cotisation annuelle vaut douze mensualités, sans remise.
     *
     * Le moteur de devis appliquait `* 12 * 0.90`. Cette remise de 10 %
     * n'apparaît nulle part dans la grille validée : elle offrait un mois et
     * demi de cotisation à chaque adhérent annuel.
     */
    public function testAucuneRemiseAnnuelle(): void
    {
        $c = $this->catalog();
        assertSame(19188, $c->annualCents(1599), 'Douze mensualités, sans remise');

        foreach ($c->europeOffers() as $offer) {
            assertSame(
                $c->annualCents((int) $offer['monthly_cents']),
                (int) $offer['annual_cents'],
                sprintf('Europe/%s : annuel ≠ 12 × mensuel', $offer['id'])
            );
        }
    }

    /**
     * Le plafond actuariel tient sur toute la gamme famille au pays.
     *
     * C'est le gate qui compte : il échoue si un prix baisse, si un plafond
     * monte, ou si le ratio maximal est desserré sans que personne ne le voie.
     */
    public function testLePlafondActuarielEstRespecte(): void
    {
        $violations = $this->catalog()->invariantViolations();
        assertSame([], $violations, "Grille non conforme :\n      - " . implode("\n      - ", $violations));
    }

    /**
     * Collégien A est saturé : la marge restante est inférieure au franc.
     *
     * Ce test verrouille le cas limite. Sans lui, une correction d'arrondi dans
     * la conversion EUR→FCFA pourrait faire passer ou échouer la gamme entière
     * sans qu'on comprenne pourquoi.
     */
    public function testCollegienAEstExactementAuPlafondActuariel(): void
    {
        $c = $this->catalog();
        $tier = $c->homeTier('collegien', 'A');

        $annualXaf = $c->eurCentsToXaf($c->annualCents((int) $tier['monthly_cents']));
        $maxXaf = (int) ($c->maxPremiumRatioPct() * $tier['ceiling_xaf'] / 100);

        assertSame(19600, $annualXaf, 'Collégien A : prime annuelle en FCFA');
        assertSame(19600, $maxXaf, 'Collégien A : prime maximale admissible');
        assertTrue($annualXaf <= $maxXaf, 'Collégien A doit rester sous le plafond actuariel');
    }

    /**
     * L'aller-retour FCFA → centimes → FCFA dérive, et cette dérive est bornée.
     *
     * Le centime d'euro vaut 6,56 FCFA : l'euro est la monnaie *grossière* du
     * couple. Passer par des centimes perd donc jusqu'à un demi-centime, soit
     * environ 3,3 FCFA. Prétendre à l'exactitude au franc serait faux — et
     * c'est exactement pour cette raison que le plafond actuariel se vérifie en
     * francs entiers plutôt qu'en euros convertis.
     */
    public function testLaDeriveDeConversionResteBornee(): void
    {
        $c = $this->catalog();
        $maxDrift = (int) ceil(PricingCatalog::XAF_PER_EUR / 200); // un demi-centime, arrondi au franc supérieur

        assertSame(4, $maxDrift, 'Borne de dérive attendue pour la parité fixe');

        foreach ([35000, 60000, 120000, 250000, 400000, 750000, 900000] as $xaf) {
            $roundTrip = $c->eurCentsToXaf($c->xafToEurCents($xaf));
            assertTrue(
                abs($roundTrip - $xaf) <= $maxDrift,
                sprintf('Dérive excessive : %d FCFA → %d FCFA (max %d)', $xaf, $roundTrip, $maxDrift)
            );
        }
    }

    public function testLeFormatageEstLisible(): void
    {
        $c = $this->catalog();
        assertSame('15,99 €', $c->formatEur(1599), 'Format euro');
        assertSame('35 000 FCFA', $c->formatXaf(35000), 'Format franc CFA');
    }

    /** Une grille absente doit échouer bruyamment, pas retomber sur des montants par défaut. */
    public function testUneGrilleAbsenteLeve(): void
    {
        try {
            PricingCatalog::load('/introuvable/diaspora-2026.json');
            assertTrue(false, 'Le chargement aurait dû lever');
        } catch (RuntimeException $e) {
            assertContainsString('introuvable', $e->getMessage(), 'Message de chargement');
        }
    }

    /** Une grille tronquée doit lever plutôt que servir une gamme sur deux. */
    public function testUneGrilleIncompleteLeve(): void
    {
        $path = sys_get_temp_dir() . '/mulemacare_pricing_' . bin2hex(random_bytes(6)) . '.json';
        file_put_contents($path, json_encode(['version' => '0', 'lines' => ['europe' => ['offers' => []]]]));

        try {
            PricingCatalog::load($path);
            assertTrue(false, 'Le chargement aurait dû lever');
        } catch (RuntimeException $e) {
            assertContainsString('incomplète', $e->getMessage(), 'Message de structure');
        } finally {
            @unlink($path);
        }
    }
}
