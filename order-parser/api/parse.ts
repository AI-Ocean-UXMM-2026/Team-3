import { createExtractor } from "../src/pipeline.ts";
import { parseBatchStream, summarize, type BatchResult } from "../src/parser.ts";
import { DictionaryGeocoder } from "../src/places.ts";
import type { ParsedOrder } from "../src/order.ts";

const MAX_CHARS = 100_000;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8" } });

/**
 * POST /api/parse with {"text": "<pasted orders>"}.
 * Returns {orders, summary, mode}; mode "offline-demo" means the UI shows the Offline demo mode badge.
 * Send "Accept: application/x-ndjson" to get one line per order as it is ready, then a summary line.
 */
export async function handleParse(req: Request, env: Record<string, string | undefined>): Promise<Response> {
  if (req.method !== "POST") return json({ error: "Use POST" }, 405);
  let text: unknown;
  try {
    text = ((await req.json()) as { text?: unknown }).text;
  } catch {
    return json({ error: "Body must be JSON" }, 400);
  }
  if (typeof text !== "string" || !text.trim()) return json({ error: "text is required" }, 400);
  if (text.length > MAX_CHARS) return json({ error: `text is over ${MAX_CHARS} characters` }, 413);

  const stream = parseBatchStream(text, { extractor: createExtractor(env), geocoder: new DictionaryGeocoder() });

  if (req.headers.get("accept")?.includes("application/x-ndjson")) {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      async start(controller) {
        const orders: ParsedOrder[] = [];
        for await (const order of stream) {
          orders.push(order);
          controller.enqueue(encoder.encode(JSON.stringify({ type: "order", order }) + "\n"));
        }
        const summary = summarize(orders);
        controller.enqueue(encoder.encode(JSON.stringify({ type: "summary", summary, mode: mode(summary) }) + "\n"));
        controller.close();
      },
    });
    return new Response(body, { headers: { "content-type": "application/x-ndjson; charset=utf-8" } });
  }

  const orders: ParsedOrder[] = [];
  for await (const order of stream) orders.push(order);
  const summary = summarize(orders);
  return json({ orders, summary, mode: mode(summary) });
}

const mode = (summary: BatchResult["summary"]) => (summary.offline ? "offline-demo" : "live");

// Netlify Functions (v2) default export and Vercel's named POST export.
export default (req: Request) => handleParse(req, process.env);
export const POST = (req: Request) => handleParse(req, process.env);
export const config = { path: "/api/parse" };
