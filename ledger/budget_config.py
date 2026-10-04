"""Loads and validates config.yaml — the YAML replacement for the Setup,
Accounts (manual rows), and Limits tabs from the old spreadsheet.

Usage:
    from ledger.budget_config import load_budget_config
    config = load_budget_config()
    config.category_type("Groceries")   -> "spend"
    config.categories_of_type("income") -> [Category(...), ...]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import yaml

from ledger.models.account import Account
from ledger.models.transaction import Transaction

CategoryType = Literal["spend", "offset", "income", "transfer"]
AccountKind = Literal["bank", "cash", "credit", "prepaid", "loan", "investment"]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


class ConfigError(ValueError):
    """Raised when config.yaml is malformed — fail loudly, not silently."""


@dataclass
class Category:
    name: str
    type: CategoryType


@dataclass
class ManualAccount:
    name: str
    kind: AccountKind
    starting_balance: float = 0.0
    credit_limit: float | None = None
    interest_rate: float | None = None
    interest_starts: date | None = None
    payoff_order: int | None = None
    autopay_day: int | None = None
    annual_fee: float | None = None


@dataclass
class ManualTransaction:
    date: date
    account: str            # must be a name in manual_accounts — the account charged
    amount: float            # same convention as Plaid: positive = money out, negative = money in
    category: str
    note: str = ""
    # Name of the account the money moved to, if this is a transfer. Can be
    # another manual account (credited automatically) or a Plaid-tracked
    # account (not credited here — Plaid's own sync already reflects it).
    transfer_to: str | None = None


@dataclass
class PayrollAssumptions:
    deferral_rate_401k: float = 0.0
    match_tier_1_rate: float = 0.0
    match_tier_1_pct: float = 0.0
    match_tier_2_rate: float = 0.0
    match_tier_2_pct: float = 0.0
    expected_net_pay_per_period: float | None = None


@dataclass
class ForecastAssumptions:
    minimum_cash_buffer: float = 0.0
    hsa_cash_floor: float = 0.0


@dataclass
class ContributionLimit:
    tax_year: int
    roth_ira_limit: float | None = None
    roth_401k_limit: float | None = None
    hsa_limit: float | None = None
    tax_filing_deadline: date | None = None


@dataclass
class BudgetConfig:
    tracker_start_date: date
    categories: list[Category] = field(default_factory=list)
    manual_accounts: list[ManualAccount] = field(default_factory=list)
    transactions: list[ManualTransaction] = field(default_factory=list)
    payroll: PayrollAssumptions = field(default_factory=PayrollAssumptions)
    forecast: ForecastAssumptions = field(default_factory=ForecastAssumptions)
    contribution_limits: list[ContributionLimit] = field(default_factory=list)

    def category_type(self, name: str) -> CategoryType:
        for cat in self.categories:
            if cat.name == name:
                return cat.type
        raise ConfigError(
            f"Category '{name}' is not in config.yaml. "
            "Add it under `categories:` before using it on a transaction."
        )

    def categories_of_type(self, category_type: CategoryType) -> list[Category]:
        return [c for c in self.categories if c.type == category_type]

    def category_type_or_none(self, name: str) -> CategoryType | None:
        """Like category_type(), but returns None instead of raising for a
        category not in config.yaml — e.g. Plaid's raw category strings on
        transactions you haven't tagged with one of your own categories yet.
        """
        for cat in self.categories:
            if cat.name == name:
                return cat.type
        return None

    def limits_for_year(self, tax_year: int) -> ContributionLimit | None:
        return next((l for l in self.contribution_limits if l.tax_year == tax_year), None)

    def manual_account_balance(self, account_name: str) -> float:
        """starting_balance, minus every transaction charged to this account,
        plus every transfer this account received from another manual
        account (via another account's transfer_to).
        """
        account = next((a for a in self.manual_accounts if a.name == account_name), None)
        if account is None:
            raise ConfigError(f"No manual account named '{account_name}' in config.yaml.")

        balance = account.starting_balance
        for t in self.transactions:
            if t.account == account_name:
                balance -= t.amount
            if t.transfer_to == account_name:
                balance += t.amount
        return balance

    def manual_accounts_as_accounts(self) -> list[Account]:
        """Converts config.yaml's manual_accounts into the same Account
        shape Plaid accounts use, so both can populate one table.
        """
        return [
            Account(
                institution="Manual",
                name=ma.name,
                official_name=ma.name,
                account_type=ma.kind,
                current_balance=self.manual_account_balance(ma.name),
                available_balance=None,
                currency="USD",
            )
            for ma in self.manual_accounts
        ]

    def manual_transactions_as_transactions(self) -> list[Transaction]:
        """Converts config.yaml's transactions into the same Transaction
        shape Plaid transactions use, so both can populate one table:
        Date -> date, Account -> institution, Note -> merchant,
        Amount -> amount, Category -> category.
        """
        return [
            Transaction(
                transaction_id=f"manual-{idx}",
                institution=t.account,
                date=datetime.combine(t.date, datetime.min.time()),
                merchant=t.note or t.category,
                amount=t.amount,
                category=t.category,
            )
            for idx, t in enumerate(self.transactions)
        ]


_VALID_CATEGORY_TYPES = {"spend", "offset", "income", "transfer"}
_VALID_ACCOUNT_KINDS = {"bank", "cash", "credit", "prepaid", "loan", "investment"}


def load_budget_config(path: Path | None = None) -> BudgetConfig:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        raise ConfigError(f"No config.yaml found at {path}.")

    raw = yaml.safe_load(path.read_text()) or {}

    categories = []
    seen_names: set[str] = set()
    for entry in raw.get("categories", []):
        name = entry.get("name")
        cat_type = entry.get("type")
        if not name:
            raise ConfigError("A category entry is missing 'name'.")
        if cat_type not in _VALID_CATEGORY_TYPES:
            raise ConfigError(
                f"Category '{name}' has type '{cat_type}'; "
                f"must be one of {sorted(_VALID_CATEGORY_TYPES)}."
            )
        if name in seen_names:
            raise ConfigError(f"Category '{name}' is defined more than once.")
        seen_names.add(name)
        categories.append(Category(name=name, type=cat_type))

    manual_accounts = []
    for entry in raw.get("manual_accounts", []):
        kind = entry.get("kind")
        if kind not in _VALID_ACCOUNT_KINDS:
            raise ConfigError(
                f"Account '{entry.get('name')}' has kind '{kind}'; "
                f"must be one of {sorted(_VALID_ACCOUNT_KINDS)}."
            )
        manual_accounts.append(ManualAccount(
            name=entry["name"],
            kind=kind,
            starting_balance=entry.get("starting_balance", 0.0),
            credit_limit=entry.get("credit_limit"),
            interest_rate=entry.get("interest_rate"),
            interest_starts=entry.get("interest_starts"),
            payoff_order=entry.get("payoff_order"),
            autopay_day=entry.get("autopay_day"),
            annual_fee=entry.get("annual_fee"),
        ))

    manual_account_names = {ma.name for ma in manual_accounts}

    transactions = []
    for entry in raw.get("transactions", []):
        account = entry.get("account")
        if account not in manual_account_names:
            raise ConfigError(
                f"Transaction dated {entry.get('date')} references unknown manual "
                f"account '{account}'. Add it under `manual_accounts:` first."
            )
        category = entry.get("category")
        if category not in seen_names:
            raise ConfigError(
                f"Transaction dated {entry.get('date')} references unknown category "
                f"'{category}'. Add it under `categories:` first."
            )
        if "amount" not in entry:
            raise ConfigError(f"Transaction dated {entry.get('date')} is missing 'amount'.")
        transactions.append(ManualTransaction(
            date=entry["date"],
            account=account,
            amount=entry["amount"],
            category=category,
            note=entry.get("note", ""),
            transfer_to=entry.get("transfer_to"),
        ))

    payroll_raw = raw.get("payroll", {})
    payroll = PayrollAssumptions(
        deferral_rate_401k=payroll_raw.get("deferral_rate_401k", 0.0),
        match_tier_1_rate=payroll_raw.get("match_tier_1_rate", 0.0),
        match_tier_1_pct=payroll_raw.get("match_tier_1_pct", 0.0),
        match_tier_2_rate=payroll_raw.get("match_tier_2_rate", 0.0),
        match_tier_2_pct=payroll_raw.get("match_tier_2_pct", 0.0),
        expected_net_pay_per_period=payroll_raw.get("expected_net_pay_per_period"),
    )

    forecast_raw = raw.get("forecast", {})
    forecast = ForecastAssumptions(
        minimum_cash_buffer=forecast_raw.get("minimum_cash_buffer", 0.0),
        hsa_cash_floor=forecast_raw.get("hsa_cash_floor", 0.0),
    )

    contribution_limits = [
        ContributionLimit(
            tax_year=entry["tax_year"],
            roth_ira_limit=entry.get("roth_ira_limit"),
            roth_401k_limit=entry.get("roth_401k_limit"),
            hsa_limit=entry.get("hsa_limit"),
            tax_filing_deadline=entry.get("tax_filing_deadline"),
        )
        for entry in raw.get("contribution_limits", [])
    ]

    if "tracker_start_date" not in raw:
        raise ConfigError("config.yaml is missing 'tracker_start_date'.")

    return BudgetConfig(
        tracker_start_date=raw["tracker_start_date"],
        categories=categories,
        manual_accounts=manual_accounts,
        transactions=transactions,
        payroll=payroll,
        forecast=forecast,
        contribution_limits=contribution_limits,
    )