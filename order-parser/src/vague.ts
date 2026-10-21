/** Words that say where something is relative to a landmark instead of where it is. */
export const VAGUE_MARKERS = [
  "မျက်နှာချင်းဆိုင်",
  "နောက်ဘက်",
  "ဘေးနား",
  "အနီး",
  "နား",
  "ဘေး",
  "နောက်",
  "ရှေ့",
  "ထဲ",
  "opposite",
  "behind",
  "next to",
  "near",
  "around",
];

const TOKEN_RE = /[^\s၊။,]+/g;

export interface Token {
  text: string;
  start: number;
  end: number;
}

/** Tokens (words between spaces and Burmese punctuation) that contain a vague marker. */
export function vagueTokens(text: string): (Token & { marker: string })[] {
  const lower = text.toLowerCase();
  const out: (Token & { marker: string })[] = [];
  for (const m of lower.matchAll(TOKEN_RE)) {
    const marker = VAGUE_MARKERS.find((v) => m[0].includes(v));
    if (marker) out.push({ text: text.slice(m.index, m.index + m[0].length), start: m.index, end: m.index + m[0].length, marker });
  }
  // "next to" spans two tokens.
  for (const m of lower.matchAll(/next to/g)) {
    if (!out.some((t) => t.start <= m.index && m.index < t.end)) {
      out.push({ text: text.slice(m.index, m.index + 7), start: m.index, end: m.index + 7, marker: "next to" });
    }
  }
  return out.sort((a, b) => a.start - b.start);
}
