# ledger

Personal financial dashboard — Plaid + Textual, run in your terminal.

## Setup

First, clone the ledger repository

```bash
git clone https://github.com/ethancrall/ledger.git
cd ledger
```

```bash
pip install -e .
cp .env.example .env   # fill in PLAID_CLIENT_ID and PLAID_SECRET
cp config-example.yaml config.yaml # configure your own financial categories & manual acc balances
```

`.env.example` automatically sets `PLAID_ENV=sandbox` which will open
the Plaid sandbox portal. To link your actual accounts, change this value
to `production`.

## Link your accounts (once per institution)

```bash
python scripts/link_accounts.py "American Express"
python scripts/link_accounts.py "Capital One"
python scripts/link_accounts.py "Truist"
python scripts/link_accounts.py "Venmo"
```

This opens a browser tab with Plaid Link, then stores the resulting
access token in your OS keyring (not in a file).

## Run the dashboard

```bash
ledger
```

Press `r` inside the dashboard to refresh from Plaid (pulls balances +
syncs transactions, then updates the local cache). Opening the dashboard
otherwise always reads from cache — no network/API call on startup.

## Project layout

See `ledger/` for the package: `plaid_client/` wraps the Plaid SDK,
`storage/` handles the token keyring + local SQLite cache, `models/`
are plain dataclasses, and `screens/` holds the Textual UI.

## Notes

- Start by testing `scripts/link_accounts.py` and the Plaid fetch
  functions against `PLAID_ENV=sandbox` before pointing at real
  accounts (`production`).
- `detect_paychecks()` in `plaid_client/transactions.py` is a rough
  heuristic — refine the thresholds once you see your real transaction
  categories and amounts.
