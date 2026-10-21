import type { Township } from "./townships.ts";
import type { Location } from "./order.ts";

export type Level = "green" | "amber" | "red";

export type ReasonCode =
  | "all_checks_passed"
  | "no_phone"
  | "invalid_phone"
  | "unknown_township"
  | "several_townships"
  | "place_in_other_township"
  | "location_vague";

export interface Reason {
  code: ReasonCode;
  en: string;
  my: string;
}

export interface TriageResult {
  level: Level;
  /** Icon name for the UI, so status never relies on colour alone (HLR-11). */
  icon: "check" | "warning" | "stop";
  label: { en: string; my: string };
  /** Where the order goes next (HLR-14, HLR-15). */
  route: "rider_queue" | "buyer_confirmation" | "dispatcher_hold";
  reasons: Reason[];
}

export interface TriageInput {
  phone: { number: string; valid: boolean } | null;
  township: Township | null;
  townshipCount: number;
  location: Location | null;
}

const LEVELS: Record<Level, Omit<TriageResult, "reasons">> = {
  green: { level: "green", icon: "check", label: { en: "Ready to dispatch", my: "ပို့ရန် အသင့်" }, route: "rider_queue" },
  amber: {
    level: "amber",
    icon: "warning",
    label: { en: "Confirm with buyer", my: "ဝယ်သူနှင့် အတည်ပြုရန်" },
    route: "buyer_confirmation",
  },
  red: { level: "red", icon: "stop", label: { en: "Held for dispatcher", my: "ဆိုင်းငံ့ထားသည်" }, route: "dispatcher_hold" },
};

/**
 * Confidence triage from rule checks only, never from the AI's own opinion (HLR-10).
 * Red: missing or broken phone, or unknown area. Amber: phone and township fine but the location is vague.
 * Green: valid phone, township matched, and a landmark, street or pin we can put on the map.
 */
export function triage(input: TriageInput): TriageResult {
  const red: Reason[] = [];
  if (!input.phone) red.push({ code: "no_phone", en: "No phone number found", my: "ဖုန်းနံပါတ် မတွေ့ပါ" });
  else if (!input.phone.valid) {
    red.push({ code: "invalid_phone", en: `Phone number ${input.phone.number} is incomplete`, my: "ဖုန်းနံပါတ် မပြည့်စုံပါ" });
  }
  if (!input.township) {
    red.push({ code: "unknown_township", en: "Township not recognised", my: "မြို့နယ် ရှာမတွေ့ပါ" });
  }
  if (red.length > 0) return { ...LEVELS.red, reasons: red };

  const township = input.township!;
  const amber: Reason[] = [];
  if (input.townshipCount > 1) {
    amber.push({ code: "several_townships", en: "More than one township is mentioned", my: "မြို့နယ် တစ်ခုထက် ပိုပါနေသည်" });
  }
  const loc = input.location;
  if (loc?.source === "dictionary" && loc.townshipId && loc.townshipId !== township.id) {
    const other = loc.townshipId.replace(/(^|-)(\w)/g, (_, dash: string, c: string) => (dash ? " " : "") + c.toUpperCase());
    amber.push({
      code: "place_in_other_township",
      en: `${loc.name} is in ${other}, not ${township.en}`,
      my: "နေရာနှင့် မြို့နယ် မကိုက်ညီပါ",
    });
  } else if (!loc) {
    amber.push({
      code: "location_vague",
      en: "Location is vague: no landmark or street we can put on the map",
      my: "တည်နေရာ မရှင်းလင်းပါ",
    });
  }
  if (amber.length > 0) return { ...LEVELS.amber, reasons: amber };

  return {
    ...LEVELS.green,
    reasons: [{ code: "all_checks_passed", en: "Phone, township and a mapped place found", my: "ဖုန်း၊ မြို့နယ်နှင့် နေရာ စစ်ပြီး" }],
  };
}
