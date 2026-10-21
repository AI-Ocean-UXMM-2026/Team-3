# Handoff: LannPya Signboard UI overhaul

## Continuation status · 21 October 2026

The secondary dispatcher pages, plain dialog copy, rider night-mode coverage and built-system documentation are implemented. Read `DESIGN.md` for current tokens, components and responsive rules; `.impeccable/design.json` is its companion. Cream remains the pinned brand ground. All motion except the 240ms lane-count flip is immediate, including buyer pin changes.

`BURMESE-REVIEW.md` contains 49 distinct authored Burmese UI runs. The project owner volunteered as the native-language reviewer; approval is pending and the PR must remain draft until their review is recorded. This is not native-approved copy.

Validation: all 93 root tests and syntax checks pass. The API test helper now accepts Windows CRLF line endings. Fresh browser evidence is stored outside the repo; the supplied branch has no `screens` directory. The isolated three-variant route study also lives outside production code. The original handoff below remains as a record of the starting point.

Branch: `claude/project-thread-gcp93k` on `fightahackathon/lannpya-ai`, branched from `prototype`. No PR has been opened yet.
Run it by opening `index.html` (no build step). Run `npm test` to check it; 93 of 93 tests pass.

## What this is

This is a UI overhaul of the device-local prototype in the "Signboard" direction Arti chose. The look is Yangon's bilingual shop signs:

- Navy signs with cream lettering.
- Saffron only for "your move": the Needs you sign and the rider's Delivered button.
- Hairline edges, which Arti asked for. Don't bring back the 2px borders.
- Status is always an icon plus a plain word.

Pinned brand:

- Colours: Navy #16263A, Saffron #F0A032 (never as text on a light background), Saiq-ka Red #D23F2E (logo and map pin only), Cream #FFF5E4.
- Fonts: Inter (opsz 32) for headings, Manrope for body text, Noto Sans Myanmar for Burmese.

UI role names: Dispatcher, Buyer, Rider. The code still uses admin, customer and rider.

Read these first:

- `PRODUCT.md`: the product record, users, principles and accessibility target.
- `.impeccable/surfaces/index-html.md`: the direction contract (Impeccable).
- The UX reasoning, screen states, accessibility, Burmese fit, success measures and handoff spec are in the Claude Doc "LannPya intent and service blueprint".

## What changed

- `index.html` now loads only `signboard.css` plus the brand fonts. The old CSS files stay in the repo because `api.html` still uses them.
- `signboard.css` is the whole design system: tokens in `:root`, then shell, board, order check, buyer, rider, dialogs and mobile rules.
- `functional-app.js` (view layer only; workflow logic and every `data-action` and form id are unchanged):
  - `ICON` and `icon()`: one SVG icon set, which replaces the Unicode glyphs.
  - `WORDS`, `word()`, `REASON` and `pill()`: plain words for status codes and domain reasons.
  - `laneOf()` and `cardLine()`: map each order to five lanes (Needs you, Waiting on buyer, Ready to send, With rider, Delivered) and give each card one human line.
  - `boardView()` and `boardRows()`: the service board. It has a bilingual title, a labelled proportional strip, one toolbar row and lane signs with counts. The count "flips" when a lane changes.
  - `detailView()`: the order check. The buyer's original chat sits beside what LannPya read, with plain-language next steps.
  - `customerHome()`, `customerView()`, `customerForm()` and `initialLocationForm()`: the phone-first buyer link, with Burmese above English on the main buttons.
  - `riderView()`: next stop owns the screen. It shows a landmark sign, cash, read aloud and Maps, plus 64px Can't deliver and Delivered buttons.
  - The page copy was rewritten in plain language. Amounts now show as "Ks" instead of "MMK".
- `sw.js` caches the new files. The version is now 0.8.0.
- `assets/brand/` holds the brand marks from the final brand set.
- One test assertion changed with the copy: "Delivery stop · X" is now "Delivery stop: X" (screen-reader text).

## Still to do (in this order)

1. **Check the finish-review fixes I just made.** Look at the bilingual sign text size, the labelled strip, the toolbar row, the rider landmark on navy, the "Amount unclear" tag and the mobile nav at 390px. Then commit any tweaks.
2. **Secondary dispatcher pages** (`intakeView`, `routesView`, `closeoutView`, `linksView`, `exceptionsView`, `settingsView`, `manualView`): restyle them the way the order check was done.
   - The routes list still uses "A · B · C" meta strings and raw state words. Use `word()` and plain sentences.
   - In the paste preview, show each record side by side with what was read, the same way the order check does.
3. **Dialogs** (`orderDialog`, `cashDialog`, `deliveryDialog`, `failDialog`): rewrite the copy in the same plain voice, and put Burmese first on the rider's dialogs.
4. **Night mode** for riders (`body.night` in the CSS): look at it again after the landmark moved to a navy sign.
5. **Motion:** keep it to one moment, the sign count flip. The board must not get entrance animations.
6. **DESIGN.md:** write it from the built system (tokens, components, rules). This is Impeccable `document`/`extract`.
7. **Burmese copy:** a native speaker needs to review every Burmese string. Mine are drafts.
8. **PR:** open one from this branch into `prototype`, or into whichever branch Arti wants.

## Known decisions and flags

- The Impeccable detector flags the Cream page background as a generic-AI tell. It stays because it is the pinned brand colour; switching the ground to white paper is Arti's call.
- There is no van departure time in the data model. The header shows the Yangon clock and how many buyers haven't answered, not a countdown. Add a departure time to Hub policy if a countdown is wanted.
- Mockups of all three UI options, with notes, are on the "LannPya redesign mockups" canvas. Signboard is the chosen one.
- To make screenshots with data, seed a realistic morning in the browser console with `Workflow.createStore(localStorage)`. All names and amounts are synthetic.
