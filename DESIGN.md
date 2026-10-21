---
name: LannPya Signboard
description: Bilingual delivery tools inspired by Yangon's painted shop signs.
colors:
  navy: "#16263A"
  navy-secondary: "#24384F"
  navy-muted: "#C9D1DC"
  saffron: "#F0A032"
  saffron-soft: "#FBE3B8"
  brand-red: "#D23F2E"
  cream: "#FFF5E4"
  cream-secondary: "#F3EAD8"
  paper: "#FFFDF8"
  ink-secondary: "#4A5A70"
  line: "#D9CDB8"
  error: "#A8281C"
  error-background: "#FBE4E0"
  waiting: "#7A4F00"
  waiting-background: "#FCEBC4"
  success: "#1C6A45"
  success-background: "#DDF1E5"
  night-ground: "#0F1B2A"
  night-paper: "#1C2F46"
  night-muted: "#B6C5D8"
typography:
  heading:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "clamp(1.6rem, 1.2rem + 1.4vw, 2.2rem)"
    fontWeight: 750
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Manrope, Noto Sans Myanmar, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  burmese:
    fontFamily: "Noto Sans Myanmar, Manrope, sans-serif"
    lineHeight: 1.8
  cash:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "2.2rem"
    fontWeight: 750
    lineHeight: 1
    letterSpacing: "-0.03em"
rounded:
  panel: "10px"
  control: "8px"
spacing:
  tight: "8px"
  related: "12px"
  group: "16px"
  panel: "20px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.cream}"
    rounded: "{rounded.control}"
    padding: "8px 16px"
    height: "44px"
  button-delivered:
    backgroundColor: "{colors.saffron}"
    textColor: "{colors.navy}"
    rounded: "{rounded.control}"
    height: "64px"
  panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.navy}"
    rounded: "{rounded.panel}"
    padding: "18px 20px"
---

## Overview

**Creative North Star: "A sign you can read across the counter."**

LannPya is a working delivery tool for a dispatcher at a shop counter, a buyer opening a chat link, and a rider checking a phone outdoors. Navy signs, cream lettering and an occasional saffron action make the next job visible without filling the workspace with decoration. The cream ground is an intentional, pinned brand choice, retained despite a generic-background detector warning.

**Key Characteristics:**

- Bilingual signs with Burmese first where the buyer or rider acts.
- Calm working sheets with hairline edges and plain sentences.
- The original chat remains available beside the interpretation.
- A person decides every dispatch, hold, delivery and cash handover.

This document describes the device-local `index.html` implementation. `signboard.css` owns its tokens and components; `functional-app.js` owns the view markup. The API workspace uses its existing separate styles. Product constraints are recorded in `PRODUCT.md`; no departure countdown exists in the local data model.

## Colors

Use Navy for navigation, signboards and primary actions; Cream for the page ground and lettering on Navy; Paper for working surfaces. `--ink-2` provides secondary text. `--line`, `--edge` and `--edge-strong` separate content without heavy outlines.

**The Your Move Rule.** Saffron points to action or current position: Needs you, Delivered, active navigation and stop selection. Never use saffron text on a light ground. Saiq-ka Red is reserved for the brand mark and map pin; error text uses the separate darker `--bad` token.

Status tones are semantic: error, waiting and success each pair dark text with a light background and always include an SVG icon and a plain word. Colour alone does not explain status.

Night mode is explicitly selected in the rider view. It sets a dark page ground, dark working surfaces, cream foreground and blue-tinted secondary text. Inputs, select menus, queue rows, dialogs, the prototype bar and visible focus all participate. The landmark stays Navy with Cream lettering. Saffron Delivered retains Navy text. Switching themes is immediate.

## Typography

Inter at optical size 32 carries headings, sign counts and cash. Manrope carries English body text. Noto Sans Myanmar carries Burmese; use `lang="my"` when authoring new Burmese text. Burmese defaults to 1.8 line height; compact signs use their established 1.4–1.5 values and must be checked for stacked marks and wrapping.

Use sentence case, a clear heading scale and tabular numerals. Amounts display as `35,000 Ks`. Preserve exact amounts; do not round. Headings use -0.02em tracking; do not tighten Burmese text. Controls wrap rather than truncate essential actions. English remains visible beneath Burmese in rider dialogs because the Burmese is awaiting native review.

Fonts currently load from Google Fonts with system fallbacks. First-time offline use can show fallback fonts; this is a prototype limitation, not proof of local font caching.

## Layout

Dispatcher content is centred within 1440px, with 24px horizontal padding on desktop and 16px below 760px. The Navy header holds three main destinations, More and the daily status sign. The prototype role switcher scrolls horizontally without expanding the page.

The board uses five lanes at a minimum of 200px each. At 760px and below, lanes stack. The labelled proportional strip wraps without hiding its text. At 480px and below, navigation uses shorter English labels and the search field spans the toolbar.

Order checks and paste previews keep the original chat beside extracted fields, stacking at small sizes. The order check's third column moves below at 1100px. Manual entry and policy pages use a main form and a 260–320px save panel; below 900px, the save panel follows the fields in document order. Fields group by the decision the dispatcher is making.

Rider content is at most 520px wide. The next stop, landmark, cash and two delivery outcomes own the first task. Buyer and rider controls are at least 48px; Delivered and Can't deliver are at least 64px. Tables retain their columns in a labelled horizontal scroll container on narrow screens. Dialogs scroll within the viewport and use native focus containment and Escape handling.

## Elevation & Depth

Working surfaces are flat with a single 1px hairline. Board card hover has a small diffuse lift (`--lift`); menus and dialogs use stronger soft shadows because they float above the page. Avoid adding shadows to every working sheet. Focus is a 3px outline with a 2px offset; on Navy and in night mode, use Saffron.

## Shapes

Panels and signs use `--r: 10px`; buttons, inputs and board cards use `--r-sm: 8px`. Status tags use pill shapes. Edges stay 1px, including strong edges. The earlier surface brief's 2px painted edge and 6px corner description is superseded by the built system and the hairline decision in `HANDOFF-UI.md`.

## Components

### Signboards and counts

Navy sign, Cream name, Burmese above English, count aligned to the far edge. Needs you uses Saffron with Navy text. Empty lanes use the secondary Cream ground. The only authored animation is the lane-count flip: 240ms, `cubic-bezier(.16,1,.3,1)`, transform and opacity only. Reduced motion disables it. No board or card entrance animations; navigation, disclosures and theme switching are immediate.

### Buttons and navigation

Primary actions are Navy with Cream text; secondary actions use Paper with a strong hairline. Delivered uses Saffron. Hover changes the surface immediately; press moves a control by 1px without a transition. Keep visible focus and an explicit disabled state. Main navigation uses a Saffron underline for the current destination. Native details/summary supplies the More menu and optional sections.

### Working sheets and facts

Use a section heading, related fields or facts, and a specific next action. Routes present a rider and delivery day as a sentence, ordered stops, plain status words and reasons blocking dispatch. Cash close-out separates recorded cash, delivery counts, returns and the physical handover. Empty states explain how to begin.

### Forms and chat comparison

Every field has a visible label. Fields are at least 44px tall, at least 48px for buyers and riders, and use a 2px input focus outline. Original chats remain editable in paste previews; interpretation appears in a definition list with missing fields stated explicitly. Duplicate warnings require a deliberate import choice. Preserve all form IDs, field names and `data-action` values when styling.

### Dialogs

Use an action-specific title and save label. Rider title, key field labels and submit/cancel actions put Burmese above English. Native `<dialog>` provides modal focus containment; `aria-labelledby` points to its title. Cash dialogs ask for the amount physically counted; a differing amount requires a reason. Cancelling preserves workflow state. The existing two-second Delivered undo remains intact.

Burmese strings are drafts, including the inherited board and buyer copy. `BURMESE-REVIEW.md` carries the complete UI inventory and review protocol. Native-speaker approval is still required; automated checks are not language approval.

## Do's and Don'ts

- **Do** preserve Navy, Saffron, Saiq-ka Red and Cream in their assigned roles.
- **Do** use plain status words with an icon and a next step.
- **Do** show original evidence beside parsed fields.
- **Do** verify real controls at 390px, tablet and desktop widths, including night mode and enlarged text.
- **Do** describe local storage and queued actions honestly; replay is not server sync.
- **Don't** restore 2px card edges or replace the cream ground based solely on a detector warning.
- **Don't** use raw state codes or chains of dot-separated metadata in dispatcher task lists.
- **Don't** add entry animations to the service board or animate frequent navigation.
- **Don't** change workflow command names, form hooks, or field values while rewriting copy.
- **Don't** claim Burmese has native approval until a named reviewer signs off.
