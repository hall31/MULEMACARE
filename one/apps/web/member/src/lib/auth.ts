/**
 * Fournisseur d'identité non choisi (PRD §10 Q2) : interface + implémentation de test, comme le
 * comptoir. Aucune clé ni jeton réel dans le code : l'implémentation de test envoie un jeton
 * factice, accepté par le serveur de mocks Prism et par les tests Playwright. Sans fournisseur,
 * l'API répond AUTH-01 et l'espace l'affiche avec son code.
 *
 * La page publique du lien de paiement n'utilise jamais ce fournisseur (opération `security: []`).
 */
export interface TokenProvider {
  getToken(): string | null;
}

class TestTokenProvider implements TokenProvider {
  getToken(): string {
    return "jeton-de-test-adherent";
  }
}

class MissingIdentityProvider implements TokenProvider {
  getToken(): null {
    return null;
  }
}

export const tokenProvider: TokenProvider =
  process.env.NEXT_PUBLIC_MULEMA_AUTH_MODE === "test" ? new TestTokenProvider() : new MissingIdentityProvider();
