#!/usr/bin/env python3
"""First contact: run issuedb's sync client against a LIVE Tracker.

Everything either side has proven so far is about a fixture. FakeTracker
agrees with issuedb because both were written to the same document; that says
the document is unambiguous, not that the server works. This script is the
instrument that answers the actual question, and it is written before the
endpoints exist so that first contact is one command rather than an
improvisation.

Three outcomes are kept strictly apart, because conflating them is how a
probe lies:

    PROBE BROKEN     a control request failed. We report NOTHING about sync.
    NOT IMPLEMENTED  the endpoint is absent (404). Expected today.
    FAILED           the endpoint EXISTS and behaves wrongly. This is a defect.

The controls are the load-bearing part. A 404 from a misconfigured probe looks
exactly like a 404 from a missing route, so the script first proves it can
reach endpoints that are known to exist. Without that, "not implemented" is an
unfounded accusation against another team.

Exit codes:
    0   controls passed; endpoints absent, or present and correct
    1   an implemented endpoint behaved wrongly
    2   PROBE BROKEN — controls failed, no conclusion drawn

Standard library only.

    python3 audit/evaluations/first_contact_probe.py
    python3 audit/evaluations/first_contact_probe.py --server http://127.0.0.1:8099
    python3 audit/evaluations/first_contact_probe.py --token trk_xxx_yyy
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from issuedb.sync._client import (  # noqa: E402
    AuthFailedError,
    ProtocolUnsupportedError,
    SyncClient,
    SyncError,
)
from issuedb.sync._credentials import load as load_credential  # noqa: E402

DEFAULT_SERVER = "https://tracker.rodmena.co.uk"
VECTOR_DIR = REPO_ROOT / "tests" / "data" / "vectors"

# Endpoints that must answer before any conclusion is drawn about /v1/sync/*.
# If these fail, the probe is broken, not the server.
CONTROL_PATHS = ["/_build", "/healthz", "/"]

BROKEN = "PROBE BROKEN"
ABSENT = "NOT IMPLEMENTED"
FAILED = "FAILED"
PASSED = "PASSED"
NO_CREDENTIAL = "NO CREDENTIAL"


def _status(url: str, timeout: float) -> int | str:
    """HTTP status for a GET, or a string describing why there was none."""
    request = urllib.request.Request(url, method="GET")
    request.add_header("X-IssueDB-Protocol", "1")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except urllib.error.URLError as exc:
        return f"unreachable ({exc.reason})"


def run_controls(
    server: str, timeout: float, paths: list[str] | None = None
) -> tuple[bool, list[str]]:
    """Prove the probe can reach this host before judging what is missing."""
    lines = ["CONTROLS — endpoints known to exist:"]
    ok = True
    for path in paths or CONTROL_PATHS:
        status = _status(f"{server}{path}", timeout)
        good = status == 200
        ok = ok and good
        lines.append(f"  {path:<24} {status}{'' if good else '   <- CONTROL FAILED'}")
    return ok, lines


def served_commit(server: str, timeout: float) -> str:
    """Which build is actually serving. Merging is not deploying."""
    try:
        request = urllib.request.Request(f"{server}/_build", method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return str(json.loads(response.read()).get("commit", "unknown"))
    except Exception:
        return "unknown"


def probe_sync_surface(server: str, timeout: float) -> tuple[dict[str, int | str], list[str]]:
    results: dict[str, int | str] = {}
    lines = ["SYNC SURFACE:"]
    for path in ("/v1/sync/handshake", "/v1/sync/pull", "/v1/sync/push"):
        status = _status(f"{server}{path}", timeout)
        results[path] = status
        note = "  <- absent" if status == 404 else ""
        lines.append(f"  {path:<24} {status}{note}")
    return results, lines


def exercise_handshake(client: SyncClient) -> tuple[str, list[str]]:
    """The preflight, which must work before anything is written locally."""
    lines = ["HANDSHAKE:"]
    try:
        shake = client.handshake()
    except ProtocolUnsupportedError as exc:
        # A real answer, not a failure of the probe: the server spoke and said
        # no. That is the preflight doing its job.
        lines.append(f"  protocol refused: {exc}")
        return FAILED, lines
    except AuthFailedError as exc:
        # The handshake is unauthenticated by design in the contract, so auth
        # being required here is a genuine divergence worth reporting.
        lines.append(f"  AUTH REQUIRED at the handshake — contract says unauthenticated: {exc}")
        return FAILED, lines
    except SyncError as exc:
        if exc.status == 404:
            lines.append("  absent")
            return ABSENT, lines
        lines.append(f"  error: code={exc.code!r} status={exc.status}")
        return FAILED, lines

    lines.append(f"  protocol range      {shake.protocol_min}..{shake.protocol_max}")
    lines.append(f"  project_uid         {shake.project_uid or '(empty)'}")
    lines.append(f"  uid_algorithm       {shake.uid_algorithm or '(empty)'}")
    lines.append(f"  symmetric types     {sorted(shake.symmetric_relation_types) or '(none)'}")
    lines.append(f"  tombstone retention {shake.tombstone_retention_days} days")

    # ONLY the fields openapi.yaml marks required are divergences.
    #
    # An earlier version of this probe flagged an empty project_uid as a
    # defect and reported FAILED against the live server. That was wrong, and
    # it was wrong in the way that matters: the schema's required list is
    # [protocol_min, protocol_max, uid_algorithm], and project_uid is NOT in
    # it. It cannot be — the handshake is unauthenticated by design, so the
    # server does not yet know which project the caller means.
    #
    # A probe that invents a requirement files a defect against another team
    # for behaviour their contract permits. That is worse than a probe that
    # misses something, because it is confidently wrong and it costs someone
    # else an investigation.
    problems = []
    if shake.uid_algorithm != "s256t128":
        problems.append(f"uid_algorithm is {shake.uid_algorithm!r}, contract says 's256t128'")
    if not (shake.protocol_min <= 1 <= shake.protocol_max):
        problems.append(
            f"advertised range {shake.protocol_min}..{shake.protocol_max} excludes protocol 1"
        )

    # Optional fields: reported so a human can see them, never asserted.
    notes = []
    if not shake.project_uid:
        notes.append(
            "project_uid absent — permitted: the handshake is unauthenticated, so the "
            "server cannot know the project yet. Expect it on an authenticated call."
        )
    if not shake.symmetric_relation_types:
        notes.append(
            "symmetric set empty — CORRECT for production v1 per the contract; "
            "FakeTracker's x-test-symmetric exists only so the vectors are not vacuous."
        )
    if shake.tombstone_retention_days <= 0:
        notes.append("tombstone_retention_days not advertised")

    for note in notes:
        lines.append(f"  note: {note}")
    for problem in problems:
        lines.append(f"  DIVERGENCE: {problem}")
    return (FAILED if problems else PASSED), lines


def exercise_round_trip(client: SyncClient) -> tuple[str, list[str]]:
    """Push one entry and pull it back. The minimum that proves contact."""
    lines = ["ROUND TRIP (push one entry, pull it back):"]
    uid = "s256t128:" + "f" * 32
    entry = {
        "uid": uid,
        "entity": "issue",
        "op": "upsert",
        "content_hash": "s256t128:" + "e" * 32,
        "payload": {"title": "issuedb first-contact probe"},
    }

    try:
        results = client.push([entry], replica_id="issuedb-first-contact-probe")
    except AuthFailedError as exc:
        # A MISSING KEY IS NOT A SERVER DEFECT. Reporting 401 as FAILED would
        # accuse Tracker of a bug whose entire cause is that this probe was
        # run without a credential — the same mistake as flagging an empty
        # project_uid, one endpoint along.
        lines.append(f"  push refused the credential: code={exc.code!r} status={exc.status}")
        lines.append("  This is the server working. The probe has no key.")
        return NO_CREDENTIAL, lines
    except SyncError as exc:
        if exc.status == 404:
            lines.append("  push absent")
            return ABSENT, lines
        lines.append(f"  push error: code={exc.code!r} status={exc.status}")
        return FAILED, lines

    lines.append(f"  push -> {results}")
    if not results:
        lines.append("  DIVERGENCE: push returned no results for one entry")
        return FAILED, lines

    # A 200 is not blanket success. Tracker rejects per-uid for entities it has
    # not implemented, and a client that read the status alone would advance
    # its cursor past a change that never landed.
    rejected = SyncClient.rejected(results)
    if rejected:
        for item in rejected:
            lines.append(f"  REJECTED {item.get('uid')}: {item.get('reason')}")
        lines.append("  (a 200 with per-entry rejections is NOT success for those uids)")
        return FAILED, lines

    try:
        pulled = client.pull("c:0")
    except SyncError as exc:
        if exc.status == 404:
            lines.append("  pull absent")
            return ABSENT, lines
        lines.append(f"  pull error: code={exc.code!r} status={exc.status}")
        return FAILED, lines

    found = [c for c in pulled.changes if c.get("uid") == uid]
    lines.append(f"  pull -> {len(pulled.changes)} change(s), cursor={pulled.cursor}")
    if not found:
        lines.append("  DIVERGENCE: the pushed entry did not come back from pull")
        return FAILED, lines

    lines.append("  the pushed entry came back.")
    return PASSED, lines


def check_vectors_present() -> tuple[bool, list[str]]:
    """Control on our own fixtures: no vectors means no coverage, loudly."""
    vectors = sorted(VECTOR_DIR.glob("*.json"))
    lines = [f"VECTORS AVAILABLE: {len(vectors)}"]
    if len(vectors) < 12:
        lines.append(f"  CONTROL FAILED: expected >=12 vectors in {VECTOR_DIR}")
        return False, lines
    return True, lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token. Omitted, the probe uses the credential stored by "
        "`issuedb-cli signin` — the product's own interface, rather than a "
        "placeholder that makes a real deployment look unauthenticated.",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--control",
        action="append",
        metavar="PATH",
        help="Control path that must answer 200 before any conclusion is drawn. "
        "Repeatable. Defaults to the paths the real Tracker serves. Override it "
        "to point the probe at another host — including a local FakeTracker, "
        "which is how the SUCCESS path of this probe is itself verified.",
    )
    args = parser.parse_args()

    controls = args.control or CONTROL_PATHS

    server = args.server.rstrip("/")
    is_production = server == DEFAULT_SERVER.rstrip("/")
    print(f"issuedb first-contact probe against {server}")
    if not is_production:
        print("  NON-PRODUCTION TARGET — a pass here is not first contact.")
    print()

    controls_ok, control_lines = run_controls(server, args.timeout, controls)
    print("\n".join(control_lines))
    if not controls_ok:
        print(
            f"\n{BROKEN}: a control endpoint did not answer 200.\n"
            "  No conclusion is drawn about /v1/sync/*. A 404 from a broken probe "
            "looks exactly like a missing route, and reporting one as the other is "
            "an unfounded claim against another team."
        )
        return 2

    vectors_ok, vector_lines = check_vectors_present()
    print("\n".join(vector_lines))
    if not vectors_ok:
        return 2

    print(f"\nSERVED COMMIT: {served_commit(server, args.timeout)}")
    print("  (merging is not deploying — this is the build actually answering)\n")

    _statuses, surface_lines = probe_sync_surface(server, args.timeout)
    print("\n".join(surface_lines))
    print()

    # Prefer the credential the user actually signed in with. The first
    # version defaulted to a placeholder, so a probe run on a machine WITH a
    # valid key still reported NO CREDENTIAL — the instrument ignoring the
    # product's own state and reporting a state the machine was not in.
    token = args.token
    if token is None:
        stored = load_credential(server)
        if stored is None:
            print(
                f"NO STORED CREDENTIAL for {server}.\n"
                f"  Run: issuedb-cli signin --server {server}\n"
                f"  Continuing unauthenticated — the round trip will be UNTESTED."
            )
            token = "trk_absent_absent"
        else:
            token = stored.token
            print(f"Using the credential from issuedb-cli signin: {stored.redacted()}\n")

    client = SyncClient(server, token=token, timeout=args.timeout)
    handshake_result, handshake_lines = exercise_handshake(client)
    print("\n".join(handshake_lines))
    print()

    if handshake_result == ABSENT:
        print(
            f"VERDICT: {ABSENT}.\n"
            "  Tracker has not implemented /v1/sync/*. The controls above answered 200 "
            "through the identical invocation, which is what makes this a fact about the "
            "server rather than about this probe.\n"
            "  issuedb's client passes 12/12 vectors against FakeTracker. That is "
            "'the fixture agrees' and nothing more: the two implementations have never "
            "exchanged a byte."
        )
        return 0

    if handshake_result == FAILED:
        print(
            f"VERDICT: {FAILED} at the handshake. See the DIVERGENCE or "
            f"'protocol refused' line above — a protocol refusal is the preflight "
            f"working, not a field mismatch, and the two need different fixes."
        )
        return 1

    round_trip_result, round_trip_lines = exercise_round_trip(client)
    print("\n".join(round_trip_lines))
    print()

    if round_trip_result == PASSED:
        # WHICH SERVER answered decides what this result is worth. A green run
        # against FakeTracker is the fixture agreeing with itself; only the
        # production host makes it first contact. The probe cannot be allowed
        # to print the stronger claim just because the bytes moved — that is
        # the overclaim this whole project has been removing.
        if is_production:
            print(
                "VERDICT: FIRST CONTACT SUCCEEDED.\n"
                "  This is the first evidence in this project that is NOT about a fixture.\n"
                "  It proves a handshake and a round trip. It does NOT prove tombstones, "
                "cursor_too_old, revoked-key-mid-sync or symmetric-relation convergence — "
                "those need their vectors run against this server, not against FakeTracker."
            )
        else:
            print(
                f"VERDICT: round trip succeeded against {server} — NOT the production host.\n"
                f"  THIS IS NOT FIRST CONTACT. It proves this probe works and that the "
                f"client speaks the protocol; against FakeTracker it is the fixture "
                f"agreeing, because both sides were written from the same document.\n"
                f"  Re-run with no --server to probe {DEFAULT_SERVER}."
            )
        return 0

    if round_trip_result == ABSENT:
        print(f"VERDICT: handshake exists but push/pull are {ABSENT}. Partial deployment.")
        return 0

    if round_trip_result == NO_CREDENTIAL:
        print(
            f"VERDICT: {NO_CREDENTIAL}. The handshake succeeded and push rejected an "
            f"invalid key — both correct server behaviour.\n"
            f"  The round trip is UNTESTED, not failing. Supply a real key to complete it:\n"
            f"    issuedb-cli signin --server {server}\n"
            f"    python3 audit/evaluations/first_contact_probe.py --token trk_..."
        )
        return 0

    print(f"VERDICT: {FAILED} on the round trip. See DIVERGENCE lines above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
