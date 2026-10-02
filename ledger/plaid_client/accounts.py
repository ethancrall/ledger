"""Fetches balances across every linked institution."""
from plaid.api import plaid_api
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest

from ledger.models.account import Account
from ledger.storage.tokens import get_all_access_tokens


def fetch_all_balances(client: plaid_api.PlaidApi) -> list[Account]:
    """One Plaid call per linked institution (each access_token = one Item)."""
    accounts: list[Account] = []

    for institution_name, access_token in get_all_access_tokens().items():
        request = AccountsBalanceGetRequest(access_token=access_token)
        response = client.accounts_balance_get(request)

        for acct in response["accounts"]:
            balances = acct["balances"]
            accounts.append(
                Account(
                    institution=institution_name,
                    name=acct["name"],
                    official_name=acct.get("official_name") or acct["name"],
                    account_type=str(acct["type"]),
                    current_balance=balances["current"] or 0.0,
                    available_balance=balances.get("available"),
                    currency=balances.get("iso_currency_code") or "USD",
                )
            )

    return accounts
