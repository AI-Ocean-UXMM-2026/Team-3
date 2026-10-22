# Customer doorstep pinning

The existing buyer map supports click selection, marker dragging, coordinate
entry and device GPS after a button click. Permission denial, unavailable GPS and
timeouts leave manual selection usable. Geolocation requires a supported secure
context (HTTPS or browser-approved loopback); no background tracking is enabled.
GPS requests high accuracy with no cached fix and shows device-reported accuracy when available. Device coordinates can be inaccurate: displayed precision is not an accuracy
guarantee. The initial Yangon map centre is a browsing view, never a saved point.

The buyer opens a generated link, verifies the phone's final four digits and uses
the short-lived server-bound buyer authorization. Submission calls the existing
`PATCH /api/confirm/{token}/location`; coordinates and request ID are validated
server-side. Untrusted initial pins require acknowledgement and dispatcher review.
Pending proposals do not replace canonical order coordinates or enter routing.
Dispatcher approval persists coordinates and buyer-confirmation provenance.

The existing Haversine policy uses 500 metres only against a separately established
trusted `LocationReference`. A map centre, extracted landmark, AI estimate or
manually entered point is not such a reference. Same/cross-township decisions
cannot be inferred from missing boundary data; uncertain changes remain review
requests. Buyer confirmation or dispatcher approval does not establish independent
geospatial accuracy or automatically turn AMBER into GREEN.

Map tiles are optional: Leaflet works without API keys; tiles load on explicit
request with OpenStreetMap attribution. Without tiles, pin/geometry overlays remain
interactive but do not provide a street basemap. Tile failure leaves manual
coordinates available and displays a warning. No geocoding service was activated.

Existing browser coverage verifies real map clicks and dragging, granted/denied
GPS, timeout/unavailable GPS, invalid coordinates, location review and refreshed
persistence. The routing browser journey additionally uses actual buyer
confirmation/review before route planning and rider navigation.
