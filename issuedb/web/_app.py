"""Flask Web UI and API for .issue.db."""

import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, request
from werkzeug.wrappers import Response

from issuedb.repository import IssueRepository

# root_path is pinned to the issuedb package dir (the parent of this web/ subpackage)
# so the favicon/font routes that resolve `app.root_path/static` keep finding
# issuedb/static/ after web.py was split into this package.
app = Flask(__name__, root_path=str(Path(__file__).resolve().parent.parent))
# Set a secret key so the app never runs with an insecure default. A stable key can
# be provided via the environment; otherwise a random per-process key is used.
app.secret_key = os.environ.get("ISSUEDB_SECRET_KEY") or os.urandom(32)

# Cache repository instances by db_path
_repo_cache: dict[str, IssueRepository] = {}

# HTTP methods that may change state and therefore require CSRF protection.
_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Tag colors are interpolated into inline ``style="..."`` attributes in the
# templates. Even with Jinja autoescaping (which prevents breaking out of the
# quoted attribute), a value like ``red;background:url(//evil)`` would still
# inject arbitrary CSS. Restricting colors to a hex literal removes that vector.
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{3,8}$")
_DEFAULT_COLOR = "#888888"


def _safe_color(value: Optional[str]) -> str:
    """Return ``value`` only if it is a safe hex color, else a safe default.

    Used both when accepting colors from request input and (as defense in depth)
    when rendering pre-existing colors, so that no tag color can ever inject CSS
    into an inline ``style`` attribute.
    """
    if value is not None and _HEX_COLOR_RE.match(value):
        return value
    return _DEFAULT_COLOR


# Expose the sanitizer to templates so colors are validated at render time.
app.jinja_env.filters["safe_color"] = _safe_color

# Matches the issue id in an issue-detail path such as ``/issues/42`` or
# ``/issues/42/edit`` (anchored, digits only).
_ISSUE_PATH_RE = re.compile(r"^/issues/(\d+)(?:/|$)")


def _issue_id_from_referer(referer: Optional[str]) -> Optional[int]:
    """Extract an issue id from a Referer's *path* only, ignoring host/scheme.

    Returns the integer id when the path identifies an issue detail page, else
    ``None``. Only the path component is inspected, so the result can never be a
    client-controlled redirect target -- it is solely used to rebuild a
    server-side ``url_for`` URL.
    """
    if not referer:
        return None
    match = _ISSUE_PATH_RE.match(urlsplit(referer).path)
    if match:
        return int(match.group(1))
    return None


@app.before_request
def _csrf_protect() -> Optional[Response]:
    """Reject cross-origin state-changing requests (CSRF mitigation).

    Browsers always send an ``Origin`` header on cross-origin POST/PUT/PATCH/DELETE
    (and a ``Referer`` on form posts), so comparing the request's origin host against
    the server's own host blocks browser-driven CSRF. Non-browser API clients that
    omit both headers are still allowed, preserving programmatic access.
    """
    if request.method not in _STATE_CHANGING_METHODS:
        return None

    target_host = request.host  # host[:port] the request was sent to

    origin = request.headers.get("Origin")
    if origin:
        if urlsplit(origin).netloc != target_host:
            resp = jsonify({"error": "Cross-origin request blocked"})
            resp.status_code = 403
            return resp
        return None

    referer = request.headers.get("Referer")
    if referer and urlsplit(referer).netloc != target_host:
        resp = jsonify({"error": "Cross-origin request blocked"})
        resp.status_code = 403
        return resp

    return None


@app.errorhandler(ValueError)
def _handle_value_error(error: ValueError) -> Response:
    """Return invalid user input (e.g. bad status/priority/date) as a clean 400.

    Without this, a ``ValueError`` from ``Priority.from_string``/``Status.from_string``
    or the repository would surface as an unhandled 500.
    """
    resp = jsonify({"error": str(error)})
    resp.status_code = 400
    return resp


@app.context_processor
def inject_project_info() -> dict[str, str]:
    """Inject project information into templates."""
    db_path = app.config.get("ISSUEDB_DB_PATH")
    if db_path:
        try:
            path = Path(db_path).resolve()
            project_name = path.parent.name if path.is_file() else path.name
        except Exception:
            project_name = "unknown"
    else:
        project_name = Path.cwd().name
    return {"project_name": project_name}


def get_repo() -> IssueRepository:
    """Get the repository for the database this server was started for.

    The database path is fixed at server startup (``--db`` on the CLI). It was
    previously taken from a ``?db=`` query parameter, which let any request —
    including unauthenticated cross-origin GETs — create directories and
    SQLite files at arbitrary filesystem paths or read arbitrary databases.
    """
    db_path = app.config.get("ISSUEDB_DB_PATH") or ""

    # Use request-scoped cache first (Flask g object)
    cache_key = f"repo_{db_path}"
    cached_repo: Optional[IssueRepository] = getattr(g, cache_key, None)
    if cached_repo is not None:
        return cached_repo

    # Fall back to global cache
    if db_path not in _repo_cache:
        _repo_cache[db_path] = IssueRepository(db_path if db_path else None)

    repo = _repo_cache[db_path]
    setattr(g, cache_key, repo)
    return repo


@app.teardown_appcontext
def cleanup_db_connection(exception: Optional[BaseException] = None) -> None:
    """Close database connection at end of request.

    Ensures thread-local connections are properly cleaned up,
    preventing connection leaks in the Waitress thread pool.
    """
    for key in list(vars(g).keys()):
        if key.startswith("repo_"):
            repo = getattr(g, key, None)
            if repo is not None:
                repo.db.close_connection()


# =============================================================================
# HTML Templates
# =============================================================================

