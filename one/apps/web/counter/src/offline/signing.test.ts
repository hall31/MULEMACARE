import { describe, expect, it } from "vitest";
import { canonicalJson, exportPublicJwk, fromBase64url, generateDeviceKeys, signPayload, verifySignature } from "./signing";

describe("signature de l'accord provisoire sur l'appareil", () => {
  it("produit un JSON canonique (clés triées, sans espace), stable quel que soit l'ordre", () => {
    expect(canonicalJson({ b: 1, a: { d: [2, { z: 1, y: 2 }], c: "é" } })).toBe('{"a":{"c":"é","d":[2,{"y":2,"z":1}]},"b":1}');
    expect(canonicalJson({ a: 1, b: 2 })).toBe(canonicalJson({ b: 2, a: 1 }));
  });

  it("garde la clé privée non exportable", async () => {
    const keys = await generateDeviceKeys();
    expect(keys.privateKey.extractable).toBe(false);
    await expect(crypto.subtle.exportKey("jwk", keys.privateKey)).rejects.toThrow();
  });

  it("signe en ES256 : la signature se vérifie avec la clé publique enregistrée", async () => {
    const keys = await generateDeviceKeys();
    const jwk = await exportPublicJwk(keys.publicKey);
    expect(JSON.parse(jwk)).toMatchObject({ kty: "EC", crv: "P-256" });
    const signed = await signPayload(keys.privateKey, { total_xof: 48_000, offline_ref: "x" });
    expect(new TextDecoder().decode(fromBase64url(signed.signed_payload))).toBe('{"offline_ref":"x","total_xof":48000}');
    expect(fromBase64url(signed.signature)).toHaveLength(64);
    expect(await verifySignature(jwk, signed.signed_payload, signed.signature)).toBe(true);
  });

  it("rejette un contenu modifié après signature", async () => {
    const keys = await generateDeviceKeys();
    const jwk = await exportPublicJwk(keys.publicKey);
    const signed = await signPayload(keys.privateKey, { total_xof: 48_000 });
    const forged = await signPayload(keys.privateKey, { total_xof: 480_000 });
    expect(await verifySignature(jwk, forged.signed_payload, signed.signature)).toBe(false);
  });
});
