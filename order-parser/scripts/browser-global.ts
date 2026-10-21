import { browserApi } from "../src/browser.ts";

// Entry for the IIFE bundle loaded by the prototype's index.html.
(globalThis as { LannPyaOrderParser?: typeof browserApi }).LannPyaOrderParser = browserApi;
