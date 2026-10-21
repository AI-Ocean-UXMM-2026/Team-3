import { extractName, extractPayment, extractPhones, isPaymentLine, type Span } from "./rules.ts";

/**
 * Strips the customer's name, phone numbers, money and item lines so only address text and delivery
 * notes reach the AI (HLR-06, NFR-06). Pure and dependency-light, so it runs in the browser.
 */
const PHONE_LABEL_RE = /^(?:ဖုန်း(?:နံပါတ်)?|ph(?:one)?|tel|mobile|call)\s*[:.-]?$/i;

export function redactForAi(text: string): string {
  const name = extractName(text);
  const lines: string[] = [];
  let offset = 0;
  for (const line of text.split("\n")) {
    const lineSpan = { start: offset, end: offset + line.length };
    offset += line.length + 1;
    if (name && name.start === lineSpan.start) continue;
    if (isPaymentLine(line)) continue;
    const cuts: Span[] = [...extractPhones(line), ...(extractPayment(line).spans ?? [])];
    lines.push(cutSpans(line, cuts));
  }
  return lines
    .map((l) => l.replace(/[ \t]{2,}/g, " ").replace(/^[\s,၊/-]+|[\s,၊/-]+$/g, ""))
    .filter((l) => l.length > 0 && !PHONE_LABEL_RE.test(l))
    .join("\n");
}

function cutSpans(text: string, spans: Span[]): string {
  let out = "";
  let at = 0;
  for (const s of [...spans].sort((a, b) => a.start - b.start)) {
    if (s.start < at) continue;
    out += text.slice(at, s.start);
    at = s.end;
  }
  return out + text.slice(at);
}
