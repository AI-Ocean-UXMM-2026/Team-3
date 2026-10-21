import { toAsciiDigits } from "./encoding.ts";

export interface AliasEntry<T> {
  aliases: string[];
  value: T;
}

export interface AliasMatch<T> {
  value: T;
  alias: string;
  start: number;
  end: number;
}

const BURMESE_RE = /[က-႟]/;
const IGNORED_RE = /[\s​-‍﻿]/;
// Vowel signs, tone marks, asat and the stacker all extend the syllable they follow.
const isSyllableTail = (c: string | undefined) => c !== undefined && c >= "ါ" && c <= "ှ";
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Finds dictionary aliases in free text. Burmese aliases match with spaces and zero-width characters
 * ignored but never cut a syllable in half; Latin aliases match whole words, case-insensitively.
 * Overlaps resolve to the longest alias, and results come back in reading order.
 */
export function findAliases<T>(text: string, entries: AliasEntry<T>[]): AliasMatch<T>[] {
  const norm = toAsciiDigits(text);
  const compactIndex: number[] = [];
  let compact = "";
  for (let i = 0; i < norm.length; i++) {
    if (IGNORED_RE.test(norm[i])) continue;
    compact += norm[i];
    compactIndex.push(i);
  }
  const lower = norm.toLowerCase();

  const found: AliasMatch<T>[] = [];
  for (const { aliases, value } of entries) {
    for (const alias of aliases) {
      if (BURMESE_RE.test(alias)) {
        const needle = [...alias].filter((c) => !IGNORED_RE.test(c)).join("");
        for (let at = compact.indexOf(needle); at !== -1; at = compact.indexOf(needle, at + 1)) {
          const end = at + needle.length;
          if (isSyllableTail(compact[end]) || compact[at - 1] === "္") continue;
          found.push({ value, alias, start: compactIndex[at], end: compactIndex[end - 1] + 1 });
        }
      } else {
        const pattern = alias.toLowerCase().split(/\s+/).map(escapeRe).join("\\s*");
        for (const m of lower.matchAll(new RegExp(`(?<![a-z])${pattern}(?![a-z])`, "g"))) {
          found.push({ value, alias, start: m.index, end: m.index + m[0].length });
        }
      }
    }
  }

  found.sort((a, b) => b.end - b.start - (a.end - a.start) || a.start - b.start);
  const kept: AliasMatch<T>[] = [];
  for (const m of found) {
    if (!kept.some((k) => m.start < k.end && k.start < m.end)) kept.push(m);
  }
  return kept.sort((a, b) => a.start - b.start);
}
