# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Dispatcher** (called admin in the code): runs a small Yangon delivery hub or online shop's dispatch from a laptop at the counter, with Messenger open beside the app. Job: turn a morning of chat orders into checked addresses and rider routes before the vans leave at 9:00.
- **Buyer** (called customer in the code): receives a private link from the shop in Messenger or Viber and opens it on a low-end Android phone inside the chat app's browser. Job: confirm where and when to receive a cash-on-delivery parcel, in about a minute, with no sign-up.
- **Rider**: delivers from a motorbike with an Android phone in one hand or on a mount, outdoors in strong sun, sometimes offline. Job: find the next stop by landmark, collect the right cash, mark it delivered, hand over cash at close-out.

## Product Purpose

LannPya reads Burmese and English order messages pasted from chats, checks each address against the service area, gets buyers to confirm their own pin and time through a private link, and gives riders a clear stop-by-stop route with cash to collect. Success is riders on the road by 9:00 with addresses the buyers confirmed, first-attempt deliveries, and a cash close-out that matches.

## Positioning

Built for how Yangon orders actually arrive: unstructured Messenger text in Burmese (including Zawgyi) and English, landmark addresses, names without surnames, and cash on delivery. The buyer confirms their own location, so the shop stops chasing them in chat.

## Operating Context

- Orders arrive in Messenger as free text; the dispatcher pastes them in batches.
- Service area is Yangon townships; orders outside it are held with a reason.
- Vans leave at 9:00; silent buyers are decided by the dispatcher at 8:45 (Send as is or Hold). Nothing moves on its own.
- Buyers verify with the last 4 digits of their phone (3 tries) before the address is shown.
- Riders mark Delivered, record cash, and hand over to the hub at close-out.

## Capabilities and Constraints

- Static web prototype (index.html, plain JS and CSS, no build step); `npm test` must stay green.
- Order parser in `order-parser/`, bundled to `vendor/lannpya-order-parser.js`: Zawgyi conversion, Burmese phone and amount rules, 33-township dictionary.
- Works offline with local storage; queued actions send when back online.
- UI terms: Dispatcher, Buyer, Rider (chosen 21 October 2026); code keeps admin, customer, rider.
- Chosen UX (21 October 2026): live service board with five lanes (Needs you, Waiting on buyer, Ready to send, With rider, Delivered), a side-by-side order check showing the original chat beside parsed fields, a one-question-per-step buyer card, and a rider next-stop screen.
- Open: service area beyond Yangon; whether shops also use Viber; who reviews Burmese copy.

## Brand Commitments

- Name: LannPya. Final brand files in `/mnt/project-files/lannpya-brand/final/`.
- Colours: Lann Navy #16263A, Saffron #F0A032 (never as text on a light ground), Saiq-ka Red #D23F2E (logo and map pin only), Cream #FFF5E4.
- Type: Inter Display for headings, Manrope for body, Noto Sans Myanmar for Burmese.
- Status is always an icon plus a word; triage tones are separate from brand colours.
- Voice: plain, calm, bilingual where it matters (Burmese first on buyer and rider action buttons).

## Evidence on Hand

- PRD v2 (`LannPya_AI_PRD_v2.docx`), functional review (`FUNCTIONAL_REVIEW.md`), UX audit and intent doc (Claude Docs).
- No real customers, shops, testimonials or delivery numbers yet. All names and orders in mockups are synthetic.

## Product Principles

1. Nothing moves on its own: every send, hold and deadline decision is a tap by a person.
2. Show the reason, not the code: every flag says what is wrong and what to do.
3. Keep the original chat in view: parsed data is always checkable against what the buyer wrote.
4. One job per screen for buyers and riders.
5. Never lose work: drafts and offline actions are kept and sent later.

## Accessibility & Inclusion

WCAG 2.2 AA. Burmese line height about 1.8; 200% text size must not clip. Rider and buyer touch targets at least 48 px, Delivered and Can't deliver 64 px tall. Board fully usable by keyboard. Status never by colour alone.
