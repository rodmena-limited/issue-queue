#!/usr/bin/env python3
"""Replay the twelve frozen vectors against the LIVE Tracker.

The probe answers "can the two implementations talk at all". This answers the
question after it: WHICH OF THE FROZEN VECTORS SURVIVE CONTACT — as a
checklist, per vector, rather than a judgement.

Three classifications, kept apart for the same reason the probe keeps its
verdicts apart. Collapsing them is how a replay lies:

    PASS             every step matched the frozen expectation
    NOT IMPLEMENTED  the server has not built this endpoint or entity yet
    FAILED           the server HAS built it and answered differently

Only the third is a defect. A replay that reported "9 failures" when nine of
them were unbuilt features would be worse than useless — it would send another
team hunting bugs that are just unwritten code.

THE STATE PROBLEM, and why uids are salted
------------------------------------------
Every vector was written against FakeTracker, whose store is a dict recreated
per vector. Production is shared and persistent, so a uid pushed by an earlier
run is still there: a vector expecting ``created`` gets ``existing`` on its
second run and "fails" for a reason that has nothing to do with the server.

So each run salts every uid with a run id. The vector's SHAPE is preserved —
same uid reused across steps within a run, different uids stay different — but
no two runs collide. Without this the harness would be green exactly once and
then permanently, meaninglessly red.

Standard library only.

    python3 audit/evaluations/vector_replay.py
    python3 audit/evaluations/vector_replay.py --server http://127.0.0.1:8123
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from issuedb.sync._credentials import load as load_credential  # noqa: E402

DEFAULT_SERVER = "https://tracker.rodmena.co.uk"
VECTOR_DIR = REPO_ROOT / "tests" / "data" / "vectors"

PASS = "PASS"
ABSENT = "NOT IMPLEMENTED"
FAILED = "FAILED"
SKIPPED = "SKIPPED"
HARNESS = "HARNESS ERROR"


def salt_uids(obj: Any, run_id: str) -> Any:
    """Rewrite every ``s256t128:`` uid so this run cannot collide with the last.

    Deterministic within a run: the same input uid always maps to the same
    salted uid, so a vector that reuses a uid across steps still exercises
    replay/idempotency. Different input uids stay different, so a vector
    testing convergence still tests convergence.
    """
    if isinstance(obj, dict):
        return {k: salt_uids(v, run_id) for k, v in obj.items()}
    if isinstance(obj, list):
        return [salt_uids(v, run_id) for v in obj]
    if isinstance(obj, str) and obj.startswith("s256t128:"):
        digest = hashlib.sha256(f"{run_id}:{obj}".encode()).hexdigest()[:32]
        return f"s256t128:{digest}"
    return obj


def adapt_body(request_spec: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    """Add what the real route requires and the vectors do not carry.

    The vectors were written against FakeTracker, which takes ``replica_id``
    from the STEP rather than the body. The real route requires it in the body
    — the number alias is keyed on (project, REPLICA, number), so without it
    two replicas' #3 collide in the table that exists to resolve them.

    So a vector replayed verbatim gets 422 on every push. That is the harness
    being wrong, not the server, and it is exactly the shape that produces a
    false accusation against another team.
    """
    body = request_spec.get("body")
    if body is None:
        return None
    if request_spec["path"].startswith("/v1/sync/push") and "replica_id" not in body:
        body = dict(body)
        body["replica_id"] = f"issuedb-replay-{run_id}"
    return body


def call(
    server: str, step: dict[str, Any], token: str, timeout: float, run_id: str
) -> tuple[int, dict[str, Any]]:
    request_spec = step["request"]
    url = f"{server}{request_spec['path']}"
    body = adapt_body(request_spec, run_id)
    data = None if body is None else json.dumps(body).encode()

    request = urllib.request.Request(url, data=data, method=request_spec["method"])
    request.add_header("Authorization", f"Bearer {token}")
    for header, value in (request_spec.get("headers") or {}).items():
        request.add_header(header, str(value))
    request.add_header("X-IssueDB-Protocol", "1")
    if data is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, (json.loads(raw) if raw else {})
        except json.JSONDecodeError:
            return exc.code, {"_body": raw[:200].decode("utf-8", "replace")}
    except urllib.error.URLError as exc:
        return 0, {"_unreachable": str(exc.reason)}


def compare(expected: Any, actual: Any, path: str = "") -> list[str]:
    """Report where actual departs from expected, ignoring extra server fields.

    Subset comparison: a server adding a field it did not previously send is
    not a contract break, but a server CHANGING or DROPPING one is.
    """
    problems: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path or '<root>'}: expected an object, got {type(actual).__name__}"]
        for key, want in expected.items():
            if key not in actual:
                problems.append(f"{path}.{key}: MISSING (expected {want!r})")
            else:
                problems.extend(compare(want, actual[key], f"{path}.{key}"))
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected a list, got {type(actual).__name__}"]
        if len(expected) != len(actual):
            problems.append(f"{path}: expected {len(expected)} item(s), got {len(actual)}")
        else:
            for index, (want, got) in enumerate(zip(expected, actual)):
                problems.extend(compare(want, got, f"{path}[{index}]"))
    elif expected != actual:
        problems.append(f"{path}: expected {expected!r}, got {actual!r}")
    return problems


def classify_step(
    status: int, body: dict[str, Any], expected_status: int
) -> str | None:
    """ABSENT when the feature is unbuilt, else None to continue comparing."""
    if status == 404 and expected_status != 404:
        return ABSENT
    if status == 405:
        return ABSENT
    for result in body.get("results", []) or []:
        if result.get("outcome") == "rejected" and "unknown entity" in str(
            result.get("reason", "")
        ):
            return ABSENT
    return None


def _relax_server_assigned_numbers(want: dict[str, Any], got: dict[str, Any]) -> list[str]:
    """Copy server-assigned `number` values into the expectation, in place.

    Returns what was relaxed so the caller can PRINT it. The absolute number
    is unpredictable against a shared server; number_aliased and local_number
    are not, and those keep being asserted.
    """
    relaxed: list[str] = []
    for index, want_result in enumerate(want.get("results") or []):
        if "number" not in want_result:
            continue
        got_results = got.get("results") or []
        if index >= len(got_results) or "number" not in got_results[index]:
            continue
        if want_result["number"] != got_results[index]["number"]:
            relaxed.append(f"{want_result['number']}->{got_results[index]['number']}")
            want_result["number"] = got_results[index]["number"]
    return relaxed


def replay(path: pathlib.Path, server: str, token: str, run_id: str, timeout: float):
    vector = json.loads(path.read_text())
    steps = vector.get("steps") or []
    if not steps:
        return SKIPPED, ["no HTTP steps — derivation-only vector"]

    # Salt per VECTOR, not merely per run. Three uid literals appear in more
    # than one vector — `aaaa0000…` is in 01, 02, 04 and 06 — and each vector
    # was written against a FRESH FakeTracker store. Sharing a salt across
    # vectors makes 01 create the row that 02 then finds `existing`, and 02
    # "fails" for a reason that has nothing to do with the server.
    scope = f"{run_id}:{path.stem}"

    notes: list[str] = []
    for index, step in enumerate(steps):
        salted = salt_uids(step, scope)
        expected = salted.get("response") or {}
        expected_status = int(expected.get("status", 200))

        # A step may call for a credential this harness does not hold. Vector
        # 06 needs a REVOKED key at step 1; sending the valid one instead gets
        # 200 where the vector expects 401, and reporting that as a server
        # defect would be a false accusation caused entirely by the harness
        # substituting a credential it happened to have.
        step_key = salted["request"].get("key", "valid")
        if step_key not in ("valid", None):
            return SKIPPED, [
                f"step {index} requires a '{step_key}' credential, which this harness "
                f"does not hold — NOT run rather than run with the wrong key"
            ]

        status, body = call(server, salted, token, timeout, scope)

        if status == 0:
            return FAILED, [f"step {index}: unreachable — {body.get('_unreachable')}"]

        verdict = classify_step(status, body, expected_status)
        if verdict == ABSENT:
            return ABSENT, [f"step {index}: {salted['request']['path']} -> {status}"]

        if status == 422 and expected_status != 422:
            fields = [
                ".".join(str(x) for x in e.get("loc", []))
                for e in (body.get("errors") or [])
            ]
            return HARNESS, [
                f"step {index}: the server rejected OUR request body as invalid"
                + (f" (missing/!invalid: {', '.join(fields)})" if fields else "")
                + " — this harness is malformed, not the server"
            ]

        if status != expected_status:
            return FAILED, [
                f"step {index} {salted['request']['path']}: "
                f"expected HTTP {expected_status}, got {status} — {json.dumps(body)[:160]}"
            ]

        # A server-assigned issue number cannot match a frozen literal: the
        # vectors were written against a store whose counter starts at 1, and
        # production is at 9000+. The RELATIONSHIP is what the vector tests —
        # number_aliased, local_number — not the absolute value. Relaxed
        # explicitly and reported, because a silent relaxation is how a check
        # becomes vacuous.
        want_body = expected.get("body") or {}
        relaxed = _relax_server_assigned_numbers(want_body, body)
        if relaxed:
            notes.append(f"step {index}: relaxed absolute number(s) {relaxed}")

        problems = compare(want_body, body, f"step{index}")
        if problems:
            return FAILED, [f"step {index}: " + p for p in problems[:4]]
        notes.append(f"step {index} ok")

    return PASS, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--token", default=None)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument(
        "--run-id",
        default=None,
        help="Salt for uids. Defaults to a fresh one, so runs never collide. "
        "Pass a fixed value to deliberately re-run against existing state.",
    )
    args = parser.parse_args()

    server = args.server.rstrip("/")
    vectors = sorted(VECTOR_DIR.glob("*.json"))

    # Control: without vectors every line below would be a vacuous pass.
    if len(vectors) < 12:
        print(f"PROBE BROKEN: expected >=12 vectors in {VECTOR_DIR}, found {len(vectors)}")
        return 2

    token = args.token
    if token is None:
        stored = load_credential(server)
        if stored is None:
            print(f"NOT SIGNED IN to {server}. Run: issuedb-cli signin --server {server}")
            return 2
        token = stored.token
        print(f"Using the credential from issuedb-cli signin: {stored.redacted()}")

    run_id = args.run_id or hashlib.sha256(str(vectors).encode()).hexdigest()[:8]
    if args.run_id is None:
        import uuid

        run_id = uuid.uuid4().hex[:12]

    print(f"Replaying {len(vectors)} frozen vectors against {server}")
    print(f"  run id {run_id} — uids are salted so this run cannot collide with the last\n")

    tally: dict[str, int] = {PASS: 0, ABSENT: 0, FAILED: 0, SKIPPED: 0, HARNESS: 0}
    failures: list[tuple[str, list[str]]] = []

    for path in vectors:
        verdict, notes = replay(path, server, token, run_id, args.timeout)
        tally[verdict] += 1
        marker = {PASS: "PASS", ABSENT: "----", FAILED: "FAIL", SKIPPED: "skip",
                  HARNESS: "HARN"}[verdict]
        detail = "" if verdict == PASS else f"   {notes[0] if notes else ''}"
        print(f"  {marker}  {path.stem:<34}{detail}")
        if verdict == FAILED:
            failures.append((path.stem, notes))

    print(
        f"\n{tally[PASS]} passed, {tally[FAILED]} FAILED, "
        f"{tally[ABSENT]} not implemented, {tally[HARNESS]} harness errors, "
        f"{tally[SKIPPED]} skipped"
    )
    if tally[HARNESS]:
        print(
            "  HARNESS ERROR means THIS SCRIPT sent a malformed request. Not a "
            "server defect, and must never be reported as one."
        )

    if failures:
        print("\nFAILURES IN DETAIL — these are the only entries that are defects:")
        for name, notes in failures:
            print(f"  {name}")
            for note in notes:
                print(f"    {note}")

    print(
        "\nNOT IMPLEMENTED is not a defect: the endpoint or entity is unbuilt. "
        "Only FAILED means the server built it and answered differently."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
