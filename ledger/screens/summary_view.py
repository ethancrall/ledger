from rich.table import Table
from textual.widgets import Static

from ledger.summary import SummaryData


class SummaryView(Static):
    def populate(self, summary: SummaryData) -> None:
        table = Table.grid(padding=(0, 3))
        table.add_column(justify="left")
        table.add_column(justify="right")

        def section(title: str) -> None:
            table.add_row("")
            table.add_row(f"[bold underline]{title}[/bold underline]", "")

        def row(label: str, value: str) -> None:
            table.add_row(label, value)

        p = summary.position
        section("POSITION")
        row("Bank Accounts", f"${p.bank_assets:,.2f}")
        row("Cash", f"${p.cash:,.2f}")
        row("Credit Card Liability", f"-${p.credit_liability:,.2f}")
        row("Prepaid Balances", f"${p.prepaid:,.2f}")
        row("TRUE CASH", f"${p.true_cash:,.2f}")

        section("INVESTMENTS & LOANS")
        row("Investments", f"${p.investments:,.2f}")
        row("Loans", f"${p.loans:,.2f}")

        section("NET WORTH")
        row("Net Worth", f"${p.net_worth:,.2f}")

        s = summary.spend
        section("SPEND")
        row("Months Elapsed", f"{s.months_elapsed:.1f}")
        row("Total Spend (excl. transfers)", f"${s.total_spend:,.2f}")
        row("Offsets (refunds, reimbursements)", f"${s.offsets:,.2f}")
        row("Net Spend", f"${s.net_spend:,.2f}")
        row("Average Monthly Net Spend", f"${s.average_monthly_net_spend:,.2f}")

        lp = summary.loan_payoff
        section("LOAN PAYOFF (avalanche)")
        row("Total Loan Balance", f"${lp.total_loan_balance:,.2f}")
        row(
            "Weighted Avg Rate",
            f"{lp.weighted_avg_rate:.2%}" if lp.weighted_avg_rate is not None else "—",
        )
        row("Daily Interest (once accruing)", f"${lp.daily_interest:,.2f}")
        row("Interest Accrued to Date", f"${lp.interest_accrued_to_date:,.2f}")
        if lp.next_target:
            row("Next Target", lp.next_target.name)
            row("Next Target Balance", f"${lp.next_target.balance:,.2f}")
            row("Next Target Rate", f"{lp.next_target.rate:.2%}")
        else:
            row("Next Target", "— (no rated loan balance outstanding)")

        section("PAYROLL TO DATE")
        row("Status", "Not available yet — needs structured paycheck data (see BACKLOG.md)")

        self.update(table)