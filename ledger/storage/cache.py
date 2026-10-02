"""Local cache: the dashboard always reads from here. A manual refresh
action re-hits Plaid and rewrites this cache — Plaid is never called just
because the dashboard was opened.

Transactions are stored one row per transaction_id (not as one JSON blob)
because /transactions/sync is incremental: each call only returns what
changed since your last cursor. A blob-replace cache would wipe out
everything that wasn't touched in the latest call — upserting by id is
what makes repeated refreshes additive instead of destructive.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ledger.models.account import Account
from ledger.models.transaction import Transaction

DB_PATH = Path.home() / ".ledger_cache.sqlite3"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS accounts (data TEXT, fetched_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS transaction_entries ("
        "transaction_id TEXT PRIMARY KEY, data TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sync_cursors (institution TEXT PRIMARY KEY, cursor TEXT)"
    )
    return conn


def save_accounts(accounts: list[Account]) -> None:
    conn = _connect()
    conn.execute("DELETE FROM accounts")
    conn.execute(
        "INSERT INTO accounts (data, fetched_at) VALUES (?, datetime('now'))",
        (json.dumps([a.__dict__ for a in accounts]),),
    )
    conn.commit()
    conn.close()


def load_cached_accounts() -> list[Account]:
    conn = _connect()
    row = conn.execute("SELECT data FROM accounts LIMIT 1").fetchone()
    conn.close()
    if not row:
        return []
    return [Account(**d) for d in json.loads(row[0])]


def upsert_transactions(transactions: list[Transaction]) -> None:
    """Insert new transactions, overwrite ones Plaid reports as modified.
    Existing transactions not present in `transactions` are left untouched.
    """
    if not transactions:
        return
    conn = _connect()
    conn.executemany(
        "INSERT INTO transaction_entries (transaction_id, data) VALUES (?, ?) "
        "ON CONFLICT(transaction_id) DO UPDATE SET data = excluded.data",
        [
            (t.transaction_id, json.dumps({**t.__dict__, "date": t.date.isoformat()}))
            for t in transactions
        ],
    )
    conn.commit()
    conn.close()


def delete_transactions(transaction_ids: list[str]) -> None:
    """Removes transactions Plaid reports as removed (e.g. a pending
    transaction that posted and got replaced by a new transaction_id).
    """
    if not transaction_ids:
        return
    conn = _connect()
    conn.executemany(
        "DELETE FROM transaction_entries WHERE transaction_id = ?",
        [(tid,) for tid in transaction_ids],
    )
    conn.commit()
    conn.close()


def load_cached_transactions() -> list[Transaction]:
    conn = _connect()
    rows = conn.execute("SELECT data FROM transaction_entries").fetchall()
    conn.close()
    parsed = [json.loads(row[0]) for row in rows]
    transactions = [
        Transaction(**{**d, "date": datetime.fromisoformat(d["date"])})
        for d in parsed
    ]
    transactions.sort(key=lambda t: t.date, reverse=True)
    return transactions


def get_sync_cursor(institution_name: str) -> str | None:
    conn = _connect()
    row = conn.execute(
        "SELECT cursor FROM sync_cursors WHERE institution = ?", (institution_name,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def save_sync_cursor(institution_name: str, cursor: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO sync_cursors (institution, cursor) VALUES (?, ?) "
        "ON CONFLICT(institution) DO UPDATE SET cursor = excluded.cursor",
        (institution_name, cursor),
    )
    conn.commit()
    conn.close()