import { describe, expect, it, vi } from "vitest";
import { createTracker } from "./track";

type Sent = [string, unknown];

function flushMicrotasks(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("point d'entrée léger de la mesure (client chargé à part, hors du JavaScript initial)", () => {
  it("transmet chaque événement au client une fois chargé, dans l'ordre, sans le charger deux fois", async () => {
    const sent: Sent[] = [];
    const load = vi.fn(async () => ({ track: (name: string, props?: unknown) => void sent.push([name, props]) }));
    const tracker = createTracker(load);
    tracker.track("offline_banner_seen");
    tracker.track("card_presented", { variant: "en_ligne" });
    expect(sent).toEqual([]);
    await flushMicrotasks();
    expect(sent).toEqual([["offline_banner_seen", undefined], ["card_presented", { variant: "en_ligne" }]]);
    tracker.track("claim_tracking_viewed");
    await flushMicrotasks();
    expect(sent.map(([name]) => name)).toEqual(["offline_banner_seen", "card_presented", "claim_tracking_viewed"]);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("client pas encore en cache et réseau coupé : rien n'est perdu (20 au plus), envoyé au retour du réseau", async () => {
    const sent: Sent[] = [];
    let available = false;
    const load = vi.fn(async () => {
      if (!available) throw new Error("hors ligne");
      return { track: (name: string, props?: unknown) => void sent.push([name, props]) };
    });
    const tracker = createTracker(load);
    tracker.track("offline_banner_seen");
    for (let i = 0; i < 30; i += 1) tracker.track("onboarding_started");
    await flushMicrotasks();
    expect(sent).toEqual([]);
    available = true;
    tracker.drain();
    await flushMicrotasks();
    expect(sent).toHaveLength(20);
    expect(sent[0]?.[0]).toBe("offline_banner_seen");
  });

  it("préchargement silencieux, jamais d'exception vers l'écran", async () => {
    const load = vi.fn(async () => Promise.reject(new Error("x")));
    const tracker = createTracker(load);
    expect(() => tracker.preload()).not.toThrow();
    expect(() => tracker.track("onboarding_started")).not.toThrow();
    await flushMicrotasks();
    expect(load).toHaveBeenCalled();
  });
});
