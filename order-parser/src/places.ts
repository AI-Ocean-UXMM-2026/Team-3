import { findAliases, type AliasEntry } from "./textMatch.ts";

export interface Place {
  name: string;
  kind: "landmark" | "road";
  townshipId: string;
  lat: number;
  lng: number;
  /** Coordinates are hand-placed approximations for the demo; verify before a pilot. */
  approx: boolean;
}

/** Anything that can turn address words into a point on the map. A real geocoder can replace the dictionary. */
export interface Geocoder {
  locate(text: string, townshipId: string | null): Promise<Place | null>;
}

type Row = [name: string, kind: Place["kind"], townshipId: string, lat: number, lng: number, aliases: string[]];

// Demo gazetteer: major Yangon landmarks and roads (one row per township a road runs through).
const ROWS: Row[] = [
  ["Junction Square", "landmark", "kamayut", 16.8166, 96.1285, ["ဂျန်ရှင်းစကွဲ"]],
  ["Hledan Centre", "landmark", "kamayut", 16.829, 96.1295, ["Hledan Center", "လှည်းတန်းစင်တာ"]],
  ["Yangon University", "landmark", "kamayut", 16.832, 96.135, ["ရန်ကုန်တက္ကသိုလ်"]],
  ["Sule Pagoda", "landmark", "kyauktada", 16.7747, 96.1588, ["ဆူးလေဘုရား"]],
  ["Bogyoke Market", "landmark", "pabedan", 16.7804, 96.1534, ["ဗိုလ်ချုပ်ဈေး"]],
  ["Junction City", "landmark", "pabedan", 16.7795, 96.1565, ["ဂျန်ရှင်းစီးတီး"]],
  ["Shwedagon Pagoda", "landmark", "bahan", 16.7983, 96.1497, ["ရွှေတိဂုံဘုရား"]],
  ["Kandawgyi Lake", "landmark", "bahan", 16.793, 96.165, ["Kandawgyi", "ကန်တော်ကြီး"]],
  ["Thuwunna Stadium", "landmark", "thingangyun", 16.823, 96.195, ["သုဝဏ္ဏအားကစားကွင်း"]],
  ["Ocean Tamwe", "landmark", "tamwe", 16.809, 96.174, ["Ocean", "အိုရှင်း"]],
  ["Ocean North Point", "landmark", "north-okkalapa", 16.9, 96.17, ["Ocean", "အိုရှင်း"]],
  ["Kaba Aye Pagoda", "landmark", "mayangon", 16.854, 96.148, ["ကမ္ဘာအေးဘုရား"]],
  ["Yangon Airport", "landmark", "mingaladon", 16.9073, 96.1332, ["ရန်ကုန်လေဆိပ်"]],
  ["Taw Win Center", "landmark", "dagon", 16.787, 96.1455, ["တော်ဝင်စင်တာ"]],
  ["Insein Market", "landmark", "insein", 16.889, 96.102, ["အင်းစိန်ဈေး"]],
  ["8 Mile Junction", "landmark", "mayangon", 16.864, 96.144, ["8 မိုင်လမ်းဆုံ"]],
  ["Pyay Road", "road", "kamayut", 16.82, 96.129, ["ပြည်လမ်း"]],
  ["Pyay Road", "road", "sanchaung", 16.803, 96.137, ["ပြည်လမ်း"]],
  ["Pyay Road", "road", "mayangon", 16.86, 96.14, ["ပြည်လမ်း"]],
  ["Kaba Aye Pagoda Road", "road", "bahan", 16.815, 96.156, ["ကမ္ဘာအေးဘုရားလမ်း"]],
  ["Kaba Aye Pagoda Road", "road", "yankin", 16.835, 96.155, ["ကမ္ဘာအေးဘုရားလမ်း"]],
  ["Kaba Aye Pagoda Road", "road", "mayangon", 16.845, 96.153, ["ကမ္ဘာအေးဘုရားလမ်း"]],
  ["Baho Road", "road", "sanchaung", 16.803, 96.128, ["ဗဟိုလမ်း"]],
  ["Insein Road", "road", "kamayut", 16.83, 96.125, ["အင်းစိန်လမ်း"]],
  ["Insein Road", "road", "hlaing", 16.845, 96.12, ["အင်းစိန်လမ်း"]],
  ["Hledan Road", "road", "kamayut", 16.8285, 96.13, ["လှည်းတန်းလမ်း"]],
  ["U Wisara Road", "road", "dagon", 16.795, 96.144, ["ဦးဝိစာရလမ်း"]],
  ["Bogyoke Aung San Road", "road", "pabedan", 16.78, 96.155, ["ဗိုလ်ချုပ်အောင်ဆန်းလမ်း"]],
  ["Anawrahta Road", "road", "latha", 16.777, 96.15, ["အနော်ရထာလမ်း"]],
  ["Waizayantar Road", "road", "thingangyun", 16.825, 96.198, ["ဝေဇယန္တာလမ်း"]],
  ["Waizayantar Road", "road", "south-okkalapa", 16.83, 96.19, ["ဝေဇယန္တာလမ်း"]],
  ["Kyaikkasan Road", "road", "tamwe", 16.81, 96.18, ["ကျိုက္ကဆံလမ်း"]],
  ["Thanthumar Road", "road", "thingangyun", 16.82, 96.185, ["သန်သုမာလမ်း"]],
];

export const PLACES: Place[] = ROWS.map(([name, kind, townshipId, lat, lng]) => ({
  name,
  kind,
  townshipId,
  lat,
  lng,
  approx: true,
}));

const ENTRIES: AliasEntry<Place>[] = ROWS.map((row, i) => ({ value: PLACES[i], aliases: [row[0], ...row[5]] }));

export class DictionaryGeocoder implements Geocoder {
  async locate(text: string, townshipId: string | null): Promise<Place | null> {
    const hits = findAliases(text, ENTRIES);
    // The same words can name places in several townships (an Ocean branch, a long road): keep every candidate
    // that shares the matched span, and prefer the one in the stated township.
    const candidates = hits.flatMap((hit) =>
      ENTRIES.filter((e) => e.aliases.includes(hit.alias)).map((e) => e.value),
    );
    return candidates.find((p) => p.townshipId === townshipId) ?? candidates[0] ?? null;
  }
}
