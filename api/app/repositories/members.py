"""In-memory member store — fondation Mutuelle OS (avant PG)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


@dataclass
class MemberRecord:
    cssa_id: str
    nss_id: str | None = None
    status: str = "PENDING_PAYMENT"
    payment_status: str = "unpaid"
    plan_id: str = "silver"
    currency: str = "EUR"
    stripe_checkout_id: str | None = None
    stripe_subscription_id: str | None = None
    paid_at: str | None = None
    subscriber_name: str = ""
    subscriber_country: str = ""
    meta: dict = field(default_factory=dict)


class MemberStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._by_cssa: dict[str, MemberRecord] = {}

    def upsert(self, record: MemberRecord) -> MemberRecord:
        key = record.cssa_id.upper()
        record.cssa_id = key
        with self._lock:
            self._by_cssa[key] = record
        return record

    def get(self, cssa_id: str) -> MemberRecord | None:
        with self._lock:
            return self._by_cssa.get(cssa_id.upper())

    def activate_from_stripe(
        self,
        *,
        cssa_id: str,
        checkout_session_id: str | None = None,
        subscription_id: str | None = None,
    ) -> MemberRecord | None:
        with self._lock:
            rec = self._by_cssa.get(cssa_id.upper())
            if rec is None and checkout_session_id:
                for candidate in self._by_cssa.values():
                    if candidate.stripe_checkout_id == checkout_session_id:
                        rec = candidate
                        break
            if rec is None:
                return None
            rec.status = "ACTIVE"
            rec.payment_status = "paid"
            rec.paid_at = datetime.now(timezone.utc).isoformat()
            if checkout_session_id:
                rec.stripe_checkout_id = checkout_session_id
            if subscription_id:
                rec.stripe_subscription_id = subscription_id
            return rec


store = MemberStore()
