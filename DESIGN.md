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
    fontFamily: "Big Shoulders Display, Noto Sans Myanmar, Impact, sans-serif"
    fontSize: "clamp(1.6rem, 1.2rem + 1.4vw, 2.2rem)"
    fontWeight: 750
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Public Sans, Noto Sans Myanmar, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.65
  burmese:
    fontFamily: "Noto Sans Myanmar, Public Sans, sans-serif"
    lineHeight: 1.8
  cash:
    fontFamily: "Big Shoulders Display, Noto Sans Myanmar, Impact, sans-serif"
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

Signpaint type (chosen 22 Oct): Big Shoulders Display, condensed capitals like painted Yangon shop signs, carries page titles, lane signs, counts and money only. Public Sans carries names, section headings and all running text. Spacing uses a 4 px scale (`--s1`…`--s14`): the dispatcher is dense (12–16 px card padding, 40 px buttons), the rider roomy (48 px buttons, 56 px main actions, 24 px between blocks), the buyer one calm column (20 px padding, 32 px between steps). A language switch shows English or Burmese, one at a time. Noto Sans Myanmar carries Burmese; use `lang="my"` when authoring new Burmese text. Burmese defaults to 1.8 line height, including lane labels. Compact rider action labels use their established 1.4–1.5 values and must be checked for stacked marks and wrapping.

Use sentence case, a clear heading scale and tabular numerals. Amounts display as `35,000 Ks`. Preserve exact amounts; do not round. Headings use -0.02em tracking; do not tighten Burmese text. Controls wrap rather than truncate essential actions. English remains visible beneath Burmese in rider dialogs for bilingual use.

Fonts currently load from Google Fonts with system fallbacks. First-time offline use can show fallback fonts; this is a prototype limitation, not proof of local font caching.

## Layout

Dispatcher content is centred within 1440px, with 32px horizontal padding on desktop and 18px below 760px. The Navy header holds three main destinations, More and the daily status sign. The compact prototype bar keeps role switching and offline/storage warnings visible. Clock and storage diagnostics, Test scenarios and the API workspace live in the Demo tools disclosure.

The board uses five lanes at a minimum of 200px each. At 760px and below, lanes stack. Lanes have an 18px desktop gutter and 24px between stacked mobile lanes; original Navy/Saffron sign fills, Paper cards and hairline border colours remain unchanged. The labelled proportional strip wraps without hiding its text. At 480px and below, navigation uses shorter English labels and the search field spans the toolbar.

Order checks and paste previews keep the original chat beside extracted fields, stacking at small sizes. The order check's third column moves below at 1100px. Manual entry and policy pages use a main form and a 260–320px save panel; below 900px, the save panel follows the fields in document order. Fields group by the decision the dispatcher is making.

Rider content is at most 520px wide. The next stop, landmark, cash and two delivery outcomes own the first task. Buyer and rider controls are at least 48px; Delivered and Can't deliver are at least 64px. Tables retain their columns in a labelled horizontal scroll container on narrow screens. Dialogs scroll within the viewport and use native focus containment and Escape handling.

## Elevation & Depth

Working surfaces are flat with a single 1px hairline. Board card hover has a small diffuse lift (`--lift`); menus and dialogs use stronger soft shadows because they float above the page. Avoid adding shadows to every working sheet. Focus is a 3px outline with a 2px offset; on Navy and in night mode, use Saffron.

## Shapes

Panels and signs use `--r: 10px`; buttons, inputs and board cards use `--r-sm: 8px`. Status tags use pill shapes. Edges stay 1px, including strong edges. The earlier surface brief's 2px painted edge and 6px corner description is superseded by the built system and the hairline decision in `HANDOFF-UI.md`.

## Components

### Signboards and counts

Navy sign, Cream name, Burmese above English, count aligned to the far edge. Needs you uses Saffron with Navy text. Empty lanes use the secondary Cream ground. Lane descriptions stay available to assistive technology without repeating below every sign. Cards show the order ID and exact cash with Ks, omitting the repeated delivery date. Card padding is 16px on desktop and 18px on mobile; status copy uses a lighter 500 weight to separate it from names. The board's only authored animation is the lane-count flip: 240ms, `cubic-bezier(.16,1,.3,1)`, transform and opacity only. Reduced motion disables it. No board or card entrance animations; navigation, disclosures and theme switching are immediate.

### Buttons and navigation

Primary actions are Navy with Cream text; secondary actions use Paper with a strong hairline. Delivered uses Saffron. Hover changes the surface immediately; press moves a control by 1px without a transition. Keep visible focus and an explicit disabled state. The selected Inline navigation keeps the logo, destination tabs and status together at desktop widths. On phones the full LannPya wordmark stays beside the existing mark in the top row; tabs and status wrap below. Main navigation uses a Saffron underline for the current destination. Native details/summary supplies the More menu and optional sections.

### Working sheets and facts

Use a section heading, related fields or facts, and a specific next action. Routes present a rider and delivery day as a sentence, ordered stops, plain status words and reasons blocking dispatch. Cash close-out separates recorded cash, delivery counts, returns and the physical handover. Empty states explain how to begin.

### Forms and chat comparison

Every field has a visible label. Fields are at least 44px tall, at least 48px for buyers and riders, and use a 2px input focus outline. Original chats remain editable in paste previews; interpretation appears in a definition list with missing fields stated explicitly. Duplicate warnings require a deliberate import choice. The order check preserves its original three-column layout, field order and bordered action panels. Order ID, delivery date and time sit on a dedicated metadata line. Labels, status sentences and action copy use lighter weights and more line spacing; no form fields or action panels are hidden for this refinement. Preserve all form IDs, field names and `data-action` values when styling.

### Dialogs

Use an action-specific title and save label. Rider title, key field labels and submit/cancel actions put Burmese above English. Native `<dialog>` provides modal focus containment; `aria-labelledby` points to its title. Cash dialogs ask for the amount physically counted; a differing amount requires a reason. Cancelling preserves workflow state. The existing two-second Delivered undo remains intact.

The project owner approved the current Burmese UI inventory on 21 October 2026, recorded against source commit `6b800c48741ec3973378253a1b0b92ae573167d6` in `BURMESE-REVIEW.md`. Future Burmese wording changes need a new review; automated checks are not language approval.

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

## Motion (added 22 Oct 2026)

Motion lives in `frontend/css/motion.css`. Tokens: `--ease-out: cubic-bezier(.23,1,.32,1)` for entering and leaving, `--ease-in-out: cubic-bezier(.77,0,.175,1)` for movement on screen, `--ease-drawer: cubic-bezier(.32,.72,0,1)` for sheets. Only transform, opacity and clip-path animate. Nothing starts from `scale(0)`. Hover effects sit behind `(hover:hover) and (pointer:fine)`. Reduced motion keeps the fades that explain a change and drops travel.

- **Buttons:** press is `scale(.97)` over 140ms. Saving buttons show three dots, then a tick. A wrong password or PIN shakes the form once.
- **Sign-in:** the logo builds once on load (loop, handle, parcel, dots, pin), about 900ms in total. The motto **လိပ်စာလည်းမှန် အချိန်လည်းမှန်** / "Right address, right time." sits under the wordmark and always shows both languages. Rider sign-in puts Burmese first.
- **Read orders pop-up:** opens with a 260ms rise (a bottom sheet under 640px). Boxes stagger 40ms. Edit opens in place with a 240ms row expand. A saved box flashes a Saffron edge.
- **Accept alerts:** the dispatcher gets a toast. The buyer gets a text-message-style banner that drops from the top, can be swiped up, and hides after 7s.
- **Buyer road:** the LannPya mark rides along a dotted road from Hub to You. The wheels spin and the frame bobs only while the parcel is out. Position moves over 900ms in-out.
- **Map swap:** "See your rider on the map" grows a full-screen map out of the road card with a 380ms clip-path, and shrinks back over 300ms. The Road/Map pill or a downward drag/flick on the bottom card closes it. The rider's point is estimated from the stops left until rider GPS exists.
- **Language switch:** the pill slides 220ms and the page text fades in over 180ms.
