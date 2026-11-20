import { QueryCache, QueryClient } from "@tanstack/react-query";
import { isAccessDenied } from "@/api/errors";

/**
 * Client de requêtes de l'espace adhérent. Refus d'accès (session expirée, carte révoquée,
 * 401/403/404) : toutes les données gardées en mémoire sont oubliées et les écrans ouverts les
 * redemandent (et affichent alors l'erreur avec son code) ; jamais une donnée d'avant le refus
 * laissée à l'écran. Seules les requêtes qui ont des données sont réinitialisées : pas de boucle
 * quand la nouvelle demande est refusée à son tour.
 */
export function createMemberQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        if (isAccessDenied(error)) void client.resetQueries({ predicate: (query) => query.state.data !== undefined });
      },
    }),
    defaultOptions: {
      // L'espace gère lui-même le hors ligne (carte en cache, erreurs E-NET-xx) : pas de pause silencieuse.
      queries: { networkMode: "always", retry: false, refetchOnWindowFocus: false, staleTime: 60_000 },
      mutations: { networkMode: "always", retry: false },
    },
  });
  return client;
}
