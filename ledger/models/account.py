from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Account:
    institution: str          # "American Express", "Capital One", "Truist"
    name: str
    official_name: str
    account_type: str         # "credit", "depository", etc.
    current_balance: float
    available_balance: float | None
    currency: str