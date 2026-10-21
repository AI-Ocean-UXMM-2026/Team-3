import { extractPayment, extractPhones } from "./rules.ts";
import { findTownship, getTownship } from "./townships.ts";
import { retriage } from "./parser.ts";
import type { Geocoder } from "./places.ts";
import type { FieldName, Location, OrderFields, ParsedOrder } from "./order.ts";

export class CorrectionError extends Error {
  override name = "CorrectionError";
}

export type CorrectableField = Exclude<FieldName, "phoneValid" | "altPhones" | "prepaid" | "paymentMethod"> | "pin";

/**
 * One-tap dispatcher correction (HLR-13): applies the new value through the same rules, marks the field as
 * the dispatcher's (no sparkle), and re-triages. The AI is not called again. Returns a new order.
 */
export async function correctField(
  order: ParsedOrder,
  field: CorrectableField,
  value: string | number | { lat: number; lng: number },
  deps: { geocoder: Geocoder },
): Promise<ParsedOrder> {
  const fields: OrderFields = { ...order.fields };
  const pinned = order.location && order.location.source !== "dictionary" ? order.location : null;
  let pin: Location | null = pinned;

  if (field === "pin") {
    if (typeof value !== "object") throw new CorrectionError("A pin needs lat and lng");
    pin = { lat: value.lat, lng: value.lng, townshipId: fields.township?.id ?? null, source: "dispatcher" };
  } else if (field === "phone") {
    const [phone] = extractPhones(String(value));
    if (!phone) throw new CorrectionError(`Not a phone number: ${value}`);
    fields.phone = phone.number;
    fields.phoneValid = phone.valid;
  } else if (field === "township") {
    const township = getTownship(String(value)) ?? findTownship(String(value));
    if (!township) throw new CorrectionError(`Unknown township: ${value}`);
    fields.township = township;
  } else if (field === "codAmount") {
    const amount = typeof value === "number" ? value : extractPayment(`COD ${value}`).codAmount;
    if (amount === null) throw new CorrectionError(`Not an amount: ${value}`);
    fields.codAmount = amount;
    fields.prepaid = amount === 0 && fields.prepaid;
  } else {
    fields[field] = String(value).trim() || null;
  }

  const sourceField = field === "pin" ? null : field;
  return retriage(
    {
      ...order,
      fields,
      // A township the dispatcher chose settles any "several townships" doubt.
      townshipCount: field === "township" ? 1 : order.townshipCount,
      sources: sourceField ? { ...order.sources, [sourceField]: "dispatcher" } : order.sources,
      aiFilled: order.aiFilled.filter((f) => f !== field),
      warnings: field === "codAmount" ? order.warnings.filter((w) => !w.startsWith("cod_")) : order.warnings,
    },
    deps.geocoder,
    pin,
  );
}
