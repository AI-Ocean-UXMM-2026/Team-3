import { describe, expect, it } from "vitest";
import { extractPhones, extractPayment, extractName, extractStreet } from "../src/rules.ts";

describe("Layer 1: phone numbers (HLR-03)", () => {
  it.each([
    ["ဖုန်း 09 777 123 456", "09777123456"],
    ["Ph: 09-450-123-456", "09450123456"],
    ["+95 9 777 123 456 ကိုဆက်ပါ", "09777123456"],
    ["959777123456", "09777123456"],
    ["ဖုန်း ၀၉၇၈၁၂၃၄၅၆၇", "09781234567"],
    ["ဖုန်း ဝ၉၇၈၁၂၃၄၅၆၇", "09781234567"],
    ["call 0942512345", "0942512345"],
  ])("finds the phone in %j", (text, phone) => {
    expect(extractPhones(text).map((p) => p.number)).toEqual([phone]);
  });

  it("marks well-formed mobiles valid and short ones invalid", () => {
    const [ok] = extractPhones("09777123456");
    expect(ok).toMatchObject({ number: "09777123456", valid: true });
    const [bad] = extractPhones("09 7771");
    expect(bad).toMatchObject({ valid: false });
  });

  it("keeps the matched span so the text can be redacted", () => {
    const text = "Ma Thida 09-777-123-456 Kamayut";
    const [p] = extractPhones(text);
    expect(text.slice(p.start, p.end)).toBe("09-777-123-456");
  });

  it("finds two numbers when a buyer gives a backup", () => {
    expect(extractPhones("09777123456 / 09450123456").map((p) => p.number)).toEqual([
      "09777123456",
      "09450123456",
    ]);
  });

  it("ignores prices and house numbers", () => {
    expect(extractPhones("COD 28000 ks, အမှတ် ၁၂၃")).toEqual([]);
  });
});

describe("Layer 1: COD and prepaid (HLR-03)", () => {
  it.each([
    ["COD 28000", 28000],
    ["COD - 28,000 ks", 28000],
    ["ငွေ ၂၈,၀၀၀ ကျပ် ကောက်ရန်", 28000],
    ["28000ks", 28000],
    ["စုစုပေါင်း 35,500 MMK", 35500],
    ["၂ သောင်း ၈ ထောင်", 28000],
    ["1.5 သိန်း", 150000],
    ["၅ ထောင် ကျပ်", 5000],
  ])("reads the amount in %j", (text, amount) => {
    expect(extractPayment(text)).toMatchObject({ codAmount: amount, prepaid: false });
  });

  it("prefers the labelled COD/total amount over an item price", () => {
    expect(extractPayment("ဂါဝန် 25000 ks + ပို့ခ 3000 ks\nCOD 28000")).toMatchObject({ codAmount: 28000 });
  });

  it("treats KBZPay / WavePay / AYA Pay transfers as prepaid with nothing to collect", () => {
    expect(extractPayment("KPay နဲ့ ငွေလွှဲပြီးပါပြီ")).toEqual({ codAmount: 0, prepaid: true, method: "KBZPay" });
    expect(extractPayment("Wave pay prepaid")).toEqual({ codAmount: 0, prepaid: true, method: "WavePay" });
    expect(extractPayment("AYA Pay ချေပြီး")).toEqual({ codAmount: 0, prepaid: true, method: "AYA Pay" });
  });

  it("returns null when no amount is given", () => {
    expect(extractPayment("ကမာရွတ် ဆင်ရေကန်လမ်း")).toEqual({ codAmount: null, prepaid: false });
  });

  it("does not read a phone number as money", () => {
    expect(extractPayment("09777123456")).toEqual({ codAmount: null, prepaid: false });
  });
});

describe("Layer 1: name", () => {
  it.each([
    ["Name: Ma Thida\n09777123456", "Ma Thida"],
    ["အမည် - ဒေါ်ခင်ခင်\nတာမွေ", "ဒေါ်ခင်ခင်"],
    ["Ko Aung Aung\n09777123456", "Ko Aung Aung"],
    ["ကိုအောင်အောင်\nဗဟန်း", "ကိုအောင်အောင်"],
    ["1. Ma Thida\n09777123456", "Ma Thida"],
    ["၄။ Name - မမြတ်နိုး", "မမြတ်နိုး"],
    ["12) ဒေါ်စန်းစန်း", "ဒေါ်စန်းစန်း"],
  ])("finds the customer in %j", (text, name) => {
    expect(extractName(text)?.value).toBe(name);
  });

  it("returns null without a label or honorific", () => {
    expect(extractName("ကမာရွတ် ဆင်ရေကန်လမ်း 09777123456")).toBeNull();
  });
});

describe("Layer 1: street and house number", () => {
  it.each([
    ["အမှတ် ၁၂၃၊ ၃၇ လမ်း၊ ကျောက်တံတား", { houseNo: "123", street: "37 လမ်း" }],
    ["No. 45, Baho Road, Sanchaung", { houseNo: "45", street: "Baho Road" }],
    ["No.(12/B), 5th Street, Kamayut", { houseNo: "12/B", street: "5th Street" }],
    ["တိုက် ၇ အခန်း ၃ ဗိုလ်ချုပ်လမ်း", { houseNo: null, street: "ဗိုလ်ချုပ်လမ်း" }],
  ])("reads %j", (text, expected) => {
    expect(extractStreet(text)).toEqual(expected);
  });

  it("does not read a junction or alley as a street", () => {
    expect(extractStreet("8 မိုင်လမ်းဆုံ အနီး ပြည်လမ်း").street).toBe("ပြည်လမ်း");
    expect(extractStreet("ဈေးအနီး လမ်းကြားထဲ")).toEqual({ houseNo: null, street: null });
  });

  it("returns nulls when nothing is there", () => {
    expect(extractStreet("အဆွေတော်နား")).toEqual({ houseNo: null, street: null });
  });
});
