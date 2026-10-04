"""Summary tab — POSITION/NET WORTH, spend totals, and loan avalanche
payoff math (spreadsheet Summary tab, rows 1-25: everything above the
per-category grid and data checks).

Two deliberate departures from the original spreadsheet, both forced by
what's actually available in this codebase rather than a design choice:

1. Plaid only tells us an account's broad type ("depository", "credit"),
   not subtype — we can't distinguish Checking from Savings/HYSA the way
   the sheet does. They're combined into one "Bank Accounts" figure.

2. PAYROLL TO DATE needs real paystub data (Gross Pay, FIT, FICA,
   benefits breakdown) that doesn't exist anywhere in this app yet —
   Plaid gives you a deposit amount, not a pay stub. That section is a
   placeholder until the Paychecks tab gets built out (see BACKLOG.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ledger.budget_config import BudgetConfig, ManualAccount
from ledger.models.account import Account
from ledger.models.transaction import Transaction

# Plaid's account "type" strings -> our own kind vocabulary. Anything not
# listed here (our own manual-account kinds: cash, prepaid, loan,
# investment, and "credit"/"bank" already matching) passes through as-is.
_PLAID_TYPE_TO_BUCKET = {
    "depository": "bank",
}


def _bucket(account_type: str) -> str:
    return _PLAID_TYPE_TO_BUCKET.get(account_type, account_type)


@dataclass
class PositionSummary:
    bank_assets: float
    cash: float
    credit_liability: float   # positive magnitude of what's owed
    prepaid: float
    investments: float
    loans: float              # signed — negative means owed
    true_cash: float
    net_worth: float


@dataclass
class SpendSummary:
    months_elapsed: float
    total_spend: float
    offsets: float
    net_spend: float
    average_monthly_net_spend: float


@dataclass
class LoanTarget:
    name: str
    balance: float  # positive magnitude owed
    rate: float


@dataclass
class LoanPayoffSummary:
    total_loan_balance: float
    weighted_avg_rate: float | None
    daily_interest: float
    interest_accrued_to_date: float
    next_target: LoanTarget | None


@dataclass
class SummaryData:
    position: PositionSummary
    spend: SpendSummary
    loan_payoff: LoanPayoffSummary


def _compute_position(accounts: list[Account]) -> PositionSummary:
    bank_assets = cash = prepaid = investments = loans = 0.0
    credit_liability = 0.0

    for a in accounts:
        bucket = _bucket(a.account_type)
        if bucket == "bank":
            bank_assets += a.current_balance
        elif bucket == "cash":
            cash += a.current_balance
        elif bucket == "credit":
            credit_liability += abs(a.current_balance)
        elif bucket == "prepaid":
            prepaid += a.current_balance
        elif bucket == "investment":
            investments += a.current_balance
        elif bucket == "loan":
            loans += a.current_balance  # already signed negative = owed
        # Unrecognized account types are intentionally left out of every
        # bucket rather than guessed at — better to under-report than
        # silently misclassify something as an asset or a liability.

    true_cash = bank_assets + cash
    net_worth = bank_assets + cash + prepaid + investments - credit_liability + loans

    return PositionSummary(
        bank_assets=bank_assets,
        cash=cash,
        credit_liability=credit_liability,
        prepaid=prepaid,
        investments=investments,
        loans=loans,
        true_cash=true_cash,
        net_worth=net_worth,
    )


def _compute_spend(
    transactions: list[Transaction], config: BudgetConfig, as_of: date
) -> SpendSummary:
    window = [t for t in transactions if t.date.date() >= config.tracker_start_date]

    total_spend = sum(
        t.amount for t in window if config.category_type_or_none(t.category) == "spend"
    )
    # Offsets (refunds, reimbursements) arrive as negative amounts in our
    # sign convention (negative = money in); flip sign so this reads as a
    # positive "amount offset" figure.
    offsets = -sum(
        t.amount for t in window if config.category_type_or_none(t.category) == "offset"
    )
    net_spend = total_spend - offsets

    days_elapsed = max((as_of - config.tracker_start_date).days, 1)
    months_elapsed = days_elapsed / 30.44
    average_monthly_net_spend = net_spend / months_elapsed

    return SpendSummary(
        months_elapsed=months_elapsed,
        total_spend=total_spend,
        offsets=offsets,
        net_spend=net_spend,
        average_monthly_net_spend=average_monthly_net_spend,
    )


def _compute_loan_payoff(config: BudgetConfig, as_of: date) -> LoanPayoffSummary:
    loans = [ma for ma in config.manual_accounts if ma.kind == "loan"]

    entries = []  # (ManualAccount, abs_balance)
    for loan in loans:
        balance = abs(config.manual_account_balance(loan.name))
        entries.append((loan, balance))

    total_loan_balance = sum(balance for _, balance in entries)

    rated = [(loan, bal) for loan, bal in entries if loan.interest_rate is not None and bal > 0]
    weighted_avg_rate = (
        sum(bal * loan.interest_rate for loan, bal in rated) / sum(bal for _, bal in rated)
        if rated
        else None
    )

    accruing = [
        (loan, bal) for loan, bal in rated
        if loan.interest_starts is not None and loan.interest_starts <= as_of
    ]
    daily_interest = sum(bal * loan.interest_rate / 365 for loan, bal in accruing)
    interest_accrued_to_date = sum(
        bal * loan.interest_rate / 365 * (as_of - loan.interest_starts).days
        for loan, bal in accruing
    )

    next_target = None
    if rated:
        # Avalanche: highest rate first; payoff_order (if set) breaks ties.
        best_loan, best_balance = max(
            rated, key=lambda pair: (pair[0].interest_rate, -(pair[0].payoff_order or 0))
        )
        next_target = LoanTarget(name=best_loan.name, balance=best_balance, rate=best_loan.interest_rate)

    return LoanPayoffSummary(
        total_loan_balance=total_loan_balance,
        weighted_avg_rate=weighted_avg_rate,
        daily_interest=daily_interest,
        interest_accrued_to_date=interest_accrued_to_date,
        next_target=next_target,
    )


def compute_summary(
    accounts: list[Account],
    transactions: list[Transaction],
    config: BudgetConfig,
    as_of: date | None = None,
) -> SummaryData:
    as_of = as_of or date.today()
    return SummaryData(
        position=_compute_position(accounts),
        spend=_compute_spend(transactions, config, as_of),
        loan_payoff=_compute_loan_payoff(config, as_of),
    )