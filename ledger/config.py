"""Loads configuration from environment variables / .env file."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    plaid_client_id: str
    plaid_secret: str
    plaid_env: str  # "sandbox" | "production"

    @property
    def plaid_host(self) -> str:
        hosts = {
            "sandbox": "https://sandbox.plaid.com",
            "production": "https://production.plaid.com",
        }
        return hosts[self.plaid_env]


def load_settings() -> Settings:
    client_id = os.environ.get("PLAID_CLIENT_ID")
    secret = os.environ.get("PLAID_SECRET")
    env = os.environ.get("PLAID_ENV", "sandbox")

    if not client_id or not secret:
        raise RuntimeError(
            "Missing PLAID_CLIENT_ID or PLAID_SECRET. "
            "Copy .env.example to .env and fill in your Plaid credentials."
        )

    return Settings(plaid_client_id=client_id, plaid_secret=secret, plaid_env=env)
