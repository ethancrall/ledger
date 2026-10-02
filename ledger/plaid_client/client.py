"""Builds a single shared plaid-python API client from settings."""
import plaid
from plaid.api import plaid_api

from ledger.config import Settings


def build_client(settings: Settings) -> plaid_api.PlaidApi:
    env_map = {
        "sandbox": plaid.Environment.Sandbox,
        "production": plaid.Environment.Production,
    }

    configuration = plaid.Configuration(
        host=env_map[settings.plaid_env],
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)