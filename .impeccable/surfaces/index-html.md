---
version: 1
slug: "index-html"
primary_target: "index.html"
related_targets: ["functional-app.js"]
---

# Surface brief: LannPya workspace (dispatcher, buyer, rider)

Scope: index.html and everything functional-app.js renders (dispatcher service board, order check, all dispatcher pages, buyer link pages, rider pages). Mode: Operate.

Audience and job: Dispatcher at a shop laptop clearing a morning batch of Messenger orders before vans leave; buyer on a low-end Android in Messenger's browser confirming address and time; rider on a motorbike finding the next stop and recording cash. Content is the live local workspace; no invented customers or numbers.

Constraints: plain HTML/CSS/JS, no build; all data-action names, form ids and workflow behaviour unchanged; npm test green; WCAG 2.2 AA; brand colours and fonts pinned in PRODUCT.md.

Unresolved: van departure time is not in the data model, so the header shows buyer answers and the clock rather than a countdown until a departure time exists in Hub policy.

## Direction contract

THESIS: The workspace reads like Yangon's bilingual painted shop signs: every lane, deadline and next stop is a sign you can read across the counter. It refuses the category's grey table with coloured status chips.

OWN-WORLD: Cream ground (#FFF5E4), Navy (#16263A) header and lane signs with cream lettering, Saffron (#F0A032) reserved for the one sign that is your move (Needs you, Delivered, the current step). White cards with a 2px Navy painted edge and 6px corners. Inter Display Black for names, counts and cash; Manrope body; Noto Sans Myanmar bold above English on every sign. Triage tones (crimson, amber-brown, green) only on status tags, always icon plus word.

STORY: The dispatcher sees how the batch stands in one glance (sign counts and a segment strip), opens the one card that needs them, checks the original chat beside what LannPya read, fixes it, and moves on. The buyer sees the shop's name and one question. The rider sees the next stop, its landmark and cash, and one big Delivered button.

FIRST VIEWPORT: Navy header (logo, three primary tabs, More menu, a saffron-edged sign with buyers not answered). Below it the 20-segment lane strip, a toolbar (search, filters, Paste orders, Add order), then five lanes side by side, each topped by a signboard (Burmese line, English name, painted count). Needs you is the saffron sign at far left. Cards carry name, cash, a status tag with icon and reason, and one action.

FORM: Painted shop signboard, candidate 5 of 7 on my list; seed:c7eef9c5e6f237bc. Raises: scale hierarchy (specimen), proportional segment strip (manual tabs), saffron means your move only (orienteering), one stop owns the rider screen (vertical feed). Signature interaction: when a card changes lane, the sign's count flips and the card settles into its new lane.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
