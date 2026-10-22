import { toAsciiDigits } from "./encoding.ts";

/**
 * Layer 1: deterministic rules. Phone numbers and money are only ever produced here, never by the AI.
 * All functions run on digit-normalized text; toAsciiDigits keeps string length, so spans map back
 * onto the caller's text unchanged.
 */

export interface Span {
  start: number;
  end: number;
}

export interface Phone extends Span {
  number: string;
  valid: boolean;
}

const PHONE_RE = /(?<![\d+])(?:\+?95[\s.-]?|0)9((?:[\s.-]?\d){3,9})(?!\d)/g;

export function extractPhones(text: string): Phone[] {
  const norm = toAsciiDigits(text);
  return [...norm.matchAll(PHONE_RE)].map((m) => {
    const rest = m[1].replace(/\D/g, "");
    return {
      number: `09${rest}`,
      valid: rest.length >= 7 && rest.length <= 9,
      start: m.index,
      end: m.index + m[0].length,
    };
  });
}

export type WalletMethod = "KBZPay" | "WavePay" | "AYA Pay";

export interface Payment {
  codAmount: number | null;
  prepaid: boolean;
  method?: WalletMethod;
  /** Several unlabelled amounts were found and the largest was taken. */
  ambiguous?: boolean;
  spans?: Span[];
}

const WALLETS: [RegExp, WalletMethod][] = [
  [/\b(?:kbz\s?pay|k\s?pay)\b/i, "KBZPay"],
  [/\bwave\s?(?:pay|money)?\b/i, "WavePay"],
  [/\baya\s?pay\b/i, "AYA Pay"],
];
const PAID_RE = /prepaid|(?<!\b(?:to\s+be|not|be|yet|unless)\s+)\bpaid\b(?!\s+(?:on|at|upon|when|after)\b)|(?:လွှဲ|ချေ|ရှင်း)(?:ထား)?ပြီး/i;
const LABEL_RE = /(?:cod|total|amount|ငွေ|စုစုပေါင်း|ကောက်ရန်|ကျသင့်ငွေ)\s*[:=-]?\s*$/i;
const LABEL_AFTER_RE = /^\s*(?:ks\b|kyats?\b|mmk\b|ကျပ်)?\s*(?:cod\b|ငွေချေ|ကောက်ရန်)/i;
const CURRENCY_RE = /^\s*(?:ks\b|kyats?\b|mmk\b|ကျပ်|ကျ)/i;
const UNIT_VALUES: Record<string, number> = { "သိန်း": 100_000, "သောင်း": 10_000, "ထောင်": 1_000 };
const UNIT_GROUP_RE = /(?:\d+(?:\.\d+)?\s*(?:သိန်း|သောင်း|ထောင်)\s*)+/g;
const UNIT_PART_RE = /(\d+(?:\.\d+)?)\s*(သိန်း|သောင်း|ထောင်)/g;
const NUMBER_RE = /(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?![\d,])/g;

interface Candidate extends Span {
  value: number;
  labelled: boolean;
}

/** Lines that only carry payment or item details; they never need to reach the AI. */
const PAYMENT_LINE_RE = /^\s*(?:cod|total|amount|ငွေ|စုစုပေါင်း|ကောက်ရန်|ကျသင့်ငွေ|item|order|ပစ္စည်း|ပို့ခ)\b|^\s*(?:cod|ငွေ|စုစုပေါင်း|ပစ္စည်း|ပို့ခ)/i;

export function isPaymentLine(line: string): boolean {
  return PAYMENT_LINE_RE.test(line) || PAID_RE.test(line) || WALLETS.some(([re]) => re.test(line));
}

export function extractPayment(text: string): Payment {
  const norm = toAsciiDigits(text);
  const wallet = WALLETS.find(([re]) => re.test(norm))?.[1];
  if (PAID_RE.test(norm)) {
    return { codAmount: 0, prepaid: true, ...(wallet ? { method: wallet } : {}) };
  }

  const phones = extractPhones(norm);
  const taken: Span[] = [...phones];
  const overlaps = (s: Span) => taken.some((t) => s.start < t.end && t.start < s.end);
  const labelledAt = (start: number) => LABEL_RE.test(norm.slice(Math.max(0, start - 16), start));
  const candidates: Candidate[] = [];

  for (const m of norm.matchAll(UNIT_GROUP_RE)) {
    const value = [...m[0].matchAll(UNIT_PART_RE)].reduce(
      (sum, part) => sum + Number(part[1]) * UNIT_VALUES[part[2]],
      0,
    );
    const span = { start: m.index, end: m.index + m[0].trimEnd().length };
    taken.push(span);
    candidates.push({ ...span, value: Math.round(value), labelled: labelledAt(m.index) });
  }

  for (const m of norm.matchAll(NUMBER_RE)) {
    const span = { start: m.index, end: m.index + m[0].length };
    if (overlaps(span)) continue;
    const currency = norm.slice(span.end).match(CURRENCY_RE);
    const labelled = labelledAt(m.index) || LABEL_AFTER_RE.test(norm.slice(span.end));
    if (!currency && !labelled) continue;
    candidates.push({
      start: span.start,
      end: span.end + (currency?.[0].length ?? 0),
      value: Number(m[0].replace(/,/g, "")),
      labelled,
    });
  }

  if (candidates.length === 0) return { codAmount: null, prepaid: false };
  const labelled = candidates.filter((c) => c.labelled);
  if (labelled.length > 0) {
    const pick = labelled[labelled.length - 1];
    return { codAmount: pick.value, prepaid: false, spans: candidates };
  }
  const values = new Set(candidates.map((c) => c.value));
  return {
    codAmount: Math.max(...values),
    prepaid: false,
    ...(values.size > 1 ? { ambiguous: true } : {}),
    spans: candidates,
  };
}

export interface NameMatch extends Span {
  value: string;
}

const NAME_LABEL_RE = /^\s*(?:name|customer|အမည်|နာမည်)\s*[:：-]?\s*(.+?)\s*$/i;
const HONORIFIC_RE = /^\s*((?:(?:Ma|Ko|Daw|U|Mg|Maung|Saya)\s+\S|(?:ကို|ဒေါ်|ဦး|မောင်)\S).*?)\s*$/;
const ORDER_NUMBER_RE = /^\s*(?:\d+|[၀-၉]+)\s*[.)။]\s*/;
const PLACE_WORD_RE = /လမ်း|road|street|\bst\b|မြို့နယ်|ရပ်ကွက်|township|\d/i;

/** Text before the first phone number or separator on a line, e.g. "Ma Thida" in "Ma Thida 09 7943 39082". */
function nameHead(line: string): { head: string; beforePhone: boolean } {
  const norm = toAsciiDigits(line);
  const phone = extractPhones(norm)[0];
  const cut = phone ? phone.start : norm.length;
  const head = line.slice(0, cut).split(/[,၊|/]|\s[-–]\s/)[0].trim();
  return { head, beforePhone: !!phone && line.slice(0, cut).trim() === head };
}
const PLAIN_NAME_RE = /^(?:[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,3}|[က-႟]+(?:\s+[က-႟]+){0,2})$/;

export function extractName(text: string): NameMatch | null {
  let offset = 0;
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const fullLine = lines[i];
    const line = fullLine.replace(ORDER_NUMBER_RE, "");
    const labelled = line.match(NAME_LABEL_RE);
    let value = labelled ? nameHead(labelled[1]).head || labelled[1] : undefined;
    if (!value) {
      const { head, beforePhone } = nameHead(line);
      const nextIsPhone = !!lines[i + 1] && extractPhones(lines[i + 1]).length > 0 && extractPhones(line).length === 0;
      if (head && head.length <= 40 && !PLACE_WORD_RE.test(head)) {
        const honorific = head.match(HONORIFIC_RE)?.[1];
        value = honorific ?? ((beforePhone || nextIsPhone) && PLAIN_NAME_RE.test(head) ? head : undefined);
      }
    }
    if (value) return { value, start: offset, end: offset + fullLine.length };
    offset += fullLine.length + 1;
  }
  return null;
}

export interface StreetMatch {
  houseNo: string | null;
  street: string | null;
}

const HOUSE_RE = /(?:အမှတ်|No\.?|#)\s*[([]?\s*(\d[\dA-Za-z/-]*)\s*[)\]]?/i;
const STREET_RES: [RegExp, (m: RegExpMatchArray) => string][] = [
  // A လမ်း followed by ဆုံ (junction) or ကြား (alley) is not a street name.
  [/(\d+)\s*လမ်း(?!ဆုံ|ကြား)/, (m) => `${m[1]} လမ်း`],
  [/[^\s၊,။\d]+လမ်း(?:မကြီး|မ)?(?!ဆုံ|ကြား)/, (m) => m[0]],
  [/\b\d+(?:st|nd|rd|th)?\s+Street\b/i, (m) => m[0]],
  [/\b[A-Z][A-Za-z']*(?:\s[A-Z][A-Za-z']*)*\s+(?:Road|Rd|Street|St)\b\.?/, (m) => m[0]],
];

export function extractStreet(text: string): StreetMatch {
  const norm = toAsciiDigits(text);
  const house = norm.match(HOUSE_RE);
  let best: { index: number; value: string } | null = null;
  for (const [re, pick] of STREET_RES) {
    const m = norm.match(re);
    if (m && m.index !== undefined && (!best || m.index < best.index)) best = { index: m.index, value: pick(m) };
  }
  return { houseNo: house?.[1] ?? null, street: best?.value ?? null };
}
