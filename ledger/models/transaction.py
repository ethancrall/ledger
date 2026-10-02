from dataclasses import dataclass
from datetime import datetime


@dataclass
class Transaction:
    transaction_id: str
    institution: str
    date: datetime
    merchant: str
    amount: float   # Plaid convention: positive = money out, negative = money in
    category: str