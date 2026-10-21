const SEPARATOR_RE = /\n[ \t]*(?:-{3,}[ \t]*)?\n/;
const NUMBERED_RE = /^\s*(?:(?:\d+|[၀-၉]+)\s*[.)။]|#\d+|order\s*\d+)/i;

/** Splits one pasted block into orders: blank lines, --- lines, or numbered orders written back to back. */
export function splitOrders(block: string): string[] {
  const chunks = block.replace(/\r\n?/g, "\n").split(SEPARATOR_RE);
  return chunks.flatMap((chunk) => {
    const orders: string[][] = [];
    for (const line of chunk.split("\n")) {
      if (orders.length === 0 || NUMBERED_RE.test(line)) orders.push([line]);
      else orders[orders.length - 1].push(line);
    }
    // A --- line between blank lines is left on its own; it is a separator, not an order.
    return orders.map((lines) => lines.join("\n").trim()).filter((o) => o.length > 0 && !/^-{3,}$/.test(o));
  });
}
