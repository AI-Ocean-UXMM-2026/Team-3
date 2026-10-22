# Rider route workflow

1. Dispatcher reviews the buyer pin/availability, receives the parcel at the hub,
   previews and explicitly commits a plan. Existing assignments remain fixed.
2. Dispatcher uses the existing route departure action. Optimization commit alone
   never starts a delivery.
3. Rider opens the existing Rider screen. The queue still comes from the protected
   rider-scoped backend endpoint; planned stops use their saved sequence within
   delivery-status priority. Legacy queues retain their prior window/sequence
   policy. A new panel shows the rider's own committed plan, geometry and static
   planned times, with SIMULATED/ROAD_STATIC and stale warnings.
4. Approved buyer-confirmed coordinates support an external Google Maps directions
   link; no private notes or phone numbers are placed in that URL. No API key is
   needed. Manually entered/unconfirmed coordinates remain explicitly unconfirmed;
   the existing conservative navigation gate is preserved.
5. Existing failure reasons, explicit COD confirmation, actual collected cash,
   completion and event-history operations remain unchanged. A completed stop
   disappears from the active queue but persists in delivery/workflow history.
6. Refresh polls the actual backend. Current queue details take precedence over a
   stale plan's estimates. Buyer changes continue through existing approval rules;
   pending proposals never silently update the rider pin.

Only the authorized rider's current active assignments appear in plan output.
Historical geometry is withheld if stops have been removed or reassigned, to
avoid leaking former buyers' coordinates. There is no continuous tracking,
background GPS permission, live traffic feed or automatic rerouting.
