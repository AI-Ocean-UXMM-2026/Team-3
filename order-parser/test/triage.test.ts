import { describe, expect, it } from "vitest";
import { triage } from "../src/triage.ts";
import { getTownship } from "../src/townships.ts";
import { PLACES } from "../src/places.ts";

const kamayut = getTownship("kamayut");
const junctionSquare = { ...PLACES.find((p) => p.name === "Junction Square")!, source: "dictionary" as const };
const base = {
  phone: { number: "09777123456", valid: true },
  township: kamayut,
  townshipCount: 1,
  location: junctionSquare,
};

describe("Green / Amber / Red from rule checks only (HLR-10, HLR-11, HLR-14)", () => {
  it("is Green with a valid phone, a township and a mapped place, and goes to the rider queue", () => {
    const t = triage(base);
    expect(t).toMatchObject({ level: "green", icon: "check", route: "rider_queue" });
    expect(t.label).toEqual({ en: "Ready to dispatch", my: "ပို့ရန် အသင့်" });
    expect(t.reasons.map((r) => r.code)).toEqual(["all_checks_passed"]);
  });

  it("is Amber when nothing can be put on the map, and sends the buyer a confirmation link", () => {
    const t = triage({ ...base, location: null });
    expect(t).toMatchObject({ level: "amber", icon: "warning", route: "buyer_confirmation" });
    expect(t.reasons.map((r) => r.code)).toEqual(["location_vague"]);
  });

  it("is Amber when the mapped place is in a different township", () => {
    const t = triage({ ...base, township: getTownship("tamwe") });
    expect(t.level).toBe("amber");
    expect(t.reasons[0]).toMatchObject({ code: "place_in_other_township" });
    expect(t.reasons[0].en).toContain("Junction Square is in Kamayut, not Tamwe");
  });

  it("is Amber when more than one township is mentioned", () => {
    expect(triage({ ...base, townshipCount: 2 }).reasons.map((r) => r.code)).toEqual(["several_townships"]);
  });

  it("is Red without a phone, and the order is held for the dispatcher", () => {
    const t = triage({ ...base, phone: null });
    expect(t).toMatchObject({ level: "red", icon: "stop", route: "dispatcher_hold" });
    expect(t.reasons.map((r) => r.code)).toEqual(["no_phone"]);
  });

  it("is Red with an incomplete phone or an unknown area, and lists every reason", () => {
    const t = triage({ ...base, phone: { number: "097771", valid: false }, township: null, location: null });
    expect(t.level).toBe("red");
    expect(t.reasons.map((r) => r.code)).toEqual(["invalid_phone", "unknown_township"]);
  });

  it("gives every reason in English and Burmese", () => {
    for (const r of triage({ ...base, phone: null, township: null }).reasons) {
      expect(r.en.length).toBeGreaterThan(0);
      expect(r.my).toMatch(/[က-႟]/);
    }
  });

  it("is Green when the buyer or dispatcher has set the pin", () => {
    const pin = { lat: 16.8, lng: 96.13, source: "buyer" as const, townshipId: "kamayut" };
    expect(triage({ ...base, location: pin }).level).toBe("green");
  });
});
