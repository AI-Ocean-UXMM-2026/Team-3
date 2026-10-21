import { describe, expect, it } from "vitest";
import rabbit from "rabbit-node";
import { toUnicode, toAsciiDigits } from "../src/encoding.ts";

const uni = "အဆွေတော်နား ၄ ထပ်တိုက် ညာဘက်ခန်း";

describe("Layer 0: encoding (HLR-02)", () => {
  it("leaves Unicode text unchanged", () => {
    expect(toUnicode(uni)).toEqual({ text: uni, wasZawgyi: false });
  });

  it("detects Zawgyi and converts it to Unicode", () => {
    const zawgyi = rabbit.uni2zg(uni);
    expect(zawgyi).not.toBe(uni);
    expect(toUnicode(zawgyi)).toEqual({ text: uni, wasZawgyi: true });
  });

  it("leaves English-only text alone", () => {
    expect(toUnicode("No. 12, Pyay Road")).toEqual({ text: "No. 12, Pyay Road", wasZawgyi: false });
  });

  it("converts each line on its own, so a mixed paste is handled", () => {
    const mixed = `${rabbit.uni2zg(uni)}\n${uni}`;
    expect(toUnicode(mixed)).toEqual({ text: `${uni}\n${uni}`, wasZawgyi: true });
  });
});

describe("Myanmar digits", () => {
  it("maps ၀-၉ to 0-9", () => {
    expect(toAsciiDigits("၀၉၁၂၃၄၅၆၇၈၉")).toBe("09123456789");
  });

  it("treats the letter ဝ as zero only when it sits between digits", () => {
    expect(toAsciiDigits("ဝ၉၇၇၇၁၂၃၄၅၆")).toBe("09777123456");
    expect(toAsciiDigits("၂၈ဝဝဝ")).toBe("28000");
    expect(toAsciiDigits("ဝင်း")).toBe("ဝင်း");
  });
});
