"""Cash flow domain models."""

from dataclasses import dataclass
from typing import Optional

from app.shared.domain.value_objects.currency import Currency


@dataclass
class CashFlow:
    """Cash flow transaction (deposit, withdrawal, dividend, etc.)."""

    transaction_id: str
    type_doc_id: int
    date: str
    amount: float
    currency: Currency
    amount_eur: float
    transaction_type: Optional[str] = None
    status: Optional[str] = None
    status_c: Optional[int] = None
    description: Optional[str] = None
    params_json: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None
