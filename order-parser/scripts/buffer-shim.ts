// myanmar-tools decodes its model with Node's `new Buffer(data, "base64")`. Browsers have no Buffer,
// so the bundle gets this stand-in; it only needs base64 to bytes.
export class Buffer {
  constructor(data: string, encoding: "base64") {
    if (encoding !== "base64") throw new Error("Only base64 is supported");
    return Uint8Array.from(atob(data), (c) => c.charCodeAt(0)) as unknown as Buffer;
  }
}
