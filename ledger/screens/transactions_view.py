from textual.widgets import DataTable

from ledger.models.transaction import Transaction


class TransactionsView(DataTable):
    def on_mount(self) -> None:
        self.add_columns("Date", "Institution", "Merchant", "Amount", "Category")
        self.cursor_type = "row"

    def populate(self, transactions: list[Transaction]) -> None:
        self.clear()
        for txn in transactions:
            self.add_row(
                txn.date.strftime("%Y-%m-%d"),
                txn.institution,
                txn.merchant,
                f"${txn.amount:,.2f}",
                txn.category,
            )
