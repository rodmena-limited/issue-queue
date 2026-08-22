"""Do issuedb and Tracker normalise the SAME way?

PROTOCOL.md mandates NFC in five places. Both implementations implement it.
NOTHING PROVES THEY AGREE — every frozen vector is pure ASCII, where NFC is the
identity function, so every green in the suite is equally green against an
implementation that skips normalisation entirely.

If they disagree, a composed and a decomposed spelling of one tag derive
DIFFERENT uids, create two rows where one was meant, in both databases, and
never converge — with nothing erroring on either side.

WHAT THIS PROBE CAN AND CANNOT PROVE — read this before trusting a green.

MEASURED, 2026-08-21: the sync API TRUSTS THE CLIENT-SUPPLIED UID. Pushing a
tag under a deliberately bogus uid returns that same bogus uid, not the uid the
server would have derived. So a push round trip CANNOT settle whether the
server normalises: both sides are keying off bytes issuedb chose.

    we sent   s256t128:ffffffffffffffffffffffffffffffff
    correct   s256t128:ff456ab52b338194e41b4d7a36071190
    server    s256t128:ffffffffffffffffffffffffffffffff   <- ours, echoed

Therefore this probe proves exactly two things, and claims no more:

    1. issuedb derives ONE uid for both normal forms (our side is correct), and
       a non-normalising client demonstrably derives TWO — so the input can
       discriminate and the check is not vacuous.
    2. Pushing both forms converges to a single server row, so no duplicate is
       created THROUGH THIS PATH.

It does NOT prove Tracker's own derivation normalises. That can only be settled
by a surface where the SERVER derives the uid — the web UI creating a tag, or a
server-side derivation endpoint — and comparing that uid against ours.

THE PROBE WRITES TO A PEER'S PRODUCTION DATABASE, SO IT CLEANS UP ON EVERY
PATH. The rows it needs cannot be reused between runs: the NFC test requires a
uid the server has never seen, so a fresh endpoint issue and two fresh tag rows
are created per run. Earlier versions deleted none of them on ANY path — six
rows were left in Tracker's feed and a peer removed them for us. Cleanup now
runs in a ``finally``, so the PROBE BROKEN exit sheds its rows exactly like the
two verdicts do; `tracker-fbe1b4` found the same asymmetry in their browser
probes, where only the honest exit leaked.

THREE STATES, not two:
    exit 0  both forms converge to one row via push     — no duplicate here
    exit 1  the second push created a second row        — a real defect
    exit 2  could not establish the precondition        — PROBE BROKEN, no verdict
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
BROKEN, AGREE, DISAGREE = 2, 0, 1


def naive_uid(entity: str, *fields: str) -> str:
    """A uid derived WITHOUT normalisation — the control.

    This is what a non-normalising client produces. If it equals the real
    derivation for our test input, the input cannot discriminate and the whole
    probe is vacuous.
    """
    import hashlib

    tags = {"issue_tag": "itag"}
    raw = b""
    for field in (tags[entity], *fields):
        encoded = field.encode("utf-8")  # NO unicodedata.normalize
        raw += f"{len(encoded)}:".encode() + encoded
    return "s256t128:" + hashlib.sha256(raw).hexdigest()[:32]


def _probe(created: list[tuple[str, str]], box: list[SyncClient]) -> int:
    server = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER).rstrip("/")
    cred = load_credential(server)
    if cred is None:
        print(f"PROBE BROKEN: not signed in to {server}")
        return BROKEN
    client = SyncClient(server, token=cred.token)
    box.append(client)

    try:
        shake = client.handshake()
    except SyncError as exc:
        print(f"PROBE BROKEN: handshake failed: {exc}")
        return BROKEN
    project = shake.project_uid
    if not project:
        print("PROBE BROKEN: no project_uid; every derived uid needs it as field 1")
        return BROKEN

    # A tag whose two normal forms differ. Fresh per run, so the push under
    # test is the write under test and not a replay of history.
    salt = uuid.uuid4().hex[:8]
    nfc = unicodedata.normalize("NFC", f"café-{salt}")
    nfd = unicodedata.normalize("NFD", f"café-{salt}")

    print("INPUT CONTROL — the two forms must actually differ:")
    print(f"  NFC bytes {nfc.encode()!r}")
    print(f"  NFD bytes {nfd.encode()!r}")
    if nfc == nfd:
        print("  PROBE BROKEN: the two forms are identical; nothing to discriminate")
        return BROKEN
    print("  differ: YES\n")

    # The issue the tag hangs on must exist server-side first.
    issue_uid = "s256t128:" + uuid.uuid4().hex[:32]
    try:
        res = client.push(
            [{"uid": issue_uid, "entity": "issue", "op": "upsert",
              "content_hash": uuid.uuid4().hex,
              "payload": {"title": f"NFC cross-impl probe {salt}"}}],
            replica_id="issuedb-nfc-probe",
        )
    except SyncError as exc:
        print(f"PROBE BROKEN: could not create the endpoint issue: {exc}")
        return BROKEN
    if not res or res[0].get("outcome") != "created":
        print(f"PROBE BROKEN: endpoint issue not created: {res}")
        return BROKEN
    created.append(("issue", issue_uid))
    print(f"precondition: endpoint issue created ({res[0].get('number')})\n")

    uid_nfc = derived_uid("issue_tag", project, issue_uid, nfc)
    uid_nfd = derived_uid("issue_tag", project, issue_uid, nfd)

    print("OUR DERIVATION:")
    print(f"  uid(NFC) {uid_nfc}")
    print(f"  uid(NFD) {uid_nfd}")
    print(f"  equal: {uid_nfc == uid_nfd}")

    # THE CONTROL THAT MAKES A GREEN MEAN SOMETHING. A client that skips
    # normalisation must produce DIFFERENT uids for these two inputs —
    # otherwise the input cannot tell a normalising server from a
    # non-normalising one, and any agreement below is luck.
    bad_nfc = naive_uid("issue_tag", project, issue_uid, nfc)
    bad_nfd = naive_uid("issue_tag", project, issue_uid, nfd)
    print("\nRED CONTROL — a client that SKIPS normalisation:")
    print(f"  uid(NFC) {bad_nfc}")
    print(f"  uid(NFD) {bad_nfd}")
    if bad_nfc == bad_nfd:
        print("  PROBE BROKEN: even without normalising the uids match; input cannot discriminate")
        return BROKEN
    print("  differ: YES — so this input CAN expose a non-normalising implementation\n")

    def push_tag(uid: str, tag_name: str, label: str) -> dict[str, Any] | None:
        try:
            out = client.push(
                [{"uid": uid, "entity": "issue_tag", "op": "upsert",
                  "content_hash": "nfc-probe-h1",
                  "payload": {"issue_uid": issue_uid, "tag_name": tag_name}}],
                replica_id="issuedb-nfc-probe",
            )
        except SyncError as exc:
            print(f"  {label}: push failed: {exc}")
            return None
        if out and out[0].get("outcome") in ("created", "existing"):
            created.append(("issue_tag", uid))
        return out[0] if out else None

    print("THE SERVER'S ANSWER — only it can settle this:")
    first = push_tag(uid_nfc, nfc, "NFC push")
    if first is None:
        return BROKEN
    print(f"  push NFC form -> {first}")
    if first.get("outcome") != "created":
        print("  PROBE BROKEN: the first push was not 'created'; uid was not novel")
        return BROKEN

    second = push_tag(uid_nfd, nfd, "NFD push")
    if second is None:
        return BROKEN
    print(f"  push NFD form -> {second}")

    outcome = second.get("outcome")
    print()
    if outcome == "existing":
        print("VERDICT: NO DUPLICATE VIA PUSH — and that is ALL this proves.")
        print("  The NFD form resolved to the row the NFC form created. But the server")
        print("  TRUSTS the uid we send (measured: a bogus uid comes back unchanged),")
        print("  so both pushes keyed off OUR derivation. This shows issuedb normalises")
        print("  and does not create duplicates; it does NOT show that Tracker's own")
        print("  derivation normalises. That needs a surface where the SERVER derives")
        print("  the uid — the web UI creating a tag — compared against ours.")
        return AGREE
    if outcome == "created":
        print("VERDICT: THEY DISAGREE — this is a real defect.")
        print("  The NFD form created a SECOND row. Composed and decomposed spellings")
        print("  of one tag are two rows in both databases, and they will never")
        print("  converge, with nothing erroring on either side.")
        return DISAGREE
    print(f"PROBE BROKEN: unexpected outcome {outcome!r}")
    return BROKEN


def _shed(box: list[SyncClient], created: list[tuple[str, str]]) -> None:
    """Delete every row this run created, whatever the verdict was.

    Verified against a known-positive before being relied on: ``op: "delete"``
    returns ``outcome: "deleted"`` and the row appears tombstoned in a
    subsequent pull. ``op: "tombstone"`` and ``op: "remove"`` are rejected with
    ``invalid_request``, so a typo here fails loudly rather than silently
    skipping the cleanup.
    """
    if not box or not created:
        return
    client = box[0]
    failed = []
    for entity, uid in reversed(created):
        try:
            out = client.push(
                [{"uid": uid, "entity": entity, "op": "delete",
                  "content_hash": uuid.uuid4().hex, "payload": {}}],
                replica_id="issuedb-nfc-probe",
            )
        except SyncError as exc:
            failed.append(f"{entity} {uid}: {exc}")
            continue
        if not out or out[0].get("outcome") != "deleted":
            failed.append(f"{entity} {uid}: {out}")
    print(f"\ncleanup: {len(created) - len(failed)}/{len(created)} probe rows deleted")
    for line in failed:
        # Loud, because a silent cleanup failure is how the debris accumulated
        # in the first place.
        print(f"  CLEANUP FAILED: {line}", file=sys.stderr)


def main() -> int:
    created: list[tuple[str, str]] = []
    box: list[SyncClient] = []
    try:
        return _probe(created, box)
    finally:
        _shed(box, created)


if __name__ == "__main__":
    raise SystemExit(main())
