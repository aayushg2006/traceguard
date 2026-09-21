"""Synthetic order-status tool."""

import re
from typing import Any


ORDERS = {
    "ORD-1001": {"status": "in_transit", "eta": "2026-09-26", "customer_id": "CUST-1001"},
    "ORD-1002": {"status": "delivered", "eta": "2026-09-18", "customer_id": "CUST-1002"},
}


def get_order_status(order_id: Any) -> dict[str, Any]:
    if not isinstance(order_id, str) or not re.fullmatch(r"ORD-\d{4}", order_id):
        raise ValueError("order_id must look like ORD-1001")
    order = ORDERS.get(order_id)
    if order is None:
        return {"found": False, "order_id": order_id}
    return {"found": True, "order_id": order_id, **order}
