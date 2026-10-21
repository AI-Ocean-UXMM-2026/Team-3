# Location and confidence integration policy

The server is authoritative for confidence and location provenance. The frontend can show
a map selection, but visual placement does not verify geospatial accuracy.

| State | Backend evidence | Recommended frontend label |
| --- | --- | --- |
| Unknown | No coordinates, `coordinate_status=MISSING`, or no matched location | “Pin not available” / “Address needs review”; no map destination |
| Approximate or unverified | Text parse or township match; no trusted address catalog; location verification `unverified` | “Address parsed; location not independently verified” |
| Buyer submitted | Buyer location request/history exists; initial pin has `REVIEW_REQUIRED` | “Buyer suggested a pin — dispatcher review pending” |
| Buyer confirmed | Approved/applied buyer update; queue may report `BUYER_CONFIRMED` coordinates | “Buyer confirmed pin”; do not imply external accuracy or boundaries were checked |
| Independently geospatially verified | Trusted reference plus injected trusted township boundary/location resolver; response verification metadata says verified | Use only the specific verification status/source returned by server; do not turn it into an accuracy percentage |

The buyer's initial coordinates do not overwrite trusted coordinates or prove the selected
township. A 500m movement can be automatically accepted only when the backend has a real
trusted reference and appropriate boundary policy. Without an original trusted coordinate,
there is no valid point from which to calculate/enforce 500m. Cross-township or unsupported
changes are stored for dispatcher review; client-supplied flags cannot bypass policy.

Current default catalog/boundaries are absent. GREEN requires the deterministic server rule
set and a trusted catalog; the default installation intentionally does not produce GREEN.
The backend returns categorical `GREEN`, `AMBER`, `RED`, validation reasons, source metadata,
`location_verification`, and queue `coordinate_status`/`location_verification`. It does not
return 68%, 99%, AI geocoding, map routing, building photos, or a verified geofence ring.

Visual guidance:

- Show confidence as a category plus plain-language server reasons, not a percent or gauge.
- Show coordinate provenance separately from order confidence and delivery status.
- Render buyer-selected pins as proposals while review is pending; visibly distinguish an
  unverified pin from an independent reference.
- Show a radius only when a real origin and server policy exist; otherwise don't imply a
  500m acceptance boundary.
- Use `navigation_ready` and the server-provided `navigation_url`; never construct a route
  from null/placeholder coordinates or assume the Maps link proves arrival.
- A new buyer pin does not automatically upgrade triage. Keep the server-returned confidence.

No backend location behavior was changed for the frontend guide's approximate map or 99%
illustration. Treat any such illustration as explicitly synthetic demo art, not order data.
