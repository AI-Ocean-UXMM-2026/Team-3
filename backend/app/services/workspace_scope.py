"""Account ownership shared by order reads and dispatcher operations.

The application has no multi-user hub membership model. Each hub login owns its
workspace. Merchant ownership and the immutable creation audit identify existing
orders without rewriting records or accepting a browser-supplied hub identifier.
"""

from sqlalchemy import or_, select

from app.db.models import DeliveryEvent, Order
from app.domain.lifecycle import UserRole


def order_scope(actor):
    if actor.role == UserRole.MERCHANT:
        return Order.merchant_id == actor.id
    created_by_account = (
        select(DeliveryEvent.id)
        .where(
            DeliveryEvent.order_id == Order.id,
            DeliveryEvent.event_type == "ORDER_CREATED",
            DeliveryEvent.event_metadata["actor_id"].as_string() == str(actor.id),
        )
        .exists()
    )
    return or_(Order.merchant_id == actor.id, created_by_account)
