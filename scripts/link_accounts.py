"""Run this once per institution (Amex, Capital One, Truist) to link it.

Plaid Link itself is a browser-based widget — there's no pure-CLI way to
complete it, since it has to collect your bank login securely on Plaid's
side. This script spins up a tiny local web page that hosts Link, catches
the resulting public_token, exchanges it for a permanent access_token, and
stores that token via ledger.storage.tokens — then you can close the tab.

Usage:
    python scripts/link_accounts.py "American Express"
"""
import http.server
import sys
import threading
import time
import webbrowser

from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode

from ledger.config import load_settings
from ledger.plaid_client.client import build_client
from ledger.storage.tokens import save_access_token

PORT = 8765
_public_token_holder: dict[str, str] = {}


def make_link_html(link_token: str) -> str:
    return f"""
    <html><body>
    <button id="link-btn">Link account</button>
    <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
    <script>
      var handler = Plaid.create({{
        token: "{link_token}",
        onSuccess: function(public_token, metadata) {{
          fetch("/public_token?token=" + public_token);
          document.body.innerText = "Linked! You can close this tab.";
        }},
      }});
      document.getElementById("link-btn").onclick = function() {{ handler.open(); }};
    </script>
    </body></html>
    """


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/public_token"):
            token = self.path.split("token=")[1]
            _public_token_holder["token"] = token
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self._server_link_html.encode())

    def log_message(self, *args):
        pass  # quiet


def link_institution(institution_name: str) -> None:
    settings = load_settings()
    client = build_client(settings)

    link_request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id="ledger-local-user"),
        client_name="ledger",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    link_token = client.link_token_create(link_request)["link_token"]

    _Handler._server_link_html = make_link_html(link_token)
    server = http.server.HTTPServer(("localhost", PORT), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    webbrowser.open(f"http://localhost:{PORT}")
    print(f"Opened browser for linking {institution_name}. Waiting...")

    while "token" not in _public_token_holder:
        time.sleep(0.1)
    server.shutdown()

    exchange_request = ItemPublicTokenExchangeRequest(
        public_token=_public_token_holder["token"]
    )
    access_token = client.item_public_token_exchange(exchange_request)["access_token"]

    save_access_token(institution_name, access_token)
    print(f"Linked and saved access token for {institution_name}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage: python scripts/link_accounts.py "Institution Name"')
        sys.exit(1)
    link_institution(sys.argv[1])
