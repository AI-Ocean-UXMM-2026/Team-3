# LannPya AI: order parser, triage and buyer link

The AI and ordering logic from the LannPya AI PRD v2 and the High-Level Requirements (NOW items), built
test-first. It turns pasted Messenger/Viber orders written in casual Burmese into structured, triaged
deliveries. TypeScript, no framework, runs in Node 22.18+ and in the browser (except the Gemini call,
which belongs in the serverless route).

```bash
npm install
npm test            # 141 tests (vitest)
npm run typecheck
npm run demo        # parses data/sample-orders.txt and prints the dispatcher view
GEMINI_API_KEY=... npm run demo   # same, with live Gemini Flash
```

## Pipeline (rules first, AI only where rules stop)

| Layer | File | What it does | Req |
|---|---|---|---|
| Split | `src/split.ts` | One pasted block → orders (blank lines, `---`, or `1.` / `၁။` numbering) | HLR-01 |
| 0 Encoding | `src/encoding.ts` | Zawgyi detected per line (Google myanmar-tools) and converted (Rabbit); Myanmar digits → ASCII, `ဝ` typed for `၀` handled | HLR-02 |
| 1 Rules | `src/rules.ts` | Phones (`09…`, `+95 9…`, Burmese digits), COD (`ks`, `ကျပ်`, `MMK`, `သောင်း`/`ထောင်`/`သိန်း`), KBZPay/WavePay/AYA Pay prepaid, name, house no. and street. The AI never produces phone or money | HLR-03 |
| 2 Dictionary | `src/townships.ts`, `src/places.ts` | 33 Yangon townships with Burmese, English and area aliases (Hledan → Kamayut); demo gazetteer of landmarks and major roads behind a `Geocoder` interface | HLR-04 |
| Privacy | `src/redact.ts` | Removes name, phones, money and item lines; only address text reaches the AI. Pure, so it can run in the browser | HLR-06 |
| 3 AI | `src/ai/` | `AddressExtractor` interface. `GeminiExtractor` (REST, JSON response schema, temperature 0, 4 s timeout) fills landmark, street, floor/unit, instructions and vague phrases | HLR-05, NFR-07 |
| Validation | `src/ai/schema.ts` | Zod schema check, then every AI value must be a quote from the text it was given (made-up landmarks are dropped and logged) and must not look like a phone or amount | HLR-05 |
| Triage | `src/triage.ts` | Green / Amber / Red from rule checks only, with icon, English + Burmese label, reasons and route (rider queue / buyer link / dispatcher hold) | HLR-10, 11, 14 |
| Highlights | `src/vague.ts`, `src/parser.ts` | Spans of vague words (`နား`, `ဘေး`, `နောက်ဘက်`, …) in the original text | HLR-12 |
| Sparkle | `ParsedOrder.aiFilled` / `.sources` | Which fields came from the AI | FR-1.5 |
| Correction | `src/correct.ts` | Dispatcher fixes any field or drops a pin; same rules apply, sparkle removed, order re-triaged, no new AI call | HLR-13 |
| Buyer link | `src/buyerLink.ts` | Unguessable `/track/:token`, Messenger share text, view-only until last-4-digits check, lock after 3 tries, expiry 24 h after delivery, 500 m pin circle (fixed on the original pin), cross-township block with fee message, quick answers | HLR-15, 18–24 |
| Fallback | `src/ai/chain.ts`, `src/ai/offline.ts`, `src/pipeline.ts` | Live Gemini → recorded answers → no-AI heuristic; any fallback marks the result `offline` so the UI shows the Offline demo mode badge | HLR-36 |
| API | `api/parse.ts` | `POST /api/parse {text}` → `{orders, summary, mode}`; `Accept: application/x-ndjson` streams one line per order | NFR-01, NFR-08 |

`data/sample-orders.txt` is the 20-order demo set (one order arrives in Zawgyi). `data/recordings.json` holds
the offline answers; rebuild it with `npm run build:recordings` (add `--live` with a key to record real
Gemini answers). On the sample set: 13 Green (65%), 4 Amber, 3 Red.

## Browser bundle

`npm run build:browser` bundles the rules, dictionary and Zawgyi layers (`src/browser.ts`) into
`../vendor/lannpya-order-parser.js`, which sets `window.LannPyaOrderParser = { parseRules, splitOrders,
toUnicode }`. The prototype's `index.html` loads it before `workflow-domain.js`. `scripts/buffer-shim.ts`
stands in for Node's `Buffer`, which myanmar-tools uses to load its model. Commit the rebuilt bundle with
any change to `src/`.

## Configuration

- `GEMINI_API_KEY`: turns on the live model. Without it everything runs in offline demo mode.
- `GEMINI_MODEL`: defaults to `gemini-flash-latest`; set it to pin a specific Flash version.

## Not done yet

- The prototype uses the rules and dictionary layers only; the AI layer (`api/parse.ts`) is not wired to
  its screens yet.
- Buyer links are in memory; a serverless deployment needs a KV/database behind `BuyerLinks`.
- Place coordinates are hand-placed approximations (`approx: true`); verify before a pilot. Cross-township
  detection needs township boundaries, so `movePin` takes a `townshipOf` function to plug them in.
- A customer name with no label (`Name:`/`အမည်`) and no honorific (`Ko`, `Daw`, `ကို`, `ဒေါ်`…) is not
  detected, so it would reach the AI with the address.
- Mandalay and a fuller street dictionary are NEXT (HLR-08).
