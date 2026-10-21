import { AiUnavailableError, type AddressExtractor, type AiRawResult } from "./types.ts";

/** Tries each extractor in order. Anything after the first counts as a fallback and is marked offline. */
export class ChainExtractor implements AddressExtractor {
  private readonly extractors: AddressExtractor[];

  constructor(extractors: AddressExtractor[]) {
    this.extractors = extractors;
  }

  async extract(addressText: string, options?: { signal?: AbortSignal }): Promise<AiRawResult> {
    const errors: unknown[] = [];
    for (const [i, extractor] of this.extractors.entries()) {
      try {
        const result = await extractor.extract(addressText, options);
        return i === 0 ? result : { ...result, offline: true };
      } catch (err) {
        errors.push(err);
      }
    }
    throw new AiUnavailableError("Every AI extractor failed", { cause: errors });
  }
}
