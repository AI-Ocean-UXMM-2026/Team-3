# Responsive browser results

| Viewport | Admin sections/forms | Customer verification/forms | Assigned rider/map | Dialogs |
| --- | --- | --- | --- | --- |
| 1440 x 900 | Passed | Passed | Passed | Passed |
| 1366 x 768 | Passed | Passed | Passed | Passed |
| 768 x 1024 | Passed | Passed | Passed | Passed |
| 390 x 844 | Passed | Passed | Passed | Passed |
| 360 x 740 | Passed | Passed | Passed | Passed |

Each size executes the five admin sidebar actions, creates a rider and order, verifies a
buyer, submits/approves a pin, prepares/dispatches a route, opens the assigned rider view
and opens/cancels the cash dialog. Assertions check body width against viewport width,
section navigation, departure-dialog bounds, visible cancellation controls and form actions.
No major layout defect requiring CSS changes was found. The missing success notice first
observed at tablet size was a shared controller defect, fixed without changing the design.

Screenshots include `admin-{home,orders,routes,hub-closeout,riders,order}-{width}.png`,
`customer-{width}.png`, `rider-assigned-{width}.png` and departure/delivery dialogs.
There are also intermediate empty-rider and error-state captures, identified by filename.
The JSON manifest records exact image dimensions; some pages use an internal scroll area,
so a full-page capture does not mean every scrollable panel is visible simultaneously.

Visual inspection included the small-mobile admin, buyer and cash-dialog captures and the
desktop rider capture. Burmese input/notes render without observed clipping in the tested
states. Maps are clearly labeled schematic; they are not Leaflet navigation or real GPS.

Remaining polish: compact role-switch/sidebar text and targets would benefit from a formal
touch/accessibility review. Small-screen admin navigation scrolls horizontally to reveal
all items. These tests use Chromium viewport sizes, not physical phones, actual touch
sensors, screen readers, every Burmese font installation or every possible text length.
