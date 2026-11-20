// @vitest-environment jsdom
/**
 * Bandeau de premier usage et interrupteur de la mesure : sobres, explicites, réversibles.
 * Le bandeau ne s'affiche que tant que la personne n'a pas choisi ; « En savoir plus » déplie un
 * court texte ; l'interrupteur dit l'état réel (désactivé tant qu'aucun choix n'est fait).
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { MeasureConsentBanner, MeasureSwitch } from "../../src/components/measure-consent";
import { t } from "../../src/i18n";
import { readMeasureChoice } from "../../src/lib/measure-consent";
import { telemetryEnabled } from "../../src/lib/telemetry";

afterEach(() => window.localStorage.clear());

describe("bandeau de premier usage", () => {
  it("sans choix : bandeau nommé, non modal, deux choix explicites", async () => {
    render(<MeasureConsentBanner />);
    const banner = await screen.findByRole("region", { name: t("measure.banner.title") });
    expect(banner.textContent).toContain(t("measure.banner.text"));
    expect(within(banner).getByRole("button", { name: t("measure.accept") })).toBeTruthy();
    expect(within(banner).getByRole("button", { name: t("measure.refuse") })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("« En savoir plus » déplie le court texte (aria-expanded)", async () => {
    const user = userEvent.setup();
    render(<MeasureConsentBanner />);
    const more = await screen.findByRole("button", { name: t("measure.learnMore") });
    expect(more.getAttribute("aria-expanded")).toBe("false");
    await user.click(more);
    expect(more.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByTestId("measure-details").textContent).toContain(t("measure.details.never"));
  });

  it("Accepter : choix gardé, bandeau retiré, mesure activée", async () => {
    const user = userEvent.setup();
    render(<MeasureConsentBanner />);
    await user.click(await screen.findByRole("button", { name: t("measure.accept") }));
    expect(readMeasureChoice()).toBe("granted");
    expect(telemetryEnabled()).toBe(true);
    expect(screen.queryByRole("region", { name: t("measure.banner.title") })).toBeNull();
  });

  it("Refuser : choix gardé, bandeau retiré, mesure désactivée", async () => {
    const user = userEvent.setup();
    render(<MeasureConsentBanner />);
    await user.click(await screen.findByRole("button", { name: t("measure.refuse") }));
    expect(readMeasureChoice()).toBe("refused");
    expect(telemetryEnabled()).toBe(false);
    expect(screen.queryByRole("region", { name: t("measure.banner.title") })).toBeNull();
  });

  it("choix déjà fait : aucun bandeau", () => {
    window.localStorage.setItem("mulemacare-one.console.mesure.choix", JSON.stringify({ v: 1, choice: "refused" }));
    render(<MeasureConsentBanner />);
    expect(screen.queryByRole("region", { name: t("measure.banner.title") })).toBeNull();
  });
});

describe("interrupteur", () => {
  it("désactivé tant qu'aucun choix ; un clic active, un autre désactive ; le bandeau suit", async () => {
    const user = userEvent.setup();
    render(
      <>
        <MeasureConsentBanner />
        <MeasureSwitch />
      </>,
    );
    const toggle = await screen.findByRole("switch", { name: t("measure.switch") });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    await user.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(readMeasureChoice()).toBe("granted");
    // Un choix fait par l'interrupteur vaut choix : le bandeau disparaît.
    expect(screen.queryByRole("region", { name: t("measure.banner.title") })).toBeNull();
    await user.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect(readMeasureChoice()).toBe("refused");
  });
});
