import { AiUnavailableError, type AddressExtractor, type AiRawResult } from "./types.ts";

export { AiUnavailableError };

export const DEFAULT_GEMINI_MODEL = "gemini-flash-latest";
const BASE_URL = "https://generativelanguage.googleapis.com/v1beta";

export const SYSTEM_PROMPT = `You read Myanmar (Burmese) delivery addresses for a courier in Yangon.
The text is one order's address and delivery notes. Names, phone numbers and amounts were already removed.
Return JSON with:
- landmark: the place the buyer uses to describe the location (shop, pagoda, school, building), or null
- street: the street or road name, or null
- floor_unit: floor, building, room or unit details, or null
- instructions: delivery time or handling notes for the rider, or null
- vague_phrases: phrases that only say "near / behind / opposite / inside" something, so a rider could not find the exact door
Copy every value exactly as written in the text, in the original language. Never translate, add, or guess.
If something is not in the text, use null.`;

const RESPONSE_SCHEMA = {
  type: "OBJECT",
  properties: {
    landmark: { type: "STRING", nullable: true },
    street: { type: "STRING", nullable: true },
    floor_unit: { type: "STRING", nullable: true },
    instructions: { type: "STRING", nullable: true },
    vague_phrases: { type: "ARRAY", items: { type: "STRING" } },
  },
  required: ["landmark", "street", "floor_unit", "instructions", "vague_phrases"],
};

export interface GeminiOptions {
  apiKey: string;
  model?: string;
  timeoutMs?: number;
  fetch?: typeof fetch;
}

/** Layer 3: a current Gemini Flash model, called over REST with a JSON response schema. */
export class GeminiExtractor implements AddressExtractor {
  readonly model: string;
  private readonly apiKey: string;
  private readonly timeoutMs: number;
  private readonly fetch: typeof fetch;

  constructor(options: GeminiOptions) {
    this.apiKey = options.apiKey;
    this.model = options.model ?? DEFAULT_GEMINI_MODEL;
    this.timeoutMs = options.timeoutMs ?? 4000;
    this.fetch = options.fetch ?? globalThis.fetch;
  }

  /** Builds an extractor from GEMINI_API_KEY / GEMINI_MODEL, or returns null when no key is set. */
  static fromEnv(env: Record<string, string | undefined>): GeminiExtractor | null {
    if (!env.GEMINI_API_KEY) return null;
    return new GeminiExtractor({ apiKey: env.GEMINI_API_KEY, model: env.GEMINI_MODEL || undefined });
  }

  async extract(addressText: string, options: { signal?: AbortSignal } = {}): Promise<AiRawResult> {
    const timeout = AbortSignal.timeout(this.timeoutMs);
    const signal = options.signal ? AbortSignal.any([timeout, options.signal]) : timeout;
    let response: Response;
    try {
      response = await this.fetch(`${BASE_URL}/models/${this.model}:generateContent`, {
        method: "POST",
        signal,
        headers: { "content-type": "application/json", "x-goog-api-key": this.apiKey },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
          contents: [{ role: "user", parts: [{ text: addressText }] }],
          generationConfig: { temperature: 0, responseMimeType: "application/json", responseSchema: RESPONSE_SCHEMA },
        }),
      });
    } catch (err) {
      throw new AiUnavailableError(`Gemini request failed: ${(err as Error).message}`, { cause: err });
    }
    if (!response.ok) throw new AiUnavailableError(`Gemini returned HTTP ${response.status}`);

    const body = (await response.json()) as { candidates?: { content?: { parts?: { text?: string }[] } }[] };
    const text = body.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) throw new AiUnavailableError("Gemini returned no content");
    try {
      return { raw: JSON.parse(text), model: this.model, offline: false };
    } catch (err) {
      throw new AiUnavailableError("Gemini returned text that is not JSON", { cause: err });
    }
  }
}
