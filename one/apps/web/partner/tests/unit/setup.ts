import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "../../src/mocks/node";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(async () => {
  server.resetHandlers();
  server.events.removeAllListeners();
  if (typeof document !== "undefined") {
    const { cleanup } = await import("@testing-library/react");
    cleanup();
  }
});
afterAll(() => server.close());
