import type { Township } from "./townships.ts";
import type { Place } from "./places.ts";
import type { Span, WalletMethod } from "./rules.ts";
import type { Dropped } from "./ai/schema.ts";
import type { TriageResult } from "./triage.ts";

/** Where a field's value came from. Only "ai" fields get the sparkle icon (FR-1.5). */
export type FieldSource = "rule" | "dictionary" | "ai" | "dispatcher";

/** The FR-1.2 order fields. */
export interface OrderFields {
  customerName: string | null;
  phone: string | null;
  phoneValid: boolean;
  altPhones: string[];
  township: Township | null;
  houseNo: string | null;
  street: string | null;
  landmark: string | null;
  floorUnit: string | null;
  codAmount: number | null;
  prepaid: boolean;
  paymentMethod: WalletMethod | null;
  instructions: string | null;
}

export type FieldName = keyof OrderFields;

export interface Location {
  lat: number;
  lng: number;
  townshipId: string | null;
  source: "dictionary" | "dispatcher" | "buyer";
  name?: string;
  kind?: Place["kind"];
  approx?: boolean;
}

export interface Highlight extends Span {
  text: string;
}

export interface AiReport {
  ok: boolean;
  model: string | null;
  offline: boolean;
  dropped: Dropped[];
  error?: string;
}

export interface ParsedOrder {
  id: string;
  /** The text as pasted. */
  raw: string;
  /** Unicode text; highlight spans point into this. */
  text: string;
  wasZawgyi: boolean;
  /** Exactly what was (or would be) sent to the AI. */
  addressText: string;
  fields: OrderFields;
  sources: Partial<Record<FieldName, FieldSource>>;
  /** Fields to mark with a sparkle. */
  aiFilled: FieldName[];
  townshipCount: number;
  location: Location | null;
  triage: TriageResult;
  /** Vague words to highlight for Amber orders (HLR-12). */
  highlights: Highlight[];
  ai: AiReport;
  warnings: string[];
}
