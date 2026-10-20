from enum import StrEnum


class UserRole(StrEnum):
    MERCHANT = "Merchant"
    DISPATCHER = "Dispatcher"
    RIDER = "Rider"
    ADMIN = "Admin"


class OrderStatus(StrEnum):
    DRAFT = "DRAFT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    ASSIGNED = "ASSIGNED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS = {
    OrderStatus.DRAFT: {OrderStatus.NEEDS_REVIEW, OrderStatus.CANCELLED},
    OrderStatus.NEEDS_REVIEW: {
        OrderStatus.AWAITING_CONFIRMATION,
        OrderStatus.CONFIRMED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.AWAITING_CONFIRMATION: {
        OrderStatus.NEEDS_REVIEW,
        OrderStatus.CONFIRMED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.CONFIRMED: {
        OrderStatus.NEEDS_REVIEW,
        OrderStatus.READY_FOR_DISPATCH,
        OrderStatus.CANCELLED,
    },
    OrderStatus.READY_FOR_DISPATCH: {
        OrderStatus.NEEDS_REVIEW,
        OrderStatus.ASSIGNED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.ASSIGNED: {
        OrderStatus.READY_FOR_DISPATCH,
        OrderStatus.OUT_FOR_DELIVERY,
        OrderStatus.CANCELLED,
    },
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED, OrderStatus.FAILED},
    OrderStatus.FAILED: {OrderStatus.NEEDS_REVIEW, OrderStatus.CANCELLED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}
MERCHANT_TRANSITIONS = {
    OrderStatus.NEEDS_REVIEW,
    OrderStatus.AWAITING_CONFIRMATION,
    OrderStatus.CONFIRMED,
    OrderStatus.CANCELLED,
}
EDITABLE_STATUSES = {
    OrderStatus.DRAFT,
    OrderStatus.NEEDS_REVIEW,
    OrderStatus.AWAITING_CONFIRMATION,
    OrderStatus.CONFIRMED,
    OrderStatus.READY_FOR_DISPATCH,
    OrderStatus.FAILED,
}
