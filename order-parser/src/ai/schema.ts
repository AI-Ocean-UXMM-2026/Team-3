import { z } from "zod";
import { toAsciiDigits } from "../encoding.ts";
import type { AiAddressFields } from "./types.ts";

const text = z.string().nullable().optional();

/** The fixed JSON schema the model must return (snake_case, as sent to the model). */
export const aiOutputSchema = z.object({
  landmark: text,
  street: text,
  floor_unit: text,
  instructions: text,
  vague_phrases: z.array(z.string()).optional(),
});

export class AiOutputError extends Error {
  override name = "AiOutputError";
}

export type DropReason = "not_in_text" | "looks_like_phone_or_money";

export interface Dropped {
  field: keyof AiAddressFields;
  value: string;
  reason: DropReason;
}

const IGNORABLE_RE = /[\s၊။,.\-–:;()'"!?/]/g;
const squash = (s: string) => toAsciiDigits(s).replace(IGNORABLE_RE, "").toLowerCase();
const PHONE_OR_MONEY_RE = /\d{7,}|\d[\d,]*\s*(?:ks\b|kyats?\b|mmk\b|ကျပ်)/i;

/**
 * Validates model output against the schema, then checks every value against the text the model was given:
 * values must be quotes from that text (so the model cannot invent a landmark), and phone numbers or money
 * are refused because only rules may produce those (HLR-03).
 */
export function validateAiOutput(raw: unknown, sourceText: string): { fields: AiAddressFields; dropped: Dropped[] } {
  const parsed = aiOutputSchema.safeParse(raw);
  if (!parsed.success) throw new AiOutputError(`AI output does not match schema: ${parsed.error.message}`);

  const source = squash(sourceText);
  const dropped: Dropped[] = [];
  const check = (field: keyof AiAddressFields, value: string | null | undefined): string | null => {
    const v = value?.trim();
    if (!v) return null;
    if (PHONE_OR_MONEY_RE.test(toAsciiDigits(v).replace(/[\s-]/g, ""))) {
      dropped.push({ field, value: v, reason: "looks_like_phone_or_money" });
      return null;
    }
    if (!source.includes(squash(v))) {
      dropped.push({ field, value: v, reason: "not_in_text" });
      return null;
    }
    return v;
  };

  const o = parsed.data;
  return {
    fields: {
      landmark: check("landmark", o.landmark),
      street: check("street", o.street),
      floorUnit: check("floorUnit", o.floor_unit),
      instructions: check("instructions", o.instructions),
      vaguePhrases: (o.vague_phrases ?? []).map((p) => check("vaguePhrases", p)).filter((p): p is string => p !== null),
    },
    dropped,
  };
}
