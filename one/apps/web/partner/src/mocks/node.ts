import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/** Serveur de mocks pour Vitest (mêmes gestionnaires que le navigateur). */
export const server = setupServer(...handlers);
