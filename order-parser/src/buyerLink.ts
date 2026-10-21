import { toAsciiDigits } from "./encoding.ts";
import type { Location, ParsedOrder } from "./order.ts";

export interface LinkContext {
  shop: { name: string; avatarUrl?: string };
  item: { name: string; photoUrl?: string };
  invoiceNo: string;
}

export const QUICK_ACTIONS = [
  { id: "at_home", my: "အိမ်မှာရှိပါတယ်", en: "At home" },
  { id: "reschedule", my: "အချိန်ရွှေ့မည်", en: "Reschedule" },
  { id: "leave_with_security", my: "လုံခြုံရေးထံ ထားခဲ့ပါ", en: "Leave with security" },
] as const;

export type QuickAction = (typeof QUICK_ACTIONS)[number]["id"];

export interface BuyerResponse {
  action: QuickAction;
  window?: string;
  note?: string;
}

interface LinkRecord {
  token: string;
  order: ParsedOrder;
  context: LinkContext;
  attempts: number;
  locked: boolean;
  sessions: Set<string>;
  deliveredAt: number | null;
  pin: Location | null;
  /** Centre of the movement circle: the original pin, or the buyer's first pin on an Amber order. */
  center: Location | null;
  response: BuyerResponse | null;
}

export interface BuyerLinkOptions {
  baseUrl: string;
  now?: () => number;
  /** Called once when a link locks after too many wrong tries (shop notification is NEXT, HLR-25). */
  onLocked?: (orderId: string) => void;
  maxAttempts?: number;
  radiusMeters?: number;
  /** Courier rule for moving to another township; courier-set rules are NEXT (HLR-26). */
  crossTownshipFeeMmk?: number;
}

export type PublicView =
  | { status: "not_found" | "expired" }
  | {
      status: "pending" | "delivered" | "locked";
      shop: LinkContext["shop"];
      item: LinkContext["item"];
      invoiceNo: string;
      payment: { codAmount: number | null; prepaid: boolean; method: string | null };
    };

export type FullView = PublicView & {
  address: {
    customerName: string | null;
    township: string | null;
    townshipMy: string | null;
    houseNo: string | null;
    street: string | null;
    landmark: string | null;
    floorUnit: string | null;
    instructions: string | null;
  };
  pin: Location | null;
  radiusMeters: number;
  response: BuyerResponse | null;
};

export type VerifyResult = { ok: true; session: string } | { ok: false; attemptsLeft: number; locked: boolean };

export type PinResult =
  | { allowed: true; pin: Location }
  | {
      allowed: false;
      reason: "not_verified" | "outside_radius" | "cross_township";
      message: { en: string; my: string };
    };

const DAY = 24 * 3_600_000;

function randomToken(bytes = 16): string {
  return Buffer.from(crypto.getRandomValues(new Uint8Array(bytes))).toString("base64url");
}

export function distanceMeters(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const R = 6_371_000;
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/**
 * The no-app buyer confirmation link (Module 2). In-memory for the MVP; the record shape is what a
 * serverless KV or database row would hold.
 */
export class BuyerLinks {
  private readonly links = new Map<string, LinkRecord>();
  private readonly baseUrl: string;
  private readonly now: () => number;
  private readonly onLocked?: (orderId: string) => void;
  private readonly maxAttempts: number;
  private readonly radius: number;
  private readonly fee: number;

  constructor(options: BuyerLinkOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.now = options.now ?? Date.now;
    this.onLocked = options.onLocked;
    this.maxAttempts = options.maxAttempts ?? 3;
    this.radius = options.radiusMeters ?? 500;
    this.fee = options.crossTownshipFeeMmk ?? 1500;
  }

  create(order: ParsedOrder, context: LinkContext): { token: string; url: string } {
    const token = randomToken();
    this.links.set(token, {
      token,
      order,
      context,
      attempts: 0,
      locked: false,
      sessions: new Set(),
      deliveredAt: null,
      pin: order.location,
      center: order.location,
      response: null,
    });
    return { token, url: this.url(token) };
  }

  /** The message the shop pastes into its own Messenger chat with the buyer (trust by context). */
  shareMessage(token: string): string {
    const rec = this.get(token);
    if (!rec) throw new Error("Unknown link");
    const { shop, item } = rec.context;
    return [
      `${shop.name} မှ မှာယူထားသော "${item.name}" ကို ပို့ဆောင်ရန် တည်နေရာနှင့် အချိန် အတည်ပြုပေးပါ။`,
      this.url(token),
      "စကားဝှက်၊ ဘဏ်အချက်အလက် သို့မဟုတ် ငွေပေးချေမှု မတောင်းပါ။",
    ].join("\n");
  }

  open(token: string, session?: string): PublicView | FullView {
    const rec = this.get(token);
    if (!rec) return { status: "not_found" };
    if (this.expired(rec)) return { status: "expired" };
    const { order, context } = rec;
    const view: PublicView = {
      status: rec.locked ? "locked" : rec.deliveredAt !== null ? "delivered" : "pending",
      shop: context.shop,
      item: context.item,
      invoiceNo: context.invoiceNo,
      payment: { codAmount: order.fields.codAmount, prepaid: order.fields.prepaid, method: order.fields.paymentMethod },
    };
    if (!this.verified(rec, session)) return view;
    const f = order.fields;
    return {
      ...view,
      address: {
        customerName: f.customerName,
        township: f.township?.en ?? null,
        townshipMy: f.township?.my ?? null,
        houseNo: f.houseNo,
        street: f.street,
        landmark: f.landmark,
        floorUnit: f.floorUnit,
        instructions: f.instructions,
      },
      pin: rec.pin,
      radiusMeters: this.radius,
      response: rec.response,
    };
  }

  /** Light check against accidental forwards: last 4 digits of the recipient's phone, 3 tries. */
  verify(token: string, last4: string): VerifyResult {
    const rec = this.get(token);
    if (!rec || this.expired(rec)) return { ok: false, attemptsLeft: 0, locked: true };
    if (rec.locked) return { ok: false, attemptsLeft: 0, locked: true };
    const phone = rec.order.fields.phone;
    if (phone && toAsciiDigits(last4).replace(/\D/g, "") === phone.slice(-4)) {
      const session = randomToken();
      rec.sessions.add(session);
      return { ok: true, session };
    }
    rec.attempts++;
    if (rec.attempts >= this.maxAttempts) {
      rec.locked = true;
      this.onLocked?.(rec.order.id);
    }
    return { ok: false, attemptsLeft: Math.max(0, this.maxAttempts - rec.attempts), locked: rec.locked };
  }

  /**
   * Zone 1: a free nudge inside the circle around the current pin. Zone 3: a move into another township is
   * blocked with the courier's fee message. An order with no pin yet (Amber) can drop its first pin anywhere
   * in its township.
   */
  movePin(
    token: string,
    session: string,
    to: { lat: number; lng: number },
    options: { townshipOf?: (p: { lat: number; lng: number }) => string | null } = {},
  ): PinResult {
    const rec = this.get(token);
    if (!rec || this.expired(rec) || !this.verified(rec, session)) {
      return { allowed: false, reason: "not_verified", message: { en: "Enter the last 4 digits first", my: "ဖုန်းနံပါတ် နောက်ဆုံး ၄ လုံး အရင်ထည့်ပါ" } };
    }
    const townshipId = rec.order.fields.township?.id ?? null;
    const target = options.townshipOf?.(to) ?? null;
    if (townshipId && target && target !== townshipId) {
      const fee = this.fee.toLocaleString("en-US");
      const feeMy = toMyanmarDigits(fee);
      return {
        allowed: false,
        reason: "cross_township",
        message: {
          en: `Changing township needs a new delivery route. Extra fee: +${fee} MMK. Delivery moves to tomorrow.`,
          my: `မြို့နယ်ပြောင်းလျှင် ပို့ဆောင်ရေးလမ်းကြောင်း အသစ်လိုပါသည်။ ထပ်ဆောင်းကြေး +${feeMy} ကျပ်။ နောက်တစ်နေ့မှ ပို့ပါမည်။`,
        },
      };
    }
    if (rec.center && distanceMeters(rec.center, to) > this.radius) {
      return {
        allowed: false,
        reason: "outside_radius",
        message: {
          en: `You can move the pin up to ${this.radius} m. Contact the shop for a bigger change.`,
          my: `ပင်ကို ${toMyanmarDigits(String(this.radius))} မီတာအတွင်းသာ ရွှေ့နိုင်ပါသည်။ ပိုဝေးပါက ဆိုင်ကို ဆက်သွယ်ပါ။`,
        },
      };
    }
    const pin: Location = { lat: to.lat, lng: to.lng, townshipId, source: "buyer" };
    rec.pin = pin;
    rec.center ??= pin;
    return { allowed: true, pin };
  }

  respond(token: string, session: string, response: BuyerResponse): { ok: true } | { ok: false; error: string } {
    const rec = this.get(token);
    if (!rec || this.expired(rec) || !this.verified(rec, session)) return { ok: false, error: "not_verified" };
    if (response.action === "reschedule" && !response.window) return { ok: false, error: "window_required" };
    rec.response = { ...response, note: response.note?.slice(0, 280) };
    if (rec.response.note === undefined) delete rec.response.note;
    return { ok: true };
  }

  markDelivered(token: string): void {
    const rec = this.get(token);
    if (rec) rec.deliveredAt = this.now();
  }

  private url(token: string) {
    return `${this.baseUrl}/track/${token}`;
  }

  private get(token: string) {
    return this.links.get(token);
  }

  private expired(rec: LinkRecord) {
    return rec.deliveredAt !== null && this.now() > rec.deliveredAt + DAY;
  }

  private verified(rec: LinkRecord, session?: string) {
    return !rec.locked && session !== undefined && rec.sessions.has(session);
  }
}

function toMyanmarDigits(s: string): string {
  return s.replace(/\d/g, (d) => String.fromCharCode(0x1040 + Number(d)));
}
