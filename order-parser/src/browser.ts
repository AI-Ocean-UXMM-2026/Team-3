import { toUnicode } from "./encoding.ts";
import { extractName, extractPayment, extractPhones, extractStreet } from "./rules.ts";
import { matchTownships } from "./townships.ts";
import { splitOrders } from "./split.ts";

/** What the no-build prototype reads from one pasted order. */
export interface RulesResult {
  /** Unicode text (Zawgyi lines converted). */
  text: string;
  wasZawgyi: boolean;
  phones: { number: string; valid: boolean }[];
  codAmount: number | null;
  prepaid: boolean;
  paymentMethod: string | null;
  /** Several unlabelled amounts were found, so codAmount is a guess. */
  ambiguousAmount: boolean;
  name: string | null;
  houseNo: string | null;
  street: string | null;
  /** Township ids in reading order. */
  townships: string[];
}

/**
 * Layers 0 to 2 only (encoding, rules, dictionary): synchronous and deterministic, nothing leaves the
 * browser. The AI layer stays behind the serverless route.
 */
export function parseRules(raw: string): RulesResult {
  const { text, wasZawgyi } = toUnicode(raw);
  const payment = extractPayment(text);
  const street = extractStreet(text);
  return {
    text,
    wasZawgyi,
    phones: extractPhones(text).map(({ number, valid }) => ({ number, valid })),
    codAmount: payment.codAmount,
    prepaid: payment.prepaid,
    paymentMethod: payment.method ?? null,
    ambiguousAmount: payment.ambiguous ?? false,
    name: extractName(text)?.value ?? null,
    houseNo: street.houseNo,
    street: street.street,
    townships: matchTownships(text).map((m) => m.township.id),
  };
}

export const VERSION = "0.1.0";
export { splitOrders, toUnicode };

/** The bundle (vendor/lannpya-order-parser.js) exposes this as window.LannPyaOrderParser. */
export const browserApi = { VERSION, parseRules, splitOrders, toUnicode };
