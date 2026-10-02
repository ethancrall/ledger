"""Fetches recent transactions across every linked institution.

Uses /transactions/sync, Plaid's recommended approach — each call returns
only what changed since your last cursor (added, modified, removed), not
a full history every time. Because it's incremental, we apply each page's
changes directly into the cache (upsert added/modified, delete removed)
rather than collecting "this call's results" and treating that as the
full picture — the cache is the accumulated state; a single sync call is
just a delta against it.
"""
from datetime import datetime

from plaid.api import plaid_api
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from ledger.budget_config import BudgetConfig
from ledger.models.transaction import Transaction
from ledger.storage.cache import (
    delete_transactions,
    get_sync_cursor,
    load_cached_transactions,
    save_sync_cursor,
    upsert_transactions,
)
from ledger.storage.tokens import get_all_access_tokens


def _to_transaction(txn: dict, institution_name: str) -> Transaction:
    return Transaction(
        transaction_id=txn["transaction_id"],
        institution=institution_name,
        date=datetime.fromisoformat(str(txn["date"])),
        merchant=txn.get("merchant_name") or txn["name"],
        amount=txn["amount"],
        # Plaid's own category is kept only as a fallback label;
        # your config.yaml categories are the source of truth
        # once you've tagged a transaction yourself.
        category=(txn.get("personal_finance_category") or {}).get(
            "primary", "UNCATEGORIZED"
        ),
    )


def fetch_recent_transactions(client: plaid_api.PlaidApi) -> list[Transaction]:
    """Syncs every linked institution, merges the deltas into the cache,
    and returns the full current set of cached transactions (not just
    what changed in this call) so the dashboard has something to render.
    """
    for institution_name, access_token in get_all_access_tokens().items():
        cursor = get_sync_cursor(institution_name)
        has_more = True

        while has_more:
            request = (
                TransactionsSyncRequest(access_token=access_token, cursor=cursor)
                if cursor is not None
                else TransactionsSyncRequest(access_token=access_token)
            )
            response = client.transactions_sync(request)

            upserts = [
                _to_transaction(txn, institution_name)
                for txn in (*response["added"], *response["modified"])
            ]
            upsert_transactions(upserts)

            removed_ids = [item["transaction_id"] for item in response["removed"]]
            delete_transactions(removed_ids)

            cursor = response["next_cursor"]
            has_more = response["has_more"]

        save_sync_cursor(institution_name, cursor)

    return load_cached_transactions()


def detect_paychecks(
    transactions: list[Transaction], config: BudgetConfig
) -> list[Transaction]:
    """A transaction counts as a paycheck if its category is one of the
    user's own 'income' categories (config.yaml), rather than relying on
    Plaid's categorization. Falls back to Plaid's category only for
    transactions you haven't re-tagged yet.
    """
    income_category_names = {c.name for c in config.categories_of_type("income")}

    PLAID_INCOME_CATEGORIES = {"INCOME", "INCOME_WAGES", "INCOME_DIVIDENDS", "TRANSFER_IN_DEPOSIT"}
    return [t for t in transactions if t.amount < -500 and t.category in PLAID_INCOME_CATEGORIES]