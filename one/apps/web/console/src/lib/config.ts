/** Adresse de l'API MulemaCare One (serveur de développement du contrat par défaut). */
export const API_BASE_URL: string = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Mode démonstration : les requêtes sont servies par les mocks MSW issus de specs/openapi.yaml. */
export const API_MOCKING: boolean = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";
