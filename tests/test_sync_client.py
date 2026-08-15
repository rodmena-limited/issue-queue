"""The sync client, driven against Tracker's FakeTracker over real HTTP.

There is no mock transport here, deliberately. A mocked server would agree
with whatever this repo believes the protocol is, which is the self-confirming
test this collaboration has spent its whole life finding: the check and the
thing it checks quietly agreeing while the real question goes unasked.

FakeTracker is Tracker's own stdlib reference server, vendored into
``tests/data/faketracker.py`` so these tests RUN rather than skip when the
Tracker checkout is absent. A skipped test is a check that cannot go red.

What a green run here proves and does not prove:

* PROVES: this client obeys the rules in PROTOCOL.md as FakeTracker implements
  them.
* DOES NOT PROVE: that sync works against Tracker. Tracker has not implemented
  ``/v1/sync/*`` at all. FakeTracker has no tenancy, no authorization, no
  durability and no concurrency, and its database is a dict.
"""

from __future__ import annotations

import importlib.util
import pathlib
import threading

import pytest

from issuedb.sync._client import (
    AuthFailedError,
    CursorTooOldError,
    ProtocolUnsupportedError,
    RateLimitedError,
    SyncClient,
    SyncError,
)

FAKETRACKER = pathlib.Path(__file__).parent / "data" / "faketracker.py"


def _load_faketracker():
    spec = importlib.util.spec_from_file_location("vendored_faketracker", FAKETRACKER)
    assert spec and spec.loader, f"could not load {FAKETRACKER}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def faketracker():
    return _load_faketracker()


@pytest.fixture
def server(faketracker):
    """A real FakeTracker on an ephemeral port, fresh store per test."""
    from http.server import ThreadingHTTPServer

    faketracker.Handler.store = faketracker.Store()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), faketracker.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", faketracker
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def client(server, faketracker):
    base, module = server
    return SyncClient(base, token=module.VALID_KEY)


# --- the vendored fixture is real -----------------------------------------


def test_the_vendored_faketracker_is_present_and_is_the_real_one(faketracker):
    """Control. Without it every test below could pass on an empty module."""
    assert FAKETRACKER.exists()
    assert hasattr(faketracker, "Handler")
    assert hasattr(faketracker, "Store")
    assert hasattr(faketracker, "VALID_KEY")
    assert faketracker.PROTOCOL_MIN <= 1 <= faketracker.PROTOCOL_MAX


# --- handshake -------------------------------------------------------------


def test_handshake_returns_the_servers_contract(client):
    shake = client.handshake()
    assert shake.protocol_min <= 1 <= shake.protocol_max
    assert shake.project_uid
    assert shake.uid_algorithm == "s256t128"
    assert shake.tombstone_retention_days > 0


def test_the_symmetric_set_comes_from_the_server_not_from_us(client, faketracker):
    """Hardcoding this is what made Tracker's own implementations disagree."""
    shake = client.handshake()
    assert shake.symmetric_relation_types == frozenset(
        faketracker.SYMMETRIC_RELATION_TYPES
    )


def test_an_unsupported_protocol_fails_closed(server, faketracker, monkeypatch):
    """Nothing may be written locally when the ranges do not overlap."""
    base, module = server
    monkeypatch.setattr(module, "PROTOCOL_MIN", 99)
    monkeypatch.setattr(module, "PROTOCOL_MAX", 99)

    with pytest.raises(ProtocolUnsupportedError) as excinfo:
        SyncClient(base, token=module.VALID_KEY).handshake()
    assert excinfo.value.code == "protocol_unsupported"
    assert excinfo.value.status == 409


def test_the_client_refuses_a_range_it_is_outside_even_if_the_server_allows_it():
    """The client checks the advertised range itself, not only the server's 409.

    A server that advertises a range without enforcing it would otherwise wave
    an incompatible client straight through — and the client would then write
    local rows under a contract it does not understand, which is the exact
    outcome the preflight exists to prevent.
    """
    import io
    import json as _json

    class Permissive:
        """Returns a 99..99 range with a 200, never a 409."""

        def open(self, request, timeout=None):
            body = _json.dumps(
                {"protocol_min": 99, "protocol_max": 99, "project_uid": "p"}
            ).encode()

            class Response(io.BytesIO):
                status = 200

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False

            return Response(body)

    client = SyncClient("http://example.invalid", token="t", opener=Permissive())
    with pytest.raises(ProtocolUnsupportedError) as excinfo:
        client.handshake()
    assert "nothing has been written" in str(excinfo.value).lower()


def test_the_handshake_is_unauthenticated_by_design(server, faketracker):
    """Preflight must work BEFORE the client has a usable credential.

    A client has to be able to discover a protocol mismatch without one —
    otherwise "your issuedb is too old" is indistinguishable from "your key is
    bad", and the user is sent to fix the wrong thing.

    Auth is enforced on push and pull instead; the two tests below are the
    positive control for that, so this is not read as "auth is absent".
    """
    base, module = server
    assert SyncClient(base, token="trk_not_a_real_key").handshake().project_uid


def test_a_revoked_key_is_indistinguishable_from_an_unknown_one(server, faketracker):
    """Deliberate: distinguishing them tells a caller which key ids exist."""
    base, module = server
    with pytest.raises(AuthFailedError) as revoked:
        SyncClient(base, token=module.REVOKED_KEY).push([_entry()], "test-replica")
    with pytest.raises(AuthFailedError) as unknown:
        SyncClient(base, token="trk_unknown_key").push([_entry()], "test-replica")
    assert revoked.value.code == unknown.value.code == "invalid_api_key"


def test_pull_requires_a_valid_key(server, faketracker):
    base, module = server
    with pytest.raises(AuthFailedError):
        SyncClient(base, token=module.REVOKED_KEY).pull("c:0")


# --- push ------------------------------------------------------------------


def _entry(uid="s256t128:" + "a" * 32, content_hash="h1", **payload):
    return {
        "uid": uid,
        "entity": "issue",
        "op": "upsert",
        "content_hash": content_hash,
        "payload": payload or {"title": "hello"},
    }


def test_push_creates(client):
    results = client.push([_entry()], "test-replica")
    assert [r["outcome"] for r in results] == ["created"]
    assert results[0]["version"] == 1


def test_a_replayed_push_is_success_not_a_conflict(client):
    """A git checkout can hand this replica outbox rows already pushed.

    Reporting that as a conflict would make the common case in a tracked repo
    look like an error the user has to resolve.
    """
    entry = _entry()
    client.push([entry], "test-replica")
    results = client.push([entry], "test-replica")
    assert results[0]["outcome"] == "existing"
    assert results[0]["version"] == 1


def test_push_with_a_revoked_key_raises_auth_failed(server, faketracker):
    base, module = server
    client = SyncClient(base, token=module.REVOKED_KEY)
    with pytest.raises(AuthFailedError) as excinfo:
        client.push([_entry()], "test-replica")
    assert excinfo.value.code == "invalid_api_key"


def test_work_applied_before_a_revocation_is_not_undone(server, faketracker):
    """The contract: applied changes STAY; only the cursor stops advancing."""
    base, module = server
    good = SyncClient(base, token=module.VALID_KEY)
    good.push([_entry()], "test-replica")

    revoked = SyncClient(base, token=module.REVOKED_KEY)
    with pytest.raises(AuthFailedError):
        revoked.push([_entry(uid="s256t128:" + "b" * 32)], "test-replica")

    # The first push is still there, seen through the product's own interface.
    assert len(good.pull("c:0").changes) == 1


# --- pull ------------------------------------------------------------------


def test_pull_returns_what_was_pushed(client):
    client.push([_entry(title="pulled back")], "test-replica")
    result = client.pull("c:0")
    assert len(result.changes) == 1
    assert result.changes[0]["payload"]["title"] == "pulled back"
    assert result.cursor != "c:0"


def test_pull_from_the_returned_cursor_is_empty(client):
    client.push([_entry()], "test-replica")
    first = client.pull("c:0")
    assert client.pull(first.cursor).changes == []


def test_a_cursor_past_the_horizon_is_refused(client, faketracker):
    """Refusing is the load-bearing half of tombstone retention.

    Without it a replica that sat untouched past the horizon silently
    resurrects everything the team deleted, erroring nowhere.
    """
    client.push([_entry()], "test-replica")
    faketracker.Handler.store.horizon = 10_000

    with pytest.raises(CursorTooOldError):
        client.pull("c:0")


def test_pull_with_a_bad_cursor_is_an_error_not_a_silent_reseed(client):
    with pytest.raises(SyncError) as excinfo:
        client.pull("not-a-cursor")
    assert excinfo.value.code == "bad_cursor"


# --- error handling --------------------------------------------------------


def test_errors_branch_on_code_not_on_status(client, faketracker):
    """Two different 409s mean opposite things here.

    protocol_unsupported means stop; cursor_too_old means re-seed. A client
    keying on the status alone would conflate them.
    """
    client.push([_entry()], "test-replica")
    faketracker.Handler.store.horizon = 10_000
    with pytest.raises(CursorTooOldError) as excinfo:
        client.pull("c:0")
    assert excinfo.value.status == 409
    assert excinfo.value.code == "cursor_too_old"


def test_an_unreachable_server_is_a_typed_error(faketracker):
    client = SyncClient("http://127.0.0.1:1", token=faketracker.VALID_KEY)
    with pytest.raises(SyncError) as excinfo:
        client.handshake()
    assert excinfo.value.code == "unreachable"


def test_retry_after_is_taken_from_the_server(faketracker):
    """The server's number is authoritative; we do not invent a backoff."""
    import urllib.error

    class Rejecting:
        def open(self, request, timeout=None):
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "17"},  # type: ignore[arg-type]
                None,
            )

    client = SyncClient("http://example.invalid", token="t", opener=Rejecting())
    with pytest.raises(RateLimitedError) as excinfo:
        client.handshake()
    assert excinfo.value.retry_after == 17.0


def test_a_non_json_error_body_does_not_crash_the_client(faketracker):
    """An edge proxy returning HTML must not hide the status behind a parse error."""
    import io
    import urllib.error

    class Html:
        def open(self, request, timeout=None):
            raise urllib.error.HTTPError(
                request.full_url, 502, "Bad Gateway", {}, io.BytesIO(b"<html>nope</html>")
            )

    client = SyncClient("http://example.invalid", token="t", opener=Html())
    with pytest.raises(SyncError) as excinfo:
        client.handshake()
    assert excinfo.value.status == 502


# --- the replica_id requirement, found at first contact --------------------


def test_push_sends_replica_id_in_the_body():
    """First contact returned 422 because this field was missing.

        422 {"loc": ["body", "replica_id"], "msg": "Field required"}

    It matters because the issue-number alias is keyed on (project, REPLICA,
    number). Without a replica id two replicas' #3 collide in the alias table
    — the very collision the alias exists to resolve.

    Asserted by capturing the bytes actually sent, not by trusting the
    signature: a default value or a dropped key would satisfy a signature
    check and still send nothing.
    """
    import io
    import json as _json

    captured = {}

    class Capture:
        def open(self, request, timeout=None):
            captured["body"] = _json.loads(request.data)

            class Response(io.BytesIO):
                status = 200

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False

            return Response(b'{"results": []}')

    client = SyncClient("http://example.invalid", token="t", opener=Capture())
    client.push([_entry()], "replica-xyz")

    assert captured["body"]["replica_id"] == "replica-xyz"
    assert "entries" in captured["body"]


def test_push_requires_replica_id_rather_than_defaulting_it():
    """Omitting it must be a TypeError here, not a 422 from Tracker."""
    client = SyncClient("http://example.invalid", token="t", opener=object())
    with pytest.raises(TypeError):
        client.push([_entry()])  # type: ignore[call-arg]


def test_rejected_surfaces_per_entry_rejections_inside_a_200():
    """A 200 is not blanket success.

    Tracker rejects per-uid for entities it has not implemented. A client that
    read the status alone would advance its cursor past a change that never
    landed, and nothing would error.
    """
    results = [
        {"uid": "a", "outcome": "created", "version": 1},
        {"uid": "b", "outcome": "rejected", "reason": "unknown entity: issue_tag"},
    ]
    rejected = SyncClient.rejected(results)
    assert [r["uid"] for r in rejected] == ["b"]
    assert SyncClient.rejected(results[:1]) == []
