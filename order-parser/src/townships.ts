import { findAliases, type AliasEntry } from "./textMatch.ts";

export interface Township {
  id: string;
  en: string;
  my: string;
}

interface TownshipRow extends Township {
  aliases: string[];
}

// Yangon city townships plus the near suburbs most couriers serve (HLR-04). Mandalay is NEXT (HLR-08).
// Each row's aliases cover common English spellings, kinzi variants, and well-known areas inside it.
const ROWS: TownshipRow[] = [
  { id: "ahlone", en: "Ahlone", my: "အလုံ", aliases: [] },
  { id: "bahan", en: "Bahan", my: "ဗဟန်း", aliases: ["Kokkine", "ကုက္ကိုင်း"] },
  { id: "botahtaung", en: "Botahtaung", my: "ဗိုလ်တထောင်", aliases: [] },
  { id: "dagon", en: "Dagon", my: "ဒဂုံ", aliases: [] },
  { id: "dagon-seikkan", en: "Dagon Seikkan", my: "ဒဂုံဆိပ်ကမ်း", aliases: [] },
  { id: "dala", en: "Dala", my: "ဒလ", aliases: [] },
  { id: "dawbon", en: "Dawbon", my: "ဒေါပုံ", aliases: [] },
  { id: "east-dagon", en: "East Dagon", my: "အရှေ့ဒဂုံ", aliases: [] },
  { id: "hlaing", en: "Hlaing", my: "လှိုင်", aliases: [] },
  { id: "hlaing-tharyar", en: "Hlaing Tharyar", my: "လှိုင်သာယာ", aliases: ["Hlaingthaya", "Hlaing Thar Yar"] },
  { id: "insein", en: "Insein", my: "အင်းစိန်", aliases: [] },
  { id: "kamayut", en: "Kamayut", my: "ကမာရွတ်", aliases: ["Kamaryut", "Hledan", "လှည်းတန်း"] },
  { id: "kyauktada", en: "Kyauktada", my: "ကျောက်တံတား", aliases: ["Sule", "ဆူးလေ"] },
  { id: "kyimyindaing", en: "Kyimyindaing", my: "ကြည့်မြင်တိုင်", aliases: ["Kyeemyindaing"] },
  { id: "lanmadaw", en: "Lanmadaw", my: "လမ်းမတော်", aliases: [] },
  { id: "latha", en: "Latha", my: "လသာ", aliases: [] },
  { id: "mayangon", en: "Mayangon", my: "မရမ်းကုန်း", aliases: ["Mayangone", "8 Mile", "8 မိုင်"] },
  { id: "mingala-taungnyunt", en: "Mingala Taungnyunt", my: "မင်္ဂလာတောင်ညွန့်", aliases: ["Mingalar Taung Nyunt", "မဂ်လာတောင်ညွန့်"] },
  { id: "mingaladon", en: "Mingaladon", my: "မင်္ဂလာဒုံ", aliases: ["Mingalardon", "မဂ်လာဒုံ"] },
  { id: "north-dagon", en: "North Dagon", my: "မြောက်ဒဂုံ", aliases: [] },
  { id: "north-okkalapa", en: "North Okkalapa", my: "မြောက်ဥက္ကလာပ", aliases: [] },
  { id: "pabedan", en: "Pabedan", my: "ပန်းဘဲတန်း", aliases: [] },
  { id: "pazundaung", en: "Pazundaung", my: "ပုဇွန်တောင်", aliases: [] },
  { id: "sanchaung", en: "Sanchaung", my: "စမ်းချောင်း", aliases: ["San Chaung", "Myaynigone", "မြေနီကုန်း"] },
  { id: "seikkan", en: "Seikkan", my: "ဆိပ်ကမ်း", aliases: [] },
  { id: "shwepyitha", en: "Shwepyitha", my: "ရွှေပြည်သာ", aliases: ["Shwe Pyi Thar"] },
  { id: "south-dagon", en: "South Dagon", my: "တောင်ဒဂုံ", aliases: [] },
  { id: "south-okkalapa", en: "South Okkalapa", my: "တောင်ဥက္ကလာပ", aliases: [] },
  { id: "tamwe", en: "Tamwe", my: "တာမွေ", aliases: [] },
  { id: "thaketa", en: "Thaketa", my: "သာကေတ", aliases: [] },
  { id: "thanlyin", en: "Thanlyin", my: "သန်လျင်", aliases: [] },
  { id: "thingangyun", en: "Thingangyun", my: "သင်္ဃန်းကျွန်း", aliases: ["Thingungyun", "Thuwunna", "သုဝဏ္ဏ"] },
  { id: "yankin", en: "Yankin", my: "ရန်ကင်း", aliases: [] },
];

export const TOWNSHIPS: Township[] = ROWS.map(({ id, en, my }) => ({ id, en, my }));

const ENTRIES: AliasEntry<Township>[] = ROWS.map((row, i) => ({
  value: TOWNSHIPS[i],
  aliases: [row.en, row.my, ...row.aliases],
}));

export interface TownshipMatch {
  township: Township;
  start: number;
  end: number;
}

// "အင်းစိန်လမ်း" / "Insein Road" is a road that runs through other townships, not a township.
const ROAD_AFTER_RE = /^\s*(?:လမ်း|road\b|rd\b|street\b)/i;

/** Every distinct township named in the text, in reading order. */
export function matchTownships(text: string): TownshipMatch[] {
  const seen = new Set<string>();
  return findAliases(text, ENTRIES)
    .filter((m) => !ROAD_AFTER_RE.test(text.slice(m.end)))
    .filter((m) => !seen.has(m.value.id) && seen.add(m.value.id))
    .map((m) => ({ township: m.value, start: m.start, end: m.end }));
}

export function findTownship(text: string): Township | null {
  return matchTownships(text)[0]?.township ?? null;
}

export function getTownship(id: string): Township | null {
  return TOWNSHIPS.find((t) => t.id === id) ?? null;
}
