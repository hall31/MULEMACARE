import { afterAll, afterEach, beforeAll } from "vitest";
import { resetDemoStore } from "../../src/mocks/store";
import { server } from "../../src/mocks/node";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(async () => {
  server.resetHandlers();
  server.events.removeAllListeners();
  resetDemoStore();
  if (typeof document !== "undefined") {
    const { cleanup } = await import("@testing-library/react");
    cleanup();
  }
});
afterAll(() => server.close());
