from pathlib import Path

from textual.app import App

from ledger.config import load_settings
from ledger.plaid_client.client import build_client
from ledger.screens.dashboard import DashboardScreen


class ledgerApp(App):
    CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"
    TITLE = "ledger"

    def on_mount(self) -> None:
        settings = load_settings()
        self.plaid_client = build_client(settings)
        self.push_screen(DashboardScreen())


def run() -> None:
    ledgerApp().run()


if __name__ == "__main__":
    run()
