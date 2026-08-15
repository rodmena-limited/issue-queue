"""The HTTP client for the issuedb <-> Tracker sync protocol.

``urllib`` only, following ``ollama_client.py``: this package takes no
dependencies for core functionality, and a sync client is core.

Three behaviours here are contractual rather than stylistic, and each exists
because the alternative fails silently:

* **The handshake is a preflight that fails CLOSED.** If the server's protocol
  range does not include ours, nothing is written locally. A sync that
  half-applies against a contract it does not understand is the worst outcome
  available to either side — worse than not syncing at all, because the
  database afterwards is neither the old state nor the new one.

* **`Retry-After` is authoritative.** On 429 the server's number is honoured
  rather than a locally invented backoff. A client that computes its own
  interval turns a rate limit into a thundering herd the operator cannot
  tune from their end.

* **Errors are `application/problem+json` and are branched on `code`, not on
  status.** Two different 409s mean entirely different things here —
  ``protocol_unsupported`` means stop, ``cursor_too_old`` means re-seed — and
  a client keying on the status alone would conflate them.

The client performs no local writes at all. It fetches, and returns parsed
results; applying them is the caller's job, which keeps the network layer
testable without a database and keeps "what was applied" a decision made in
one place.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, NamedTuple

PROTOCOL_VERSION = "1"
PROTOCOL_HEADER = "X-IssueDB-Protocol"
DEFAULT_TIMEOUT = 30.0


class Handshake(NamedTuple):
    """What the server told us before we were allowed to touch anything."""

    protocol_min: int
    protocol_max: int
    project_uid: str
    symmetric_relation_types: frozenset[str]
    tombstone_retention_days: int
    uid_algorithm: str
    raw: dict[str, Any]


class PullResult(NamedTuple):
    changes: list[dict[str, Any]]
    cursor: str
    has_more: bool
    safe_horizon: str | None


class SyncError(Exception):
    """A sync call failed in a way the caller must decide about.

    ``code`` is the stable machine-readable identifier from problem+json.
    Branch on it; the HTTP status is not sufficient.
    """

    def __init__(
        self, code: str, message: str, status: int = 0, retry_after: float | None = None
    ) -> None:
        self.code = code
        self.status = status
        self.retry_after = retry_after
        super().__init__(message)


class ProtocolUnsupportedError(SyncError):
    """The server does not speak our protocol version. Nothing may be written."""


class CursorTooOldError(SyncError):
    """The cursor predates the tombstone horizon; a full re-seed is required.

    Refusing is the load-bearing half of tombstone retention. Without it, a
    replica that sat untouched past the horizon would silently resurrect every
    row the team deleted, with no error at any point.
    """


class AuthFailedError(SyncError):
    """401. The key is missing, malformed, revoked or expired.

    The server deliberately returns the SAME code for unknown and revoked, so
    an unauthenticated caller cannot learn which key ids exist. Do not try to
    distinguish them.
    """


class RateLimitedError(SyncError):
    """429. ``retry_after`` is the server's number and is authoritative."""


class SyncClient:
    """Talks to a Tracker sync endpoint. Performs no local writes."""

    def __init__(
        self,
        server_url: str,
        token: str,
        timeout: float = DEFAULT_TIMEOUT,
        opener: Any = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self._token = token
        self.timeout = timeout
        # Injectable so tests drive a real local HTTP server rather than a
        # mock of one. A mocked transport would agree with whatever this file
        # believes the protocol is, which is the class of self-confirming test
        # this project keeps finding.
        self._opener = opener or urllib.request.build_opener()

    # -- transport ---------------------------------------------------------

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        url = f"{self.server_url}{path}"
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header(PROTOCOL_HEADER, PROTOCOL_VERSION)
        request.add_header("Accept", "application/json, application/problem+json")
        if data is not None:
            request.add_header("Content-Type", "application/json")

        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return response.status, self._decode(response.read())
        except urllib.error.HTTPError as exc:
            payload = self._decode(exc.read())
            raise self._problem_to_error(exc.code, payload, exc.headers) from None
        except urllib.error.URLError as exc:
            raise SyncError(
                "unreachable", f"could not reach {self.server_url}: {exc.reason}"
            ) from exc

    @staticmethod
    def _decode(raw: bytes) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            # An error arriving as HTML from an edge proxy is the case this
            # guards: a client branching on `code` cannot do so, and must not
            # crash with a JSON error that hides the real status.
            return {"code": "malformed_response", "detail": raw[:200].decode("utf-8", "replace")}
        return decoded if isinstance(decoded, dict) else {"code": "malformed_response"}

    @staticmethod
    def _retry_after(headers: Any) -> float | None:
        if headers is None:
            return None
        raw = headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _problem_to_error(self, status: int, payload: dict[str, Any], headers: Any) -> SyncError:
        """Map problem+json to a typed error, branching on `code`."""
        code = str(payload.get("code") or "")
        detail = str(payload.get("detail") or payload.get("title") or "")
        message = f"{code or status}: {detail}" if detail else (code or f"HTTP {status}")

        if code == "protocol_unsupported":
            return ProtocolUnsupportedError(code, message, status)
        if code == "cursor_too_old":
            return CursorTooOldError(code, message, status)
        if code == "invalid_api_key" or status == 401:
            return AuthFailedError(code or "invalid_api_key", message, status)
        if code == "rate_limited" or status == 429:
            return RateLimitedError(
                code or "rate_limited", message, status, self._retry_after(headers)
            )
        return SyncError(code or f"http_{status}", message, status)

    # -- the protocol ------------------------------------------------------

    def handshake(self) -> Handshake:
        """Preflight. Call this BEFORE writing anything locally.

        Raises ProtocolUnsupportedError when the ranges do not overlap — checked
        both from the server's 409 and from the advertised range, because a
        server that returns a range without enforcing it would otherwise let
        an incompatible client straight through.
        """
        _status, body = self._request("GET", "/v1/sync/handshake")

        try:
            minimum = int(body["protocol_min"])
            maximum = int(body["protocol_max"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SyncError(
                "malformed_handshake",
                f"handshake did not advertise a usable protocol range: {body!r}",
            ) from exc

        ours = int(PROTOCOL_VERSION)
        if not minimum <= ours <= maximum:
            raise ProtocolUnsupportedError(
                "protocol_unsupported",
                f"this issuedb speaks protocol {ours}; the server accepts "
                f"{minimum}-{maximum}. Nothing has been written locally. "
                f"Upgrade issuedb.",
                409,
            )

        return Handshake(
            protocol_min=minimum,
            protocol_max=maximum,
            project_uid=str(body.get("project_uid", "")),
            # Read from the handshake, NEVER hardcoded: a constant here is what
            # made Tracker's own two implementations derive different uids.
            symmetric_relation_types=frozenset(body.get("symmetric_relation_types") or ()),
            tombstone_retention_days=int(body.get("tombstone_retention_days", 0)),
            uid_algorithm=str(body.get("uid_algorithm", "")),
            raw=body,
        )

    def push(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Push outbox entries. Returns one result per entry.

        An ``existing`` outcome is SUCCESS, not a conflict: a replay of an
        entry another replica already pushed is expected here, because in a
        git-tracked repo a checkout can hand this replica outbox rows that
        were already sent.
        """
        _status, body = self._request("POST", "/v1/sync/push", {"entries": entries})
        results = body.get("results")
        return list(results) if isinstance(results, list) else []

    def pull(self, cursor: str) -> PullResult:
        """Fetch changes after ``cursor``.

        Raises CursorTooOldError when the cursor predates the tombstone horizon;
        the caller must re-seed rather than apply a partial view.
        """
        _status, body = self._request("GET", f"/v1/sync/pull?cursor={cursor}")
        return PullResult(
            changes=list(body.get("changes") or []),
            cursor=str(body.get("cursor") or cursor),
            has_more=bool(body.get("has_more", False)),
            safe_horizon=body.get("safe_horizon"),
        )
