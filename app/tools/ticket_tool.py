"""Synthetic support-ticket tools."""

import re
from typing import Any


TICKETS = {
    "TKT-1001": {"status": "open", "subject": "Unable to update delivery address", "customer_id": "CUST-1001"},
    "TKT-1002": {"status": "resolved", "subject": "Duplicate invoice question", "customer_id": "CUST-1002"},
}


def _require_id(value: Any, prefix: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(rf"{prefix}-\d{{4}}", value):
        raise ValueError(f"{prefix} identifier must look like {prefix}-1001")
    return value


def get_customer_ticket(ticket_id: Any) -> dict[str, Any]:
    ticket_id = _require_id(ticket_id, "TKT")
    ticket = TICKETS.get(ticket_id)
    if ticket is None:
        return {"found": False, "ticket_id": ticket_id}
    return {"found": True, "ticket_id": ticket_id, **ticket}


def create_support_ticket(customer_id: Any, subject: Any) -> dict[str, Any]:
    customer_id = _require_id(customer_id, "CUST")
    if not isinstance(subject, str) or not 3 <= len(subject.strip()) <= 120:
        raise ValueError("subject must be between 3 and 120 characters")
    ticket_id = "TKT-9001"
    return {"created": True, "ticket_id": ticket_id, "customer_id": customer_id, "subject": subject.strip(), "status": "open"}
