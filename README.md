<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/assets/brand/mark-dark.svg">
    <img src="frontend/assets/brand/mark-light.svg" alt="LannPya logo: a delivery scooter with a parcel and location pin" width="160" height="160">
  </picture>
</p>

<h1 align="center">LannPya · လမ်းပြ</h1>

<p align="center">
  <strong>လိပ်စာလည်းမှန် အချိန်လည်းမှန်</strong><br>
  Right address, right time.
</p>

LannPya helps Myanmar shops acting as delivery hubs coordinate orders, buyer address confirmation, rider delivery, and cash handover.

## Judges: demo access and connection notes

Open the [live demo](https://lannpya-ai.vercel.app). If the website, sign-in, or database connection does not work on your network, try using a VPN and refresh the page.

When a verification-code screen appears, use **123456** or the generated test code shown on that screen.

Use **Fill Demo Credentials** on the Dispatcher or Rider sign-in page. You can add demo data, such as sample orders and buyer details, to test the full delivery flow. The demo uses a connected backend and Supabase database, so successfully saved demo data persists.

Dispatcher-shared customer links open the order ID and phone-number page. Enter the matching buyer phone number from your demo order to open its delivery edit page.

## Pitch video

Watch or download the [full-size LannPya pitch video](pitch%20videos/LannPya-full-video-1080p.mp4) from the root [`pitch videos/` folder](pitch%20videos/).

If you cannot access or play the video on GitHub, [watch the pitch video on Google Drive](https://drive.google.com/file/d/1dLavoPT6tBc1BnQ24pimZUomRcpYDGou/view?usp=sharing).

**Exact duration: 4 minutes 48.134 seconds (04:48.134).** Original 1080p MP4, **108,440,934 bytes**, preserved without compression using Git LFS. If GitHub does not preview the video, use its download button or see the [video download notes](pitch%20videos/README.md).

## Pitch deck

The [LannPya pitch deck](slides/LannPya%20pitch%20deck.pptx.pptx) is available in the root `slides/` folder for judges and reviewers.

## Illustrated workflow

See the [step-by-step workflow with 17 screenshots](docs/workflow/README.md) for order creation, buyer phone confirmation, dispatcher review, rider acceptance and delivery, and hub handover/close-out.

## What LannPya does

LannPya is a delivery management platform for Myanmar shops acting as delivery hubs, their buyers, and riders. Shops create orders, review buyer-confirmed delivery details, oversee rider assignments, and receive collected cash and returned parcels.

The shop's dispatcher can enter orders manually or paste order messages, check delivery details, and share a customer link. Buyers use their order reference and phone number to confirm their location, delivery time, and instructions. Riders receive delivery offers, follow route guidance, and record delivery results and cash collected.

## How the system works

1. **Create an order:** The shop's dispatcher enters buyer, parcel, address, and payment details.
2. **Confirm delivery details:** The buyer opens the shared link, enters their phone number, and confirms the delivery pin and preferred time.
3. **Review changes:** The shop's dispatcher resolves any buyer requests that need review.
4. **Assign a rider:** The system offers eligible deliveries to available riders. Rider acceptance starts delivery without another dispatcher dispatch step.
5. **Deliver and record:** The rider follows the route, delivers the parcel, and records the collection amount or delivery problem.
6. **Handover and close:** The rider hands over collected cash and returned parcels back to the shop. The shop's dispatcher checks the handover and closes the route.

## Repository structure

```text
Team-3/
├── frontend/       # Dispatcher, buyer, and rider web interfaces
├── backend/        # API, database models, migrations, and delivery services
├── docs/           # Illustrated workflow, setup, and technical documentation
├── slides/         # LannPya pitch deck
├── pitch videos/   # Full-size pitch video and download notes
├── tests/          # Browser and integration tests
├── scripts/        # Build and local startup tools
├── order-parser/   # Additional order-parsing research
└── README.md
```

## Frontend and backend

The responsive web interfaces support desktop and mobile use. The frontend connects to a FastAPI backend, with Supabase Auth for account sign-in and Supabase PostgreSQL for persistent data.

The backend manages order validation, buyer confirmation, dispatcher reviews, rider assignments, delivery status, cash collection, and route close-out. Address extraction uses rule-based parsing and township matching.

For technical details, see the [backend setup](backend/README.md), [deployment guide](docs/VERCEL_DEPLOYMENT.md), and [illustrated workflow](docs/workflow/README.md).
