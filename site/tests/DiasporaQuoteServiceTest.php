<?php
declare(strict_types=1);

use App\Services\DiasporaQuoteService;
use App\Services\PricingCatalog;

/**
 * Le moteur de devis dans la grammaire Diaspora v6.1.0.
 *
 * Deux choses comptent ici : que le devis reproduise fidèlement la grille (pas
 * d'arrondi, pas de remise inventée), et que l'éligibilité par âge — absente
 * de l'ancien moteur — refuse exactement ce qu'elle doit refuser, ni plus ni
 * moins, aux bornes.
 */
final class DiasporaQuoteServiceTest
{
    private function service(): DiasporaQuoteService
    {
        return new DiasporaQuoteService(PricingCatalog::load());
    }

    // --------------------------------------------------------------- Europe

    public function testDevisEuropeAnnuelParDefaut(): void
    {
        $q = $this->service()->quoteEurope('premium');
        assertSame('europe', $q['line'], 'Ligne');
        assertSame('annual', $q['cycle'], 'Cycle par défaut');
        assertSame(9999, $q['monthly_cents'], 'Mensuel');
        assertSame(119988, $q['annual_cents'], 'Annuel');
        assertSame(119988, $q['selected_cents'], 'Montant sélectionné en annuel');
        assertSame(80, $q['coverage_rate_pct'], 'Taux');
        assertSame(240000, $q['ceiling_cents'], 'Plafond');
        assertSame('EUR', $q['ceiling_currency'], 'Devise du plafond');
        assertSame('99,99 €', $q['monthly_label'], 'Libellé mensuel');
        assertSame('1 199,88 €', $q['annual_label'], 'Libellé annuel');
    }

    public function testDevisEuropeEnCycleMensuel(): void
    {
        $q = $this->service()->quoteEurope('essentiel', 'monthly');
        assertSame('monthly', $q['cycle'], 'Cycle');
        assertSame(1599, $q['selected_cents'], 'Montant sélectionné en mensuel');
    }

    public function testOffreEuropeInconnueLeve(): void
    {
        try {
            $this->service()->quoteEurope('diamant');
            assertTrue(false, 'Aurait dû lever');
        } catch (InvalidArgumentException $e) {
            assertContainsString('Offre Europe inconnue', $e->getMessage(), 'Message');
            assertContainsString('premium', $e->getMessage(), "Doit lister les offres valides");
        }
    }

    // --------------------------------------------------------- Famille au pays

    public function testDevisFamilleAuPaysNominal(): void
    {
        $q = $this->service()->quoteFamilleAuPays('senior', 'C');
        assertSame('famille_au_pays', $q['line'], 'Ligne');
        assertSame('senior', $q['profile_id'], 'Profil');
        assertSame('C', $q['formula'], 'Formule');
        assertSame(5799, $q['monthly_cents'], 'Mensuel');
        assertSame(69588, $q['annual_cents'], 'Annuel : douze mensualités, sans remise');
        assertSame(80, $q['coverage_rate_pct'], 'Taux');
        assertSame(900000, $q['ceiling_xaf'], 'Plafond FCFA');
        assertSame('45 ans et plus', $q['age_label'], "Libellé d'âge");
    }

    /** La formule est acceptée insensible à la casse, comme le reste du catalogue. */
    public function testLaFormuleEstInsensibleALaCasse(): void
    {
        $q = $this->service()->quoteFamilleAuPays('couple', 'b');
        assertSame('B', $q['formula'], 'Formule normalisée en majuscule');
        assertSame(2599, $q['monthly_cents'], 'Couple B : cotisation');
    }

    public function testProfilInconnuLeve(): void
    {
        try {
            $this->service()->quoteFamilleAuPays('grand-parent', 'A');
            assertTrue(false, 'Aurait dû lever');
        } catch (InvalidArgumentException $e) {
            assertContainsString('Profil « famille au pays » inconnu', $e->getMessage(), 'Message');
        }
    }

    /**
     * Étudiant n'a pas de formule A dans la grille : le moteur doit le dire,
     * pas retomber sur une autre formule ni sur un plan par défaut.
     */
    public function testFormuleNonProposeeLeve(): void
    {
        try {
            $this->service()->quoteFamilleAuPays('etudiant', 'A');
            assertTrue(false, 'Aurait dû lever');
        } catch (InvalidArgumentException $e) {
            assertContainsString('ne propose pas la formule A', $e->getMessage(), 'Message');
            assertContainsString('B, C', $e->getMessage(), 'Doit lister les formules disponibles');
        }
    }

    // ------------------------------------------------------- Éligibilité âge

    public function testAgeNonFourniDonneEligibiliteNulle(): void
    {
        $q = $this->service()->quoteFamilleAuPays('collegien', 'A');
        assertSame(null, $q['age_eligible'], "Pas d'âge fourni : ni éligible ni inéligible");
    }

    /** Collégien : 10–25 ans. Les deux bornes sont incluses. */
    public function testBornesIncluesesCollegien(): void
    {
        $s = $this->service();
        assertTrue($s->quoteFamilleAuPays('collegien', 'A', 'annual', 10)['age_eligible'], '10 ans inclus');
        assertTrue($s->quoteFamilleAuPays('collegien', 'A', 'annual', 25)['age_eligible'], '25 ans inclus');
        assertFalse($s->quoteFamilleAuPays('collegien', 'A', 'annual', 9)['age_eligible'], '9 ans exclu');
        assertFalse($s->quoteFamilleAuPays('collegien', 'A', 'annual', 26)['age_eligible'], '26 ans exclu');
    }

    /** Senior : 45 ans et plus, aucune borne haute — un centenaire doit rester éligible. */
    public function testSeniorSansBorneHaute(): void
    {
        $s = $this->service();
        assertTrue($s->quoteFamilleAuPays('senior', 'A', 'annual', 45)['age_eligible'], '45 ans inclus');
        assertTrue($s->quoteFamilleAuPays('senior', 'A', 'annual', 110)['age_eligible'], 'Aucune borne haute');
        assertFalse($s->quoteFamilleAuPays('senior', 'A', 'annual', 44)['age_eligible'], '44 ans exclu');
    }
}
