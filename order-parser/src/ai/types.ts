/** What the AI layer fills in: only the parts rules cannot read (PRD Layer 3). */
export interface AiAddressFields {
  landmark: string | null;
  street: string | null;
  floorUnit: string | null;
  instructions: string | null;
  vaguePhrases: string[];
}

export interface AiRawResult {
  /** Unvalidated model output; always passed through validateAiOutput before use. */
  raw: unknown;
  model: string;
  /** True when a recorded or rule-based fallback answered instead of the live model. */
  offline: boolean;
}

/** The single interface every model sits behind, so the model can change without changing the product. */
export interface AddressExtractor {
  extract(addressText: string, options?: { signal?: AbortSignal }): Promise<AiRawResult>;
}

export class AiUnavailableError extends Error {
  override name = "AiUnavailableError";
}
