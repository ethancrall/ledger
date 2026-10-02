"""Stores Plaid access_tokens in the OS credential store (via `keyring`)
rather than in a plaintext file — these tokens are live credentials to
real bank data.

A small local file (NOT the tokens themselves) tracks which institution
names have been linked, so we know which keyring entries to look up.
"""
import json
from pathlib import Path

import keyring

SERVICE_NAME = "ledger"
INDEX_FILE = Path.home() / ".ledger_institutions.json"


def _load_institution_index() -> list[str]:
    if not INDEX_FILE.exists():
        return []
    return json.loads(INDEX_FILE.read_text())


def _save_institution_index(names: list[str]) -> None:
    INDEX_FILE.write_text(json.dumps(names))


def save_access_token(institution_name: str, access_token: str) -> None:
    keyring.set_password(SERVICE_NAME, institution_name, access_token)

    names = _load_institution_index()
    if institution_name not in names:
        names.append(institution_name)
        _save_institution_index(names)


def get_all_access_tokens() -> dict[str, str]:
    tokens = {}
    for name in _load_institution_index():
        token = keyring.get_password(SERVICE_NAME, name)
        if token:
            tokens[name] = token
    return tokens
