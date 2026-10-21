import { toUnicode } from "./encoding.ts";
import { extractName, extractPayment, extractPhones, extractStreet } from "./rules.ts";
import { matchTownships } from "./townships.ts";
import { redactForAi } from "./redact.ts";
import { splitOrders } from "./split.ts";
import { triage } from "./triage.ts";
import { vagueTokens } from "./vague.ts";
import { validateAiOutput } from "./ai/schema.ts";
import type { AddressExtractor, AiAddressFields } from "./ai/types.ts";
import type { Geocoder } from "./places.ts";
import type { AiReport, FieldName, FieldSource, Highlight, Location, OrderFields, ParsedOrder } from "./order.ts";

export interface ParserDeps {
  extractor: AddressExtractor;
  geocoder: Geocoder;
}

const NO_AI: AiAddressFields = { landmark: null, street: null, floorUnit: null, instructions: null, vaguePhrases: [] };

/** Parses one order: Layer 0 encoding, Layer 1 rules, Layer 2 dictionary, Layer 3 AI, then triage. */
export async function parseOrder(raw: string, deps: ParserDeps, id: string = crypto.randomUUID()): Promise<ParsedOrder> {
  const { text, wasZawgyi } = toUnicode(raw);

  const phones = extractPhones(text);
  const phone = phones.find((p) => p.valid) ?? phones[0] ?? null;
  const payment = extractPayment(text);
  const name = extractName(text);
  const rulesStreet = extractStreet(text);
  const townships = matchTownships(text);
  const addressText = redactForAi(text);

  const { fields: aiFields, report } = await runAi(addressText, deps.extractor);

  const sources: ParsedOrder["sources"] = {};
  const aiFilled: FieldName[] = [];
  const set = <K extends FieldName>(field: K, value: OrderFields[K], source: FieldSource) => {
    if (value === null) return value;
    sources[field] = source;
    if (source === "ai") aiFilled.push(field);
    return value;
  };

  const fields: OrderFields = {
    customerName: set("customerName", name?.value ?? null, "rule"),
    phone: set("phone", phone?.number ?? null, "rule"),
    phoneValid: phone?.valid ?? false,
    altPhones: phones.filter((p) => p !== phone).map((p) => p.number),
    township: set("township", townships[0]?.township ?? null, "dictionary"),
    houseNo: set("houseNo", rulesStreet.houseNo, "rule"),
    street: rulesStreet.street ? set("street", rulesStreet.street, "rule") : set("street", aiFields.street, "ai"),
    landmark: set("landmark", aiFields.landmark, "ai"),
    floorUnit: set("floorUnit", aiFields.floorUnit, "ai"),
    codAmount: set("codAmount", payment.codAmount, "rule"),
    prepaid: payment.prepaid,
    paymentMethod: payment.method ?? null,
    instructions: set("instructions", aiFields.instructions, "ai"),
  };

  const warnings: string[] = [];
  if (fields.codAmount === null) warnings.push("cod_missing");
  if (payment.ambiguous) warnings.push("cod_ambiguous");

  const order: Omit<ParsedOrder, "location" | "triage"> = {
    id,
    raw,
    text,
    wasZawgyi,
    addressText,
    fields,
    sources,
    aiFilled,
    townshipCount: townships.length,
    highlights: findHighlights(text, aiFields.vaguePhrases),
    ai: report,
    warnings,
  };
  return retriage(order, deps.geocoder, null);
}

async function runAi(addressText: string, extractor: AddressExtractor): Promise<{ fields: AiAddressFields; report: AiReport }> {
  if (!addressText) {
    return { fields: NO_AI, report: { ok: false, model: null, offline: false, dropped: [], error: "No address text" } };
  }
  try {
    const result = await extractor.extract(addressText);
    const { fields, dropped } = validateAiOutput(result.raw, addressText);
    return { fields, report: { ok: true, model: result.model, offline: result.offline, dropped } };
  } catch (err) {
    return { fields: NO_AI, report: { ok: false, model: null, offline: true, dropped: [], error: (err as Error).message } };
  }
}

/** Looks the order up on the map (unless someone already set a pin) and triages it again. */
export async function retriage(
  order: Omit<ParsedOrder, "location" | "triage">,
  geocoder: Geocoder,
  pinned: Location | null,
): Promise<ParsedOrder> {
  const { fields } = order;
  let location = pinned;
  if (!location) {
    const query = [fields.landmark, fields.street, order.addressText].filter(Boolean).join("\n");
    const place = await geocoder.locate(query, fields.township?.id ?? null);
    location = place ? { ...place, source: "dictionary" } : null;
  }
  return {
    ...order,
    location,
    triage: triage({
      phone: fields.phone ? { number: fields.phone, valid: fields.phoneValid } : null,
      township: fields.township,
      townshipCount: order.townshipCount,
      location,
    }),
  };
}

function findHighlights(text: string, aiPhrases: string[]): Highlight[] {
  const spans: Highlight[] = vagueTokens(text).map(({ text, start, end }) => ({ text, start, end }));
  for (const phrase of aiPhrases) {
    const start = text.indexOf(phrase);
    if (start !== -1) spans.push({ text: phrase, start, end: start + phrase.length });
  }
  spans.sort((a, b) => a.start - b.start || b.end - a.end);
  const merged: Highlight[] = [];
  for (const s of spans) {
    const last = merged[merged.length - 1];
    if (last && s.start < last.end) {
      if (s.end > last.end) merged[merged.length - 1] = { start: last.start, end: s.end, text: text.slice(last.start, s.end) };
    } else merged.push(s);
  }
  return merged;
}

export interface BatchOptions extends ParserDeps {
  /** How many orders are parsed (and sent to the AI) at once. */
  concurrency?: number;
}

/** Parses a pasted batch and yields each order as soon as it and every order before it is ready (NFR-01). */
export async function* parseBatchStream(block: string, options: BatchOptions): AsyncGenerator<ParsedOrder> {
  const limit = limiter(options.concurrency ?? 4);
  const tasks = splitOrders(block).map((chunk, i) => limit(() => parseOrder(chunk, options, `order-${i + 1}`)));
  for (const task of tasks) yield await task;
}

export interface BatchResult {
  orders: ParsedOrder[];
  summary: { total: number; green: number; amber: number; red: number; offline: boolean };
}

export async function parseBatch(block: string, options: BatchOptions): Promise<BatchResult> {
  const orders: ParsedOrder[] = [];
  for await (const order of parseBatchStream(block, options)) orders.push(order);
  return { orders, summary: summarize(orders) };
}

export function summarize(orders: ParsedOrder[]): BatchResult["summary"] {
  const count = (level: string) => orders.filter((o) => o.triage.level === level).length;
  return {
    total: orders.length,
    green: count("green"),
    amber: count("amber"),
    red: count("red"),
    offline: orders.some((o) => o.ai.offline),
  };
}

function limiter(max: number) {
  let active = 0;
  const queue: (() => void)[] = [];
  return async <T>(task: () => Promise<T>): Promise<T> => {
    if (active >= max) await new Promise<void>((resolve) => queue.push(resolve));
    active++;
    try {
      return await task();
    } finally {
      active--;
      queue.shift()?.();
    }
  };
}
