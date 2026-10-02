from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, TabbedContent, TabPane

from ledger.budget_config import load_budget_config
from ledger.plaid_client.accounts import fetch_all_balances
from ledger.plaid_client.transactions import detect_paychecks, fetch_recent_transactions
from ledger.screens.accounts_view import AccountsView
from ledger.screens.transactions_view import TransactionsView
from ledger.storage.cache import (
    load_cached_accounts,
    load_cached_transactions,
    save_accounts,
)


class DashboardScreen(Screen):
    BINDINGS = [("r", "refresh", "Refresh from Plaid")]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Accounts", id="accounts-tab"):
                yield AccountsView(id="accounts-table")
            with TabPane("Transactions", id="transactions-tab"):
                yield TransactionsView(id="transactions-table")
            with TabPane("Paychecks", id="paychecks-tab"):
                yield TransactionsView(id="paychecks-table")
        yield Footer()

    def on_mount(self) -> None:
        self.load_from_cache()

    def load_from_cache(self) -> None:
        config = load_budget_config()

        accounts = load_cached_accounts() + config.manual_accounts_as_accounts()
        self.query_one("#accounts-table", AccountsView).populate(accounts)

        transactions = load_cached_transactions()
        self.query_one("#transactions-table", TransactionsView).populate(transactions)
        self.query_one("#paychecks-table", TransactionsView).populate(
            detect_paychecks(transactions, config)
        )

    def action_refresh(self) -> None:
        """Triggered by pressing 'r'. Hits Plaid, updates the cache, re-renders."""
        client = self.app.plaid_client  # set on the App instance, see app.py

        accounts = fetch_all_balances(client)
        save_accounts(accounts)

        transactions = fetch_recent_transactions(client)

        self.load_from_cache()
        self.notify("Refreshed from Plaid.")