// Rebuilds data/recordings.json: the offline demo answers for the sample set (HLR-35, HLR-36).
// Each recording pairs the exact redacted text the AI would receive with the answer in sample-answers.json.
// With GEMINI_API_KEY set, pass --live to record real Gemini answers instead.
import { readFileSync, writeFileSync } from "node:fs";
import { splitOrders } from "../src/split.ts";
import { toUnicode } from "../src/encoding.ts";
import { redactForAi } from "../src/redact.ts";
import { GeminiExtractor } from "../src/ai/gemini.ts";

const root = new URL("../data/", import.meta.url);
const orders = splitOrders(readFileSync(new URL("sample-orders.txt", root), "utf8"));
const answers: unknown[] = JSON.parse(readFileSync(new URL("sample-answers.json", root), "utf8"));
if (answers.length !== orders.length) throw new Error(`${orders.length} orders but ${answers.length} answers`);

const live = process.argv.includes("--live") ? GeminiExtractor.fromEnv(process.env) : null;
if (process.argv.includes("--live") && !live) throw new Error("--live needs GEMINI_API_KEY");

const recordings = [];
for (const [i, order] of orders.entries()) {
  const input = redactForAi(toUnicode(order).text);
  const output = live ? (await live.extract(input)).raw : answers[i];
  recordings.push({ input, output });
}
writeFileSync(new URL("recordings.json", root), JSON.stringify(recordings, null, 2) + "\n");
console.log(`Wrote ${recordings.length} recordings${live ? ` from ${live.model}` : ""}`);
