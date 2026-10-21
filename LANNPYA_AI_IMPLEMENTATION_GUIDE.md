# LannPya AI (လမ်းပြ) — Complete System Implementation & Technical Architecture Guide

> **AI-Native Last-Mile Delivery Middleware for Myanmar Social Commerce**
> *Built for the 2026 Buildathon — Solving the "Alleyway Gap" through AI Chat Ingestion, Customer Doorstep Pinning, and Rider Co-Pilot Navigation.*

---

## 1. Executive Summary & Problem Context

In Myanmar's bustling social commerce ecosystem (over 85% of online retail occurs via **Facebook Messenger**, **Viber**, and **Telegram**), deliveries routinely stall during the last 500 meters:
1. **Messy, Colloquial Addresses**: Buyers type unstructured Burmese text with vague landmarks (*"လှိုင်မြို့နယ်၊ သမိုင်းဘူတာရုံလမ်း၊ အဆွေတော်ကွန်ဒိုရှေ့၊ ၄ လွှာ (ညာဘက်အခန်း)"*) without postal codes or GPS pins.
2. **The "Alleyway Gap"**: Google Maps stops at the main road. Yangon's narrow lanes, walkups, and unnumbered buildings force delivery riders to make **3 to 5 phone calls per delivery**, resulting in high failure rates, wasted fuel, and friction.
3. **Privacy Exposure**: Customers hesitate to share private phone numbers with couriers, and riders struggle to verify exact gates.

**LannPya AI (လမ်းပြ)** provides a **3-sided middleware solution**:
1. **Dispatcher Hub**: Ingests raw chat messages, parses them with AI, and generates a secure zero-install micro-web link.
2. **Customer Pinning Studio (Micro-Web)**: A lightweight mobile web card opened directly inside Messenger/Viber—no app install, no passwords. The buyer verifies their phone's last 4 digits, drags their pin into their exact alleyway, and picks their visual gate photo.
3. **Rider Delivery Co-Pilot HUD**: Turn-by-turn navigation directly to the doorstep pin, gate photo cues, masked private voice relay calling, and instant COD remittance.
4. **Split-Screen Pitch Demo Mode**: A synchronized 30-second live demonstration mode designed specifically for Buildathon evaluation and judging.

---

## 2. Technology Stack & Technical Rationale

| Layer | Technologies Used | Purpose & Rationale |
| :--- | :--- | :--- |
| **Frontend Core** | **HTML5** & **Vanilla JavaScript (ES Modules)** | High-speed, lightweight, zero-overhead browser execution without heavy framework runtimes. |
| **Styling & Design System** | **Vanilla CSS3** | Custom design tokens, glassmorphism (`backdrop-filter`), editorial typography, responsive iOS phone frame simulation, and zero external CSS dependencies. |
| **Typography** | **Google Fonts**: *Plus Jakarta Sans*, *Newsreader* (editorial serif), *Inter*, and *Padauk* (Burmese script) | High visual polish matching international SaaS editorial aesthetics while providing native, crisp Burmese rendering. |
| **Map & Geospatial Engine** | **Leaflet.js (v1.9.4)** (Bundled locally via Vite) | High-performance interactive maps with custom SVG `divIcons`, `circleMarkers`, dynamic polyline routing, and geofencing. |
| **Map Tile Providers** | **CartoDB Voyager** + **CARTO Positron Fallback** (`subdomains: 'abcd'`) | Crisp, uncluttered vector-raster tiles optimized for Yangon streets with automatic fallback if primary CDN encounters network delays. |
| **Build Tool & Bundler** | **Vite (v6.4.4)** | Hot Module Replacement (HMR), instant local dev server, and clean tree-shaken static production bundle (`dist/`). |
| **Backend API Engine** | **FastAPI (Python 3.12)** & **Uvicorn** | High-performance asynchronous REST backend with OpenAPI/Swagger docs, Pydantic schemas, and instant JSON serialization. |
| **Database & Persistence** | **SQLite** & **Alembic** | Lightweight relational database tracking merchants, orders, state transitions (`DRAFT` → `NEEDS_REVIEW` → `READY_FOR_DELIVERY`), and GPS audit logs. |
| **Dual-Engine Architecture** | **Hybrid Resilience (FastAPI + Client Static Fallback)** | The frontend probes `http://127.0.0.1:8000/health`. If connected, it syncs with SQLite. If offline or deployed to Vercel, it runs self-contained mock states with zero disruption. |

---

## 3. Project Directory Structure

```text
Buildathon Product Ideas/
├── index.html                           # Single Page Application entrypoint (Semantic HTML5 layout)
├── package.json                         # Node.js project manifest & build scripts
├── package-lock.json                    # Exact dependency lockfile
├── vite.config.js                       # Vite bundler configuration
│
├── src/                                 # Frontend Application Source
│   ├── app.js                           # Core application logic, map engine, state, & event wiring
│   └── style.css                        # Design system, editorial themes, modals, & mobile phone styling
│
├── public/                              # Static Public Assets
│   └── assets/                          # Doorstep photos, merchandise images, & brand logos
│       ├── floral_dress.jpg             # Sample merchandise image
│       ├── yangon_doorstep_gate.jpg     # Green sliding iron gate visual cue
│       └── yangon_apartment_entrance.jpg# Apartment walkup staircase visual cue
│
├── scripts/                             # Utility & Verification Scripts
│   └── check_buttons.cjs                # Automated script verifying all button listeners & selectors
│
├── dist/                                # Production Bundle (Generated by npm run build)
│   ├── index.html                       # Optimized production HTML
│   └── assets/
│       ├── index-[hash].css             # Minified, purge-optimized CSS (60.8 kB)
│       └── index-[hash].js              # Bundled JavaScript with embedded Leaflet (206.7 kB)
│
├── backend_repo/                        # FastAPI Backend Subsystem (Kept untracked locally)
│   └── backend/
│       ├── app/                         # FastAPI core package
│       │   ├── main.py                  # API router mount & CORS middleware
│       │   ├── api/                     # REST endpoints (orders, confirmation, health)
│       │   ├── core/                    # App config, database session, security
│       │   ├── models/                  # SQLAlchemy ORM models (Order, Merchant, Location)
│       │   └── schemas/                 # Pydantic validation schemas
│       ├── migrations/                  # Alembic database migrations
│       ├── requirements-dev.lock        # Python locked dependencies
│       └── pyproject.toml               # Python project configuration
│
├── BRAINSTORMING_AND_VALUE_CANVAS.md    # Product value canvas & market validation notes
├── LANNPYA_AI_PRD_AND_MENTOR_SOLUTIONS.md # Full product requirements document (PRD)
└── LANNPYA_AI_IMPLEMENTATION_GUIDE.md   # This comprehensive technical guide
```

---

## 4. Key Workflows & Implementation Mechanics

```mermaid
flowchart TD
    A[Customer on Messenger/Viber] -->|Raw Burmese Message| B[Dispatcher Hub Triage]
    B -->|AI Extraction & Normalization| C[Generate Secure Micro-Web Link]
    C -->|Zero-Install Link via Chat| D[Customer Pinning Studio]
    D -->|1. Enter Phone Digits| E[Verify Recipient]
    E -->|2. Drag Pin into Alleyway| F[Doorstep Coordinate Confirmed]
    F -->|3. Pick Visual Gate Photo| G[Sync to Dispatcher & Backend]
    G -->|Real-Time Status Update| H[Rider Co-Pilot HUD]
    H -->|Google Maps Nav to Exact Pin| I[Arrive at Doorstep]
    H -->|Masked Voice Relay (No Phone Leaks)| J[Call Customer]
    I -->|Collect COD & Remit| K[Cash Stamp Animation & Delivery Complete]
```

### Stage 1: Dispatcher Hub & Burmese Address Ingestion
- **Channel Switching**: Allows dispatchers to toggle between `#facebook-messenger`, `#viber-shop-orders`, and `#phone-sms-leads`.
- **Burmese NLP Normalization Engine**:
  - Automatically identifies recipient name (*မအေးသန္တာ*), phone number (*09450012345*), and township (*Hlaing / လှိုင်မြို့နယ်*).
  - Isolates narrow alleyway landmarks (*အဆွေတော်ကွန်ဒိုရှေ့၊ ၄ လွှာ (ညာဘက်အခန်း)*) from the street address.
  - Computes Cash On Delivery (COD) amounts (*28,000 MMK*).
  - Calculates an initial AI confidence score (e.g., 68% for unverified chat addresses, rising to 99% upon customer doorstep pin).
- **Multi-Hub Fulfillment Selector**:
  - Supports multiple shipping origins:
    1. *Thida Online Boutique Main Hub* (Sayar San Road, Bahan)
    2. *Mingaladon Garment Supplier Factory #3* (Pyay Road)
    3. *Insein Regional Fulfillment Warehouse* (Lower Mingaladon Road)
  - Automatically recalculates route lines and waypoints from the active hub to all pending orders.
- **Shop Fulfillment Lead Time Calculator**:
  - Dynamically calculates delivery dates based on preparation time (e.g. 5 days prep time locks earliest delivery to Sunday, October 26).
- **Copy Reply Templates**:
  - Generates courteous, ready-to-paste Burmese Messenger replies directing buyers to verify their pin.

---

### Stage 2: Customer Pinning Studio (Micro-Web Experience)
- **Zero-Install Web App**:
  - Accessible via `/?view=customer&id=lp-8492` or through unique token URLs.
  - Requires no App Store / Play Store download, no account registration, and no passwords.
- **Buyer Identity Challenge (Phone Digit Inputs)**:
  - 4 interactive input boxes (`#digit-1` to `#digit-4`) with `inputmode="numeric"`.
  - Automatically jumps cursor focus to the next digit upon typing, handles backspacing smoothly, and unlocks the doorstep coordinates with a green verification seal.
- **500m Geofencing & Draggable Pinning**:
  - Renders a 500-meter dashed green circle around the AI's approximate township estimate.
  - Provides a draggable emerald pin marker (`📍 DOORSTEP`).
  - Allows customers to tap anywhere on the map or drag the pin into narrow alleys off the main road.
  - Displays a real-time offset indicator (e.g., *Offset: 45m from street center (Optimal)*).
- **Device GPS Integration**:
  - Dedicated "Use My Live GPS" button querying `navigator.geolocation.getCurrentPosition()`.
  - Includes a desktop simulation fallback placing the pin precisely at the residential doorstep.
- **Visual Gate & Building Style Cues**:
  - Interactive photo selection allowing customers to pick their building style:
    - *Green sliding iron gate (#46)*
    - *Apartment walkup staircase entrance*
    - *Red wooden door / tea stall landmark*
- **Delivery Time Windows & Instructions**:
  - Selectable chips (`10:00 - 12:00`, `14:00 - 16:00`, `16:00 - 18:00`).
  - Courier handling options (*"Call upon arrival"*, *"Leave with building security"*, *"Ring 4th floor bell"*).

---

### Stage 3: Rider Delivery Co-Pilot HUD
- **Multi-Stop Queue Switching**:
  - Rider HUD lists today's deliveries:
    - **Stop 1**: မအေးသန္တာ (Thamaing Station Rd, Hlaing) — *28,000 MMK COD*
    - **Stop 2**: ကိုကျော်ဇင် (Bargayar Rd, Sanchaung) — *45,000 MMK COD*
    - **Stop 3**: မဆုရည် (Ward 42, North Dagon) — *Paid via KPay*
  - Clicking any stop immediately switches context, updates the embedded route map, adjusts the COD collection total, and switches the gate photo.
- **Doorstep Visual Cue Card**:
  - Displays the exact photo selected by the customer so the rider can identify the building from the street without stopping to call.
- **1-Click External Navigation**:
  - Direct link opening Google Maps Navigation targeting the exact verified latitude/longitude coordinates (`https://maps.google.com/?q=lat,lng`).
- **Masked Voice Relay Dialer**:
  - Clicking `📞 Call (Masked)` launches an interactive mobile phone overlay (`#modal-masked-call`).
  - Simulates a telecom relay proxy (`09-400-LANNPYA`) where neither the rider nor customer sees each other's private phone number.
  - Includes an active timer, working mute toggle, speakerphone toggle, and red hangup button.
- **Delivery Exception Reporting**:
  - Clicking `⚠️ Report Issue` launches `#modal-rider-report`.
  - Courier can report issues (*Customer unreachable*, *Requested tomorrow delivery*, *Gate locked/dogs*, *Monsoon flood delay*).
  - Instantly logs an alert in the Dispatcher Queue table with amber warning tags.
- **Instant COD Collection & Cash Seal**:
  - Clicking `✓ Collect COD & Deliver` triggers a green stamp animation (*"28,000 MMK COD COLLECTED • Remitted to Thida Boutique"*), updates merchant balances, and turns status to delivered.

---

### Stage 4: Dispatcher Fleet Map & Queue Management
- **Central Yangon Interactive Fleet Map**:
  - Plots the active fulfillment hub, rider location, and all order pins.
  - Interactive popups allow inspecting order details or clicking *"Inspect in Triage"*.
  - Status color coding:
    - 🟡 **Amber**: Awaiting customer doorstep pin.
    - 🟢 **Green**: 99% verified doorstep pin (ready for rider).
    - 🔵 **Blue**: Successfully delivered & cash collected.
- **Queue Table with Live Filtering**:
  - Filter pills allow isolating orders:
    - `All (3)`
    - `🟡 Awaiting Pin (2)`
    - `🟢 Verified (1)`
    - `🔵 Delivered (0)`
  - Each row features an `Inspect & Pin` button loading that order directly into the Customer Pinning Studio.
- **Floating AI Dispatch Assistant**:
  - Bottom docked input allowing natural language triage queries (e.g. *"Show pending orders"*, *"Where is Van #4?"*).

---

### Stage 5: 1-Click Guided Pitch Story (Split-Screen Presentation Mode)
- **Synchronized Dual-View**:
  - Left pane: Dispatcher Fleet Map and normalized data card.
  - Right pane: Live mobile iPhone mockup running Customer Pinning or Rider HUD.
- **Automated 30-Second Story Demo for Judges**:
  - Clicking `✨ 1-Click Pitch Story Animation` executes an automated sequential narrative:
    1. **Step 1 (0s)**: Customer sends messy Burmese Messenger text.
    2. **Step 2 (3.5s)**: LannPya AI extracts names, address, landmarks, and COD.
    3. **Step 3 (7.0s)**: Customer receives and opens zero-install micro-web card.
    4. **Step 4 (10.5s)**: Customer drags pin 45 meters off the main road into their alleyway and selects their green gate photo.
    5. **Step 5 (14.0s)**: Customer confirms location; Dispatcher map turns green with 99% confidence.
    6. **Finale (17.5s)**: Rider navigates directly to the gate, delivers without calling, and remits COD cash.

---

## 5. Engineering Challenges Solved

### A. The "Empty / Blank Map" Issue
* **Root Cause**:
  1. Leaflet was initially loaded from an external CDN (`unpkg.com`) that failed or blocked in offline/firewalled networks.
  2. When Leaflet maps initialize inside containers with `display: none`, Leaflet calculates an internal viewport size of `0x0 px`. When toggled visible, Leaflet failed to query new dimensions, rendering no map tiles.
* **Engineering Fix**:
  1. Bundled Leaflet locally into the Vite bundle (`import L from "leaflet"; import "leaflet/dist/leaflet.css"`).
  2. Created `attachMapTiles(map)` using CartoDB Voyager with automatic failover to Positron tiles.
  3. Created `scheduleMapInvalidation(map)` which triggers `map.invalidateSize()` at progressive intervals (50ms, 150ms, 300ms, 600ms, 1000ms, 1800ms) on view switches and window resize.
  4. Added a CSS blueprint dotted grid background so containers never show an empty grey void.

### B. Unclickable Buttons & Dead-End Elimination
* **Root Cause**: Multiple interactive buttons (queue filters, sidebar inboxes, courier items, dialer controls, back buttons) lacked event listeners.
* **Engineering Fix**:
  - Implemented `setupQueueFilters()`, `setupSidebarInteractions()`, `setupModalHandlers()`, `setupCustomerPhoneDigits()`, and `setupRiderStopSwitching()`.
  - Verified with an automated Node test script (`scripts/check_buttons.cjs`) ensuring 100% of IDs and classes have active listeners.

### C. Zero-Deadlock Dual-Engine Backend Integration
* **Root Cause**: If the FastAPI Python server is stopped, network requests would fail and freeze the user interface.
* **Engineering Fix**:
  - Implemented non-blocking connection probing via `checkBackendConnection()` querying `GET /health` with a 2.5s timeout.
  - If the backend is running, it creates orders in SQLite, patches buyer locations, and generates real auth tokens.
  - If the backend is offline, the UI falls back gracefully to in-memory state transitions, displaying informational toasts.

---

## 6. Backend API Contracts (FastAPI & SQLite)

The FastAPI server runs on `http://127.0.0.1:8000`:

| Endpoint | Method | Headers / Auth | Description |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | None | Returns service health: `{"status": "ok", "service": "LannPya AI"}`. |
| `/api/orders` | `POST` | `X-Dev-Access-Token` | Creates a new order in `DRAFT` status from normalized Burmese text. |
| `/api/orders/{id}/status` | `PATCH` | `X-Dev-Access-Token` | Transitions order lifecycle (`DRAFT` → `NEEDS_REVIEW`). |
| `/api/orders/{id}/confirmation-link` | `POST` | `X-Dev-Access-Token` | Generates a time-bound secure confirmation token URL. |
| `/api/confirm/{token}/verify` | `POST` | None | Verifies buyer identity against phone's last 4 digits; returns JWT bearer token. |
| `/api/confirm/{token}/location` | `PATCH` | `Authorization: Bearer <jwt>` | Commits exact doorstep latitude and longitude coordinates to the database. |

---

## 7. Build, Run, and Deployment Instructions

### Running Locally

1. **Frontend Dev Server**:
   ```bash
   # From the workspace root
   npm run dev
   # Accessible at: http://localhost:3000
   ```

2. **Backend Daemon (Optional)**:
   ```bash
   # From backend_repo/backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   # Health check: http://127.0.0.1:8000/health
   # Swagger Docs: http://127.0.0.1:8000/docs
   ```

3. **Building for Production**:
   ```bash
   npm run build
   # Generates optimized assets in dist/ (206 kB JS bundle with embedded Leaflet)
   ```

4. **Deploying to Vercel**:
   - Zero-configuration static deployment: Simply import the repository on Vercel.
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - The application automatically uses its static fallback engine when deployed to serverless hosts.

---

*Authored for the Buildathon Product Ideas Project • LannPya AI (လမ်းပြ) Engineering Documentation.*
