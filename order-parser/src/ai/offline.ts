import { toAsciiDigits } from "../encoding.ts";
import { vagueTokens } from "../vague.ts";
import { AiUnavailableError, type AddressExtractor, type AiRawResult } from "./types.ts";

export interface Recording {
  input: string;
  output: unknown;
}

const key = (s: string) => s.replace(/\s+/g, " ").trim();

/** Replays pre-recorded model answers so the live demo still works without internet (HLR-36). */
export class RecordedExtractor implements AddressExtractor {
  private readonly answers: Map<string, unknown>;

  constructor(recordings: Recording[]) {
    this.answers = new Map(recordings.map((r) => [key(r.input), r.output]));
  }

  async extract(addressText: string): Promise<AiRawResult> {
    const k = key(addressText);
    if (!this.answers.has(k)) throw new AiUnavailableError("No recording for this text");
    return { raw: this.answers.get(k), model: "recorded", offline: true };
  }
}

const FLOOR_RE = /\d+\s*ထပ်(?:တိုက်)?|\d+(?:st|nd|rd|th)?\s*floor|(?:အခန်း|room)\s*[\w/-]+/i;
const INSTRUCTION_RE = /နာရီ|မနက်|ညနေ|နေ့လယ်|ညပိုင်း|ဖုန်းဆက်|ထားခဲ့|\bcall\b|\bafter\b|\bbefore\b|\b[ap]m\b/i;

/** Last-resort extractor that uses simple patterns, so a parse never fails outright when the AI is down. */
export class HeuristicExtractor implements AddressExtractor {
  async extract(addressText: string): Promise<AiRawResult> {
    const vague = vagueTokens(addressText);
    const first = vague[0];
    const landmark = first ? first.text.replace(first.marker, "").trim() || null : null;
    const floor = toAsciiDigits(addressText).match(FLOOR_RE);
    const instructions = addressText
      .split("\n")
      .filter((l) => INSTRUCTION_RE.test(l))
      .pop()
      ?.trim();
    return {
      raw: {
        landmark,
        street: null,
        floor_unit: floor ? addressText.slice(floor.index!, floor.index! + floor[0].length) : null,
        instructions: instructions ?? null,
        vague_phrases: vague.map((t) => t.text),
      },
      model: "heuristic",
      offline: true,
    };
  }
}
