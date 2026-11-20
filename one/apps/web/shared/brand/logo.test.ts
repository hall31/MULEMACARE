import { describe, expect, it } from "vitest";
import { BRANDING_FIXTURES } from "./fixtures";
import { safeLogoSrc } from "./logo";

describe("logo (défense en profondeur, rendu dans un <img> seulement)", () => {
  it("garde les formes du contrat", () => {
    expect(safeLogoSrc(BRANDING_FIXTURES["lagune-sante"]!.logo)).toMatch(/^data:image\/svg\+xml;base64,/);
    expect(safeLogoSrc({ kind: "url", src: "/assets/logos/lagune.png" })).toBe("/assets/logos/lagune.png");
    expect(safeLogoSrc({ kind: "url", src: "https://medias.mulemacare.ci/logos/a.png" })).toBe("https://medias.mulemacare.ci/logos/a.png");
  });

  it.each([
    [{ kind: "url", src: "javascript:alert(1)" }],
    [{ kind: "url", src: "http://exemple.ci/logo.png" }],
    [{ kind: "url", src: "https://user:pw@exemple.ci/logo.png" }],
    [{ kind: "url", src: "https://exemple.ci/logo.png?x=1" }],
    [{ kind: "url", src: "//exemple.ci/logo.png" }],
    [{ kind: "url", src: "/../secret" }],
    [{ kind: "data_uri", src: "data:text/html;base64,PHNjcmlwdD4=" }],
    [{ kind: "data_uri", src: "data:image/svg+xml,<svg onload=alert(1)>" }],
    [{ kind: "data_uri", src: `data:image/png;base64,${"A".repeat(50_000)}` }],
    [{ kind: "autre", src: "/a.png" }],
    [null],
    ["/a.png"],
  ])("refuse %j", (logo) => {
    expect(safeLogoSrc(logo)).toBeNull();
  });
});
