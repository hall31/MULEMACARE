/**
 * Signature des accords provisoires sur l'appareil : ECDSA P-256 / SHA-256 (ES256), WebCrypto.
 * La clé privée est générée non exportable et ne quitte jamais l'appareil (stockée comme
 * CryptoKey dans IndexedDB). La clé publique (JWK) est enregistrée via `POST /v1/counter/devices`.
 *
 * Format : `signed_payload` = base64url(JSON canonique UTF-8) ; `signature` = base64url des
 * 64 octets r||s (format JWS) calculés sur les octets UTF-8 du JSON canonique.
 */
const ALGORITHM: EcKeyGenParams = { name: "ECDSA", namedCurve: "P-256" };
const SIGN_PARAMS: EcdsaParams = { name: "ECDSA", hash: "SHA-256" };

export type Json = string | number | boolean | null | Json[] | { [key: string]: Json | undefined };

export function canonicalJson(value: Json): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map((v) => canonicalJson(v)).join(",")}]`;
  const keys = Object.keys(value)
    .filter((k) => value[k] !== undefined)
    .sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(value[k] as Json)}`).join(",")}}`;
}

export function base64url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function fromBase64url(text: string): Uint8Array<ArrayBuffer> {
  const padded = text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export async function generateDeviceKeys(): Promise<CryptoKeyPair> {
  return crypto.subtle.generateKey(ALGORITHM, false, ["sign", "verify"]);
}

export async function exportPublicJwk(publicKey: CryptoKey): Promise<string> {
  const jwk = await crypto.subtle.exportKey("jwk", publicKey);
  return canonicalJson({ kty: jwk.kty ?? "EC", crv: jwk.crv ?? "P-256", x: jwk.x ?? "", y: jwk.y ?? "" });
}

export interface SignedPayload {
  signed_payload: string;
  signature: string;
}

export async function signPayload(privateKey: CryptoKey, payload: Json): Promise<SignedPayload> {
  const bytes = new TextEncoder().encode(canonicalJson(payload));
  const signature = new Uint8Array(await crypto.subtle.sign(SIGN_PARAMS, privateKey, bytes));
  return { signed_payload: base64url(bytes), signature: base64url(signature) };
}

export async function verifySignature(publicJwk: string, signedPayload: string, signature: string): Promise<boolean> {
  const key = await crypto.subtle.importKey("jwk", JSON.parse(publicJwk) as JsonWebKey, ALGORITHM, false, ["verify"]);
  return crypto.subtle.verify(SIGN_PARAMS, key, fromBase64url(signature), fromBase64url(signedPayload));
}
