import { describe, expect, it } from "vitest";
import { ApiProblem, NetworkUnavailable } from "@/api/client";
import { card, claims } from "@/test/fixtures";
import { createMemberQueryClient } from "./query-client";

function problem(status: number, code: "AUTH-01" | "NOT-01" | "SYS-01"): ApiProblem {
  return new ApiProblem(status, { code, message: "", action: "", request_id: "req" });
}

describe("mémoire des requêtes après un refus d'accès", () => {
  it("session expirée : plus aucune donnée de l'adhérent gardée en mémoire (carte, soins…)", async () => {
    const client = createMemberQueryClient();
    client.setQueryData(["card", "self"], card);
    client.setQueryData(["claims"], { pages: [{ items: claims, page: { next_cursor: null } }], pageParams: [null] });
    await client.fetchQuery({ queryKey: ["contributions"], queryFn: () => Promise.reject(problem(401, "AUTH-01")) }).catch(() => undefined);
    await expect.poll(() => [client.getQueryData(["card", "self"]), client.getQueryData(["claims"])]).toEqual([undefined, undefined]);
  });

  it("carte révoquée (404 NOT-01) : idem", async () => {
    const client = createMemberQueryClient();
    client.setQueryData(["claims"], { pages: [] });
    await client.fetchQuery({ queryKey: ["card", "self"], queryFn: () => Promise.reject(problem(404, "NOT-01")) }).catch(() => undefined);
    await expect.poll(() => client.getQueryData(["claims"])).toBeUndefined();
  });

  it("panne du serveur ou coupure réseau : les données restent (hors ligne, la carte du jour reste lisible)", async () => {
    const client = createMemberQueryClient();
    client.setQueryData(["claims"], { pages: [] });
    await client.fetchQuery({ queryKey: ["card", "self"], queryFn: () => Promise.reject(problem(503, "SYS-01")) }).catch(() => undefined);
    await client.fetchQuery({ queryKey: ["me"], queryFn: () => Promise.reject(new NetworkUnavailable(true)) }).catch(() => undefined);
    expect(client.getQueryData(["claims"])).toEqual({ pages: [] });
  });
});
