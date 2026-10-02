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
from datetime import date
from pathlib import Path
from typing import Literal

import yaml

from ledger.models.account import Account

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
    # Optional override — until manual accounts have their own transaction
    # feed, this is how you keep the dashboard's number current: edit it
    # in config.yaml whenever the real balance changes. Falls back to
    # starting_balance if you never set it.
    current_balance: float | None = None
    credit_limit: float | None = None
    interest_rate: float | None = None
    interest_starts: date | None = None
    payoff_order: int | None = None
    autopay_day: int | None = None
    annual_fee: float | None = None

    @property
    def effective_balance(self) -> float:
        return self.current_balance if self.current_balance is not None else self.starting_balance


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

    def limits_for_year(self, tax_year: int) -> ContributionLimit | None:
        return next((l for l in self.contribution_limits if l.tax_year == tax_year), None)

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
                current_balance=ma.effective_balance,
                available_balance=None,
                currency="USD",
            )
            for ma in self.manual_accounts
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
            current_balance=entry.get("current_balance"),
            credit_limit=entry.get("credit_limit"),
            interest_rate=entry.get("interest_rate"),
            interest_starts=entry.get("interest_starts"),
            payoff_order=entry.get("payoff_order"),
            autopay_day=entry.get("autopay_day"),
            annual_fee=entry.get("annual_fee"),
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
        payroll=payroll,
        forecast=forecast,
        contribution_limits=contribution_limits,
    )