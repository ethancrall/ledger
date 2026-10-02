from textual.widgets import DataTable

from ledger.models.account import Account


class AccountsView(DataTable):
    def on_mount(self) -> None:
        self.add_columns("Institution", "Account", "Type", "Balance", "Available")
        self.cursor_type = "row"

    def populate(self, accounts: list[Account]) -> None:
        self.clear()
        for acct in accounts:
            available = f"${acct.available_balance:,.2f}" if acct.available_balance is not None else "—"
            self.add_row(
                acct.institution,
                acct.name,
                acct.account_type,
                f"${acct.current_balance:,.2f}",
                available,
            )
