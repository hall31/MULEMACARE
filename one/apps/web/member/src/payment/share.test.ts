import { describe, expect, it, vi } from "vitest";
import { contributions } from "@/test/fixtures";
import { inviteMessage, shareInvite, whatsappUrl } from "./share";

const link = { url: "https://app.mulemacare.invalid/payer/jeton-fictif", expires_at: "2026-10-08T23:59:00Z" };
const due = contributions.items[0];

describe("inviter un proche à payer : partage du lien", () => {
  it("message : période, montant FCFA entier, échéance du lien et adresse", () => {
    if (!due) throw new Error("fixture");
    const text = inviteMessage(due, link, "Africa/Abidjan");
    expect(text).toContain("octobre 2026");
    expect(text).toContain("27 500 FCFA");
    expect(text).toContain("08/10/2026");
    expect(text).toContain(link.url);
  });

  it("WhatsApp : lien wa.me avec le message encodé (aucun numéro imposé)", () => {
    const url = new URL(whatsappUrl("Bonjour & merci : https://x.invalid/p?a=1"));
    expect(url.origin).toBe("https://wa.me");
    expect(url.pathname).toBe("/");
    expect(url.searchParams.get("text")).toBe("Bonjour & merci : https://x.invalid/p?a=1");
  });

  it("partage natif d'abord ; annulation par l'adhérent = rien à signaler", async () => {
    const share = vi.fn(async () => undefined);
    expect(await shareInvite({ share }, { title: "t", text: "m", url: link.url })).toBe("shared");
    expect(share).toHaveBeenCalledWith({ title: "t", text: "m", url: link.url });

    const cancelled = vi.fn(async () => Promise.reject(new DOMException("annulé", "AbortError")));
    expect(await shareInvite({ share: cancelled }, { title: "t", text: "m", url: link.url })).toBe("cancelled");
  });

  it("sans partage natif : copie du lien ; sans presse-papiers : échec annoncé", async () => {
    const writeText = vi.fn(async () => undefined);
    expect(await shareInvite({ clipboard: { writeText } }, { title: "t", text: "m", url: link.url })).toBe("copied");
    expect(writeText).toHaveBeenCalledWith(link.url);
    expect(await shareInvite({}, { title: "t", text: "m", url: link.url })).toBe("unavailable");
    const denied = vi.fn(async () => Promise.reject(new Error("refusé")));
    expect(await shareInvite({ clipboard: { writeText: denied } }, { title: "t", text: "m", url: link.url })).toBe("unavailable");
  });
});
