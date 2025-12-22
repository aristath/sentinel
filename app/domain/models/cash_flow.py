"""Cash flow domain model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CashFlow:
    """Cash flow transaction domain model."""
    transaction_id: str
    type_doc_id: int
    transaction_type: Optional[str]
    date: str
    amount: float
    currency: str
    amount_eur: float
    status: Optional[str]
    status_c: Optional[int]
    description: Optional[str]
    params_json: Optional[str]
    created_at: str
    updated_at: str
    id: Optional[int] = None  # Database primary key, None for new records
