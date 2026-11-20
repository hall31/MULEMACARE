/**
 * Fournisseur d'identité non choisi (PRD §10 Q2) : interface + implémentation de test.
 * Aucune clé ni jeton réel dans le code : l'implémentation de test envoie un jeton
 * factice, accepté par le serveur de mocks Prism et par les tests Playwright.
 */
export interface TokenProvider {
  getToken(): string | null;
}

class TestTokenProvider implements TokenProvider {
  getToken(): string {
    return "jeton-de-test-comptoir";
  }
}

class MissingIdentityProvider implements TokenProvider {
  getToken(): null {
    return null;
  }
}

export const tokenProvider: TokenProvider =
  process.env.NEXT_PUBLIC_MULEMA_AUTH_MODE === "test" ? new TestTokenProvider() : new MissingIdentityProvider();
