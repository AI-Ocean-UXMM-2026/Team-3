// npm run demo [file]: parses the sample orders (or a file you pass) and prints the dispatcher view.
// Uses live Gemini Flash when GEMINI_API_KEY is set; otherwise runs in offline demo mode.
import { readFileSync } from "node:fs";
import { createExtractor } from "../src/pipeline.ts";
import { parseBatch } from "../src/parser.ts";
import { DictionaryGeocoder } from "../src/places.ts";

const file = process.argv[2] ?? new URL("../data/sample-orders.txt", import.meta.url);
const started = performance.now();
const { orders, summary } = await parseBatch(readFileSync(file, "utf8"), {
  extractor: createExtractor(process.env),
  geocoder: new DictionaryGeocoder(),
});
const ms = Math.round(performance.now() - started);

const ICON = { green: "✅ GREEN", amber: "⚠️  AMBER", red: "⛔ RED  " } as const;
for (const o of orders) {
  const f = o.fields;
  const ai = (name: string) => (o.aiFilled.includes(name as never) ? "✨" : "");
  console.log(`${o.id.padEnd(9)} ${ICON[o.triage.level]}  ${f.township?.en ?? "?"}${o.wasZawgyi ? "  (Zawgyi→Unicode)" : ""}`);
  console.log(`          phone ${f.phone ?? "-"}  ${f.prepaid ? `prepaid ${f.paymentMethod ?? ""}` : `COD ${f.codAmount ?? "?"}`}`);
  if (f.street) console.log(`          street ${f.street}${ai("street")}`);
  if (f.landmark) console.log(`          landmark ${f.landmark}${ai("landmark")}`);
  if (f.floorUnit) console.log(`          floor/unit ${f.floorUnit}${ai("floorUnit")}`);
  if (f.instructions) console.log(`          note ${f.instructions}${ai("instructions")}`);
  if (o.triage.level === "amber" && o.highlights.length) console.log(`          vague: ${o.highlights.map((h) => `«${h.text}»`).join(" ")}`);
  console.log(`          why: ${o.triage.reasons.map((r) => r.en).join("; ")}\n`);
}
const pct = Math.round((100 * summary.green) / summary.total);
console.log(`${summary.total} orders in ${ms} ms: ${summary.green} green (${pct}%), ${summary.amber} amber, ${summary.red} red`);
console.log(summary.offline ? "Mode: Offline demo mode (recorded / rule-based answers)" : "Mode: live AI");
