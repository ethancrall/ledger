# BACKLOG

What's implemented vs. still manual-config-only

## Done

**Setup**
- Category list + type (Spend/Offset/Income/Transfer) → `config.yaml` `categories:`, validated in `budget_config.py`
- Payroll assumptions (401(k) deferral rate, match tiers) → `config.yaml` `payroll:`
- Forecast assumptions (minimum cash buffer, HSA cash floor) → `config.yaml` `forecast:`
- Tracker Start Date → `config.yaml` `tracker_start_date`
- Account kinds enum (Bank/Cash/Credit/Prepaid/Loan/Investment) → `AccountKind` in `budget_config.py`

**Accounts tab**
- Plaid-linked balances (Amex, Capital One, etc.) → `plaid_client/accounts.py`, rendered in `screens/accounts_view.py`

**Transactions tab**
- Pulling transactions from Plaid-linked accounts → `plaid_client/transactions.py` (`/transactions/sync`), rendered in `screens/transactions_view.py`

**Limits tab**
- Annual limit figures by tax year (Roth IRA, Roth 401(k), HSA, filing deadline) → `config.yaml` `contribution_limits:`

**Paychecks tab**
- Rough paycheck detection on synced transactions, using your own `income` categories rather than Plaid's → `detect_paychecks()` in `plaid_client/transactions.py`

## Partially done / needs follow-up

**Accounts tab**
- No current-balance tracking for manual accounts (no calculation of Starting Balance + ledger activity).
- Credit limit, utilization %, interest rate/accrual, payoff order, autopay day, annual fee, and sign-up-bonus tracking all have config fields reserved (`ManualAccount` dataclass) but no logic reads or displays them.

**Transactions tab**
- No manual transaction entry. Everything currently comes from Plaid; there's no way to log a cash transaction.
- A transfer model (one row, `Account` + `Transfer To`, so a single entry updates both account balances) has no equivalent — Plaid transactions aren't account-pair-aware, so CC payments, loan payments, and cash withdrawals aren't currently modeled as linked double-entries.

**Paychecks tab**
- `detect_paychecks()` is a blunt filter (amount < -500 and category in the Plaid income categories) on *existing* Plaid transactions. Need one row per pay period with Gross Pay, Dental/HSA/LTD/Medical/Vision deductions, FIT (typed), and FICA/Medicare/Net Pay/Employer Match (calculated). None of that structure or those calculations exist yet.

## Not started

**Summary tab**
- POSITION block: Checking/Savings/Cash/Credit Liability/Prepaid/TRUE CASH rollup
- Investments block: HSA cash vs. invested, Roth IRA, Roth 401(k), employer match balance
- NET WORTH (sum of all signed balances)
- LOAN PAYOFF (avalanche): total balance, weighted avg rate, daily interest, next target
- PAYROLL TO DATE: paychecks received, gross pay, taxes, benefits, invested, net pay, employer match, effective tax rate
- Category grid: Total and Avg/Month per category, split by type
- DATA CHECKS: the ~17 validation rules (transactions outside tracking window, missing account/category/amount, undefined category, transfer missing a destination, account name typos, over-30%-utilization flags, contribution limit breaches, etc.)

**Forecast tab**
- Recurring obligations table (name, amount, frequency, day/date, active flag) and the frequency rules (Monthly/Weekly/Biweekly/Semiannual/Annual/One-time, including the "short months" edge case)
- Receivables table (money owed to you, expected date, received flag)
- 180-day checking balance projection

**Limits tab (computed side)**
- Contributed-to-date tracking per account (scanning transactions tagged `IRA Contribution`/`HSA Contribution`)
- Window status, days left in window, percent of limit used, per-paycheck/per-month amount needed to max out
- The IRA/HSA "prior tax year" designation logic (`Tax Year` field on a transaction, since IRA/HSA contributions made Jan–Apr can count toward the prior year)

## Suggested build order

1. **Manual accounts on the dashboard** — smallest gap, and blocks net worth from ever being accurate. Merge `config.yaml` manual accounts into the Accounts view, with current balance computed from starting balance + relevant transactions.
2. **Summary tab: POSITION + NET WORTH** — Depends only on #1 plus what's already being fetched.
3. **Paychecks as structured data** — either a manual entry form or a richer Plaid-transaction mapping, since the Limits and PAYROLL TO DATE sections both depend on real paycheck records, not just a filtered transaction list.
4. **Limits tab (computed side)** — once real paychecks and tagged contribution transactions exist.
5. **Forecast tab** — recurring obligations + 180-day projection; the data checks' "active recurring row missing info" rule becomes relevant once this exists.
6. **Data checks** — once the all above exist, there's enough structured data to actually validate against.