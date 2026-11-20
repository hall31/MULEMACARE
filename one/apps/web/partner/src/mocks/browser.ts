import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

/** Service worker de démonstration : intercepte les appels à l'API (mode mock uniquement). */
export const worker = setupWorker(...handlers);
