import { describe, expect, it, vi } from "vitest";
import { BuyerLinks, distanceMeters, QUICK_ACTIONS } from "../src/buyerLink.ts";
import { parseOrder } from "../src/parser.ts";
import { DictionaryGeocoder } from "../src/places.ts";
import type { AddressExtractor } from "../src/ai/types.ts";

const noAi: AddressExtractor = { extract: async () => ({ raw: {}, model: "none", offline: false }) };
const context = {
  shop: { name: "Thida Boutique", avatarUrl: "https://example.test/thida.png" },
  item: { name: "Floral Summer Dress", photoUrl: "https://example.test/dress.jpg" },
  invoiceNo: "INV-0042",
};
const HOUR = 3_600_000;

async function setup(text = "Ma Thida\n09777123456\nကမာရွတ် Junction Square နောက်ဘက်\nCOD 28000") {
  let now = new Date("2026-10-20T08:00:00Z").getTime();
  const onLocked = vi.fn();
  const links = new BuyerLinks({ baseUrl: "https://lannpya.app", now: () => now, onLocked });
  const order = await parseOrder(text, { extractor: noAi, geocoder: new DictionaryGeocoder() }, "order-7");
  const link = links.create(order, context);
  return { links, order, link, onLocked, advance: (ms: number) => (now += ms) };
}

describe("tokenized buyer link (HLR-15, HLR-18)", () => {
  it("is unique, unguessable and opens /track/:token", async () => {
    const { links, order, link } = await setup();
    const other = links.create(order, context);
    expect(link.token).toMatch(/^[A-Za-z0-9_-]{22,}$/);
    expect(other.token).not.toBe(link.token);
    expect(link.url).toBe(`https://lannpya.app/track/${link.token}`);
  });

  it("gives the shop a Messenger message with the link that says nothing sensitive is asked", async () => {
    const { links, link } = await setup();
    const message = links.shareMessage(link.token);
    expect(message).toContain("Thida Boutique");
    expect(message).toContain("Floral Summer Dress");
    expect(message).toContain(link.url);
    expect(message).toContain("စကားဝှက်");
  });

  it("expires 24 hours after delivery, not before", async () => {
    const { links, link, advance } = await setup();
    advance(72 * HOUR);
    expect(links.open(link.token).status).toBe("pending");
    links.markDelivered(link.token);
    advance(23 * HOUR);
    expect(links.open(link.token).status).toBe("delivered");
    advance(2 * HOUR);
    expect(links.open(link.token)).toEqual({ status: "expired" });
  });

  it("returns not_found for an unknown token", async () => {
    const { links } = await setup();
    expect(links.open("nope")).toEqual({ status: "not_found" });
  });
});

describe("view-only until the 4-digit check (HLR-19, HLR-20, HLR-21)", () => {
  it("shows shop, item, invoice and COD, but never the address or phone", async () => {
    const { links, link } = await setup();
    const view = links.open(link.token);
    expect(view).toMatchObject({
      status: "pending",
      shop: context.shop,
      item: context.item,
      invoiceNo: "INV-0042",
      payment: { codAmount: 28000, prepaid: false },
    });
    const json = JSON.stringify(view);
    expect(json).not.toMatch(/09777123456|Junction|ကမာရွတ်|Thida"/);
    expect(json).not.toContain("3456");
  });

  it("shows the address after the last 4 digits of the phone are entered", async () => {
    const { links, link } = await setup();
    const result = links.verify(link.token, "3456");
    expect(result).toMatchObject({ ok: true });
    const full = links.open(link.token, result.ok ? result.session : undefined);
    expect(full).toMatchObject({ address: { township: "Kamayut", landmark: null }, pin: { lat: expect.any(Number) } });
  });

  it("accepts Myanmar digits for the check", async () => {
    const { links, link } = await setup();
    expect(links.verify(link.token, "၃၄၅၆").ok).toBe(true);
  });

  it("locks after 3 wrong tries, even for the right digits, and tells the shop", async () => {
    const { links, link, onLocked } = await setup();
    expect(links.verify(link.token, "0000")).toEqual({ ok: false, attemptsLeft: 2, locked: false });
    expect(links.verify(link.token, "1111")).toEqual({ ok: false, attemptsLeft: 1, locked: false });
    expect(links.verify(link.token, "2222")).toEqual({ ok: false, attemptsLeft: 0, locked: true });
    expect(links.verify(link.token, "3456")).toEqual({ ok: false, attemptsLeft: 0, locked: true });
    expect(links.open(link.token).status).toBe("locked");
    expect(onLocked).toHaveBeenCalledOnce();
  });

  it("does not accept a session from another link", async () => {
    const { links, order, link } = await setup();
    const other = links.create(order, context);
    const s = links.verify(other.token, "3456");
    expect(links.open(link.token, s.ok ? s.session : undefined)).not.toHaveProperty("address");
  });
});

describe("pin limits (HLR-22, HLR-24)", () => {
  it("measures distance in metres", () => {
    expect(distanceMeters({ lat: 16.8, lng: 96.13 }, { lat: 16.8045, lng: 96.13 })).toBeCloseTo(500, -1);
  });

  it("allows a nudge inside the 500 m circle and saves it as the buyer's pin", async () => {
    const { links, link, order } = await setup();
    const s = links.verify(link.token, "3456");
    if (!s.ok) throw new Error("verify failed");
    const nudge = { lat: order.location!.lat + 0.002, lng: order.location!.lng };
    const result = links.movePin(link.token, s.session, nudge);
    expect(result).toMatchObject({ allowed: true, pin: { ...nudge, source: "buyer", townshipId: "kamayut" } });
    expect(links.open(link.token, s.session)).toMatchObject({ pin: { lat: nudge.lat } });
  });

  it("refuses a move outside the circle", async () => {
    const { links, link, order } = await setup();
    const s = links.verify(link.token, "3456");
    if (!s.ok) throw new Error();
    const far = { lat: order.location!.lat + 0.01, lng: order.location!.lng };
    expect(links.movePin(link.token, s.session, far)).toMatchObject({ allowed: false, reason: "outside_radius" });
  });

  it("keeps the circle on the original pin, so repeated nudges cannot walk it away", async () => {
    const { links, link, order } = await setup();
    const s = links.verify(link.token, "3456");
    if (!s.ok) throw new Error();
    const step = (n: number) => ({ lat: order.location!.lat + 0.004 * n, lng: order.location!.lng });
    expect(links.movePin(link.token, s.session, step(1))).toMatchObject({ allowed: true });
    expect(links.movePin(link.token, s.session, step(2))).toMatchObject({ allowed: false, reason: "outside_radius" });
  });

  it("blocks a move into another township with the courier's fee message", async () => {
    const { links, link, order } = await setup();
    const s = links.verify(link.token, "3456");
    if (!s.ok) throw new Error();
    const near = { lat: order.location!.lat + 0.001, lng: order.location!.lng };
    const result = links.movePin(link.token, s.session, near, { townshipOf: () => "sanchaung" });
    expect(result).toMatchObject({ allowed: false, reason: "cross_township" });
    if (result.allowed) throw new Error();
    expect(result.message.en).toBe(
      "Changing township needs a new delivery route. Extra fee: +1,500 MMK. Delivery moves to tomorrow.",
    );
    expect(result.message.my).toMatch(/[က-႟]/);
  });

  it("lets an Amber buyer drop the first pin anywhere in their township", async () => {
    const { links, link } = await setup("09777123456\nတာမွေ အဆွေတော်နား");
    const s = links.verify(link.token, "3456");
    if (!s.ok) throw new Error();
    expect(links.movePin(link.token, s.session, { lat: 16.81, lng: 96.17 }, { townshipOf: () => "tamwe" })).toMatchObject({
      allowed: true,
    });
  });

  it("requires the 4-digit check first", async () => {
    const { links, link } = await setup();
    expect(links.movePin(link.token, "forged", { lat: 0, lng: 0 })).toMatchObject({ allowed: false, reason: "not_verified" });
  });
});

describe("one-tap buyer answers (HLR-23)", () => {
  it("offers the three Burmese quick answers", () => {
    expect(QUICK_ACTIONS.map((a) => a.my)).toEqual(["အိမ်မှာရှိပါတယ်", "အချိန်ရွှေ့မည်", "လုံခြုံရေးထံ ထားခဲ့ပါ"]);
  });

  it("records an answer with a note", async () => {
    const { links, link } = await setup();
    const s = links.verify(link.token, "3456");
    if (!s.ok) throw new Error();
    expect(links.respond(link.token, s.session, { action: "leave_with_security", note: "ဂိတ်မှူးကို ပေးပါ" })).toEqual({ ok: true });
    expect(links.open(link.token, s.session)).toMatchObject({
      response: { action: "leave_with_security", note: "ဂိတ်မှူးကို ပေးပါ" },
    });
  });

  it("needs a time window to reschedule", async () => {
    const { links, link } = await setup();
    const s = links.verify(link.token, "3456");
    if (!s.ok) throw new Error();
    expect(links.respond(link.token, s.session, { action: "reschedule" })).toEqual({ ok: false, error: "window_required" });
    expect(links.respond(link.token, s.session, { action: "reschedule", window: "17:00-19:00" })).toEqual({ ok: true });
  });
});
