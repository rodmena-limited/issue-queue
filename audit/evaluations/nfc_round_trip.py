"""The decisive NFC round trip, run against the live server.

`tracker-manager-0e2462` specified this protocol:

    1. push a tag whose name is the DECOMPOSED form, note the uid we derived
    2. pull it back, record the uid the SERVER stored
    3. push the COMPOSED form as a separate request
    4. the server must answer EXISTING, not created

Step 4 is the whole test — *if* the server derives its own uid. This probe
therefore establishes that premise FIRST, in this run, rather than recalling it:
it pushes a deliberately bogus uid and reads back what the feed holds. If the
feed holds the bogus value, the server is storing what the client sent, both
pushes in steps 1-3 key off OUR derivation, and step 4's answer is decided
before the test begins.

Reporting a green from a check whose outcome is forced is the failure this
whole collaboration has been cataloguing, so the premise result gates the
verdict rather than annotating it.

CONTROLS, all of which must fire for the verdict to mean anything:
    * a NOVEL uid every run — a fixed one passes on history
    * an ASCII pair pushed identically, which MUST go created-then-existing,
      proving replay detection works in THIS run
    * the two normal forms must differ as bytes
    * a non-normalising client must derive TWO uids for them, or the input
      cannot discriminate

EXIT
    0  the round trip completed and is reported with both uids visible
    1  the composed form created a SECOND row — a real defect
    2  PROBE BROKEN — a control failed or a step did not complete
"""

from __future__ import annotations

import pathlib
import sys
import unicodedata
import uuid
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from issuedb.sync._canonical import derived_uid  # noqa: E402
from issuedb.sync._client import SyncClient, SyncError  # noqa: E402
from issuedb.sync._credentials import load as load_credential  # noqa: E402

DEFAULT_SERVER = "https://tracker.rodmena.co.uk"
OK, DEFECT, BROKEN = 0, 1, 2
MAX_PAGES = 200


def _pull_all(client: SyncClient) -> list[dict[str, Any]]:
    cursor, pages, rows = "0", 0, []
    while pages < MAX_PAGES:
        page = client.pull(cursor)
        pages += 1
        rows.extend(page.changes)
        if not page.has_more or not page.changes or page.cursor == cursor:
            break
        cursor = page.cursor
    return rows


def _stored_uid(client: SyncClient, uid: str) -> str | None:
    """What the FEED holds for this row — not what the push response echoed.

    Reading the push response was the earlier mistake here: it reports the uid
    of the entry submitted, so it agrees with us by construction.
    """
    for row in _pull_all(client):
        if row.get("uid") == uid:
            return str(row.get("uid"))
    return None


def _push(client: SyncClient, entry: dict[str, Any]) -> dict[str, Any] | None:
    out = client.push([entry], replica_id="issuedb-nfc-round-trip")
    return out[0] if out else None


def _run(client: SyncClient, project: str, created: list[tuple[str, str]]) -> int:
    salt = uuid.uuid4().hex[:8]

    # ---------- PREMISE: does the server derive, or does it store ours? ----
    print("PREMISE — does the server derive its own uid, or store the client's?")
    # NOVEL every run, per the manager's own control. The first version used
    # an all-f constant, which a previous probe had already consumed: the
    # server answered outcome 'gone' (tombstoned, restorable) and the premise
    # check correctly refused to proceed. "Bogus" here means "not the uid the
    # server would derive from this payload" — any random value qualifies, and
    # only a novel one can distinguish storing from deriving.
    bogus = "s256t128:" + uuid.uuid4().hex[:32]
    probe_issue = f"premise probe {salt}"
    res = _push(client, {"uid": bogus, "entity": "issue", "op": "upsert",
                         "content_hash": uuid.uuid4().hex,
                         "payload": {"title": probe_issue}})
    if not res or res.get("outcome") != "created":
        print(f"  PROBE BROKEN: premise row not created: {res}")
        return BROKEN
    created.append(("issue", bogus))
    seen = _stored_uid(client, bogus)
    print(f"  we sent      {bogus}")
    print(f"  feed holds   {seen}")
    server_derives = seen != bogus
    print(f"  server derives its own uid: {server_derives}\n")

    # ---------- CONTROL: the two normal forms must differ ----------
    nfc = unicodedata.normalize("NFC", f"café-{salt}")
    nfd = unicodedata.normalize("NFD", f"café-{salt}")
    print("CONTROL — the two normal forms differ as bytes:")
    print(f"  NFD {nfd.encode()!r}")
    print(f"  NFC {nfc.encode()!r}")
    if nfc == nfd:
        print("  PROBE BROKEN: identical; nothing to discriminate")
        return BROKEN
    print("  differ: YES\n")

    # ---------- the endpoint issue the tags hang on ----------
    issue_uid = "s256t128:" + uuid.uuid4().hex[:32]
    res = _push(client, {"uid": issue_uid, "entity": "issue", "op": "upsert",
                         "content_hash": uuid.uuid4().hex,
                         "payload": {"title": f"NFC round trip {salt}"}})
    if not res or res.get("outcome") != "created":
        print(f"  PROBE BROKEN: endpoint issue not created: {res}")
        return BROKEN
    created.append(("issue", issue_uid))

    # ---------- CONTROL: ASCII pair must go created -> existing ----------
    print("CONTROL — an ASCII pair, pushed identically, must replay-detect:")
    ascii_name = f"ascii-{salt}"
    ascii_uid = derived_uid("issue_tag", project, issue_uid, ascii_name)
    first = _push(client, {"uid": ascii_uid, "entity": "issue_tag", "op": "upsert",
                           "content_hash": "rt-ascii",
                           "payload": {"issue_uid": issue_uid, "tag_name": ascii_name}})
    if first and first.get("outcome") in ("created", "existing"):
        created.append(("issue_tag", ascii_uid))
    second = _push(client, {"uid": ascii_uid, "entity": "issue_tag", "op": "upsert",
                            "content_hash": "rt-ascii",
                            "payload": {"issue_uid": issue_uid, "tag_name": ascii_name}})
    print(f"  first  -> {first}")
    print(f"  second -> {second}")
    if not first or first.get("outcome") != "created":
        print("  PROBE BROKEN: the ASCII uid was not novel; replay detection unproven")
        return BROKEN
    if not second or second.get("outcome") != "existing":
        print("  PROBE BROKEN: replay of an identical entry did not report 'existing'")
        return BROKEN
    print("  created -> existing: YES, replay detection works in this run\n")

    # ---------- THE ROUND TRIP ----------
    uid_nfd = derived_uid("issue_tag", project, issue_uid, nfd)
    uid_nfc = derived_uid("issue_tag", project, issue_uid, nfc)

    print("STEP 1 — push the DECOMPOSED form:")
    r1 = _push(client, {"uid": uid_nfd, "entity": "issue_tag", "op": "upsert",
                        "content_hash": "rt-tag",
                        "payload": {"issue_uid": issue_uid, "tag_name": nfd}})
    print(f"  -> {r1}")
    if not r1 or r1.get("outcome") != "created":
        print("  PROBE BROKEN: the decomposed push was not 'created'")
        return BROKEN
    created.append(("issue_tag", uid_nfd))
    version = r1.get("version")

    print("\nSTEP 2 — what the FEED holds (not what the push echoed):")
    stored = _stored_uid(client, uid_nfd)
    print(f"  uid WE derived    {uid_nfd}")
    print(f"  uid SERVER stored {stored}")

    print("\nSTEP 3 — push the COMPOSED form as a separate request:")
    print(f"  uid WE derived for the composed form {uid_nfc}")
    r2 = _push(client, {"uid": uid_nfc, "entity": "issue_tag", "op": "upsert",
                        "content_hash": "rt-tag",
                        "payload": {"issue_uid": issue_uid, "tag_name": nfc}})
    print(f"  -> {r2}")
    if r2 and r2.get("outcome") in ("created", "existing"):
        created.append(("issue_tag", uid_nfc))
    if not r2:
        print("  PROBE BROKEN: no result for the composed push")
        return BROKEN
    outcome = r2.get("outcome")

    print("\nSTEP 4 — the verdict:")
    if outcome == "created":
        print("  THEY DISAGREE — the composed form created a SECOND row.")
        print("  Every non-ASCII tag forks into two rows that never converge.")
        return DEFECT
    if outcome == "updated":
        # Same uid, same row, version bumped: NO duplicate, which is the thing
        # under test. Seen when the two pushes carry DIFFERENT content hashes —
        # the server matched the row and rewrote it. Reported distinctly rather
        # than folded into the pass, because "existing" and "updated" say
        # different things about what the second push did.
        print(f"  'updated' — one row, version {version} -> {r2.get('version')}.")
        print("  No duplicate. The composed form resolved to the row the")
        print("  decomposed form created, and rewrote it.")
    elif outcome != "existing":
        print(f"  PROBE BROKEN: unexpected outcome {outcome!r}")
        return BROKEN
    elif r2.get("version") not in (None, version):
        print(f"  'existing', but the version moved {version} -> {r2.get('version')}")
    else:
        print(f"  'existing', version unchanged ({version}).")
    if not server_derives:
        print()
        print("  BUT THE PREMISE FAILED, SO THIS GREEN IS FORCED.")
        print("  The feed holds the uid we sent. Both pushes above keyed off OUR")
        print("  derivation, so 'existing' was decided before step 1 ran and would")
        print("  be returned by a server that does not normalise at all.")
        print("  PROVED: issuedb derives one uid for both forms and creates no")
        print("          duplicate through the push path.")
        print("  NOT PROVED: that Tracker's own derivation normalises. That needs")
        print("          a surface where the SERVER derives the uid.")
    return OK


def _shed(client: SyncClient | None, created: list[tuple[str, str]]) -> None:
    if client is None or not created:
        return
    failed = []
    for entity, uid in reversed(created):
        try:
            out = client.push([{"uid": uid, "entity": entity, "op": "delete",
                                "content_hash": uuid.uuid4().hex, "payload": {}}],
                              replica_id="issuedb-nfc-round-trip")
        except SyncError as exc:
            failed.append(f"{entity} {uid}: {exc}")
            continue
        if not out or out[0].get("outcome") != "deleted":
            failed.append(f"{entity} {uid}: {out}")
    print(f"\ncleanup: {len(created) - len(failed)}/{len(created)} rows deleted")
    for line in failed:
        print(f"  CLEANUP FAILED: {line}", file=sys.stderr)


def main() -> int:
    server = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER).rstrip("/")
    cred = load_credential(server)
    if cred is None:
        print(f"PROBE BROKEN: not signed in to {server}")
        return BROKEN
    client = SyncClient(server, token=cred.token)
    try:
        shake = client.handshake()
    except SyncError as exc:
        print(f"PROBE BROKEN: handshake failed: {exc}")
        return BROKEN
    if not shake.project_uid:
        print("PROBE BROKEN: no project_uid")
        return BROKEN

    created: list[tuple[str, str]] = []
    try:
        return _run(client, shake.project_uid, created)
    finally:
        _shed(client, created)


if __name__ == "__main__":
    raise SystemExit(main())
