import rabbit from "rabbit-node";
import myanmarTools from "myanmar-tools";

const detector = new myanmarTools.ZawgyiDetector();
const ZAWGYI_THRESHOLD = 0.95;

export interface UnicodeResult {
  text: string;
  wasZawgyi: boolean;
}

/** Layer 0: detect Zawgyi line by line and convert it to Unicode before anything else runs. */
export function toUnicode(input: string): UnicodeResult {
  let wasZawgyi = false;
  const lines = input.split("\n").map((line) => {
    if (detector.getZawgyiProbability(line) < ZAWGYI_THRESHOLD) return line;
    wasZawgyi = true;
    return rabbit.zg2uni(line);
  });
  return { text: lines.join("\n"), wasZawgyi };
}

const MM_ZERO = 0x1040;
const LETTER_WA = "ဝ";
const isDigit = (c: string | undefined) => c !== undefined && c >= "0" && c <= "9";
const isCombiningMark = (c: string | undefined) => c !== undefined && c >= "ါ" && c <= "ှ";

/** Myanmar digits to ASCII. The letter ဝ is often typed for ၀, so it counts as zero when it touches a digit. */
export function toAsciiDigits(input: string): string {
  const chars = [...input].map((c) => {
    const code = c.charCodeAt(0);
    return code >= MM_ZERO && code <= MM_ZERO + 9 ? String(code - MM_ZERO) : c;
  });
  let changed = true;
  while (changed) {
    changed = false;
    for (let i = 0; i < chars.length; i++) {
      if (chars[i] !== LETTER_WA || isCombiningMark(chars[i + 1])) continue;
      if (isDigit(chars[i - 1]) || isDigit(chars[i + 1])) {
        chars[i] = "0";
        changed = true;
      }
    }
  }
  return chars.join("");
}
