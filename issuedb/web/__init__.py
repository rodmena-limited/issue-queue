"""Flask Web UI and API for .issue.db."""

from issuedb.web import _routes_api, _routes_api2, _routes_pages  # noqa: F401  (register routes)
from issuedb.web._app import app
from issuedb.web._server import run_server

__all__ = ["app", "run_server"]
