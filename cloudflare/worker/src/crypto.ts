import type { LicenseDocument } from "./types";

export function base64urlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function base64urlDecode(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

export async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return base64urlEncode(new Uint8Array(digest));
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, sortValue(item)]));
  }
  return value;
}

export function canonicalLicensePayload(license: Omit<LicenseDocument, "signature">): string {
  return JSON.stringify(sortValue(license));
}

export async function importEd25519PrivateKey(value: string): Promise<CryptoKey> {
  return crypto.subtle.importKey("jwk", JSON.parse(value), { name: "Ed25519" }, false, ["sign"]);
}

export async function verifyEd25519(publicKey: string, message: string, signature: string): Promise<boolean> {
  const key = await crypto.subtle.importKey("raw", base64urlDecode(publicKey), { name: "Ed25519" }, false, ["verify"]);
  return crypto.subtle.verify("Ed25519", key, base64urlDecode(signature), new TextEncoder().encode(message));
}

export async function signLicense(license: Omit<LicenseDocument, "signature">, privateKeyJwk: string): Promise<string> {
  const key = await importEd25519PrivateKey(privateKeyJwk);
  const signature = await crypto.subtle.sign("Ed25519", key, new TextEncoder().encode(canonicalLicensePayload(license)));
  return base64urlEncode(new Uint8Array(signature));
}
