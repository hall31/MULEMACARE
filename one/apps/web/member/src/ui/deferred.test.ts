import { describe, expect, it, vi } from "vitest";
import { createDeferredLoader } from "./deferred";

describe("chargement différé d'un écran secondaire (hors du JavaScript initial)", () => {
  it("un seul chargement, puis disponible tout de suite", async () => {
    const load = vi.fn(async () => "module");
    const loader = createDeferredLoader(load);
    expect(loader.peek()).toBeNull();
    const [a, b] = await Promise.all([loader.get(), loader.get()]);
    expect([a, b]).toEqual(["module", "module"]);
    expect(loader.peek()).toBe("module");
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("hors ligne avant le chargement : l'échec n'est pas gardé, un nouvel essai réussit au retour du réseau", async () => {
    let online = false;
    const load = vi.fn(async () => {
      if (!online) throw new Error("Failed to fetch dynamically imported module");
      return "module";
    });
    const loader = createDeferredLoader(load);
    await expect(loader.get()).rejects.toThrow();
    expect(loader.peek()).toBeNull();
    online = true;
    await expect(loader.get()).resolves.toBe("module");
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("préchargement silencieux, même en échec", async () => {
    const loader = createDeferredLoader(async () => Promise.reject(new Error("x")));
    expect(() => loader.preload()).not.toThrow();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(loader.peek()).toBeNull();
  });
});
