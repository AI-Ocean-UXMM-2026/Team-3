import recordings from "../data/recordings.json" with { type: "json" };
import { GeminiExtractor } from "./ai/gemini.ts";
import { ChainExtractor } from "./ai/chain.ts";
import { HeuristicExtractor, RecordedExtractor, type Recording } from "./ai/offline.ts";
import type { AddressExtractor } from "./ai/types.ts";

export const SAMPLE_RECORDINGS: Recording[] = recordings;

/**
 * The AI layer as the product uses it: live Gemini Flash when GEMINI_API_KEY is set, then the recorded
 * demo answers, then the no-AI heuristic. Anything but the live model marks results as offline demo mode.
 */
export function createExtractor(
  env: Record<string, string | undefined>,
  options: { fetch?: typeof fetch } = {},
): AddressExtractor {
  const live = env.GEMINI_API_KEY
    ? new GeminiExtractor({ apiKey: env.GEMINI_API_KEY, model: env.GEMINI_MODEL || undefined, fetch: options.fetch })
    : null;
  return new ChainExtractor([
    ...(live ? [live] : []),
    new RecordedExtractor(SAMPLE_RECORDINGS),
    new HeuristicExtractor(),
  ]);
}
