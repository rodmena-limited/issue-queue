#!/usr/bin/env python3
"""Does this client send fields the frozen contract never mentions?

The question this answers was asked by the manager and I could not answer it:
my client sends ``replica_id`` on push, and ``replica_id`` appears ZERO times
in ``openapi.yaml`` and ZERO times in ``faketracker.py``. So where did my
client learn it?

From a bus message and a live 422. Not from the schema. Which means the field
arrived by a path NO FIXTURE CAN CHECK — the fixture accepts a body without it,
the server requires it, and both of my suites were green throughout.

That is the ``project_uid`` incident with the sign flipped: that was
documented-and-absent, this is required-and-undocumented. Same root cause, the
document and the server drifting with nothing comparing them.

This compares MY CLIENT'S REQUEST SHAPE against the contract's declared schema
and reports fields in one and not the other. It cannot tell which side is
right — the manager ruled the server correct and the contract stale here — but
it makes the drift visible instead of leaving it to be discovered by a 422 in
production.

Standard library only: the contract is YAML, and rather than take a dependency
this reads the small, regular subset it needs.
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
# The VENDORED contract, not the peer's working tree.
#
# This pointed at /home/farshid/develop/Tracker/contracts/sync/openapi.yaml —
# a file another agent edits mid-turn. A drift verdict measured against it
# judges something neither committed nor deployed, and it produced exactly
# that error once: I reported replica_id as "fixed in 61a3b66" when it was in
# NO committed revision at all, only in the uncommitted tree I had grepped.
CONTRACT = REPO_ROOT / "tests" / "data" / "openapi.yaml"
VENDORED_AT = "29c461d"
VENDORED_FAKE = REPO_ROOT / "tests" / "data" / "faketracker.py"

# What this client actually puts in each request body. Kept here rather than
# introspected, so that adding a field to the client without adding it here is
# itself caught by review.
CLIENT_SENDS = {
    "/v1/sync/push": {"replica_id", "entries"},
}

# Handshake response fields this client actually reads. Listed here rather than
# introspected so that a field appearing in the contract and NOT here is
# reported — which is precisely how `entities` would have been caught.
CLIENT_READS_HANDSHAKE = {
    "protocol_min",
    "protocol_max",
    "project_uid",
    "symmetric_relation_types",
    "tombstone_retention_days",
    "uid_algorithm",
    "authenticated",
    "credential_rejected",
    "entities",
}


def declared_required(text: str, path: str) -> set[str] | None:
    """The requestBody's `required:` list for one path, or None if not found.

    Reads the REQUIRED list specifically rather than trying to enumerate
    properties. An earlier version scraped indented `name:` keys and happily
    returned `type`, `items` and `description` as if they were fields — a
    parser whose output contains obvious garbage cannot be trusted for its
    verdict, even when the verdict is accidentally right.

    Returns None rather than an empty set when nothing is found, so "the parse
    failed" stays distinguishable from "the schema requires nothing".
    """
    start = text.find(f"\n  {path}:")
    if start == -1:
        return None
    end = text.find("\n  /", start + 1)
    block = text[start : end if end != -1 else len(text)]

    request_body = block.find("requestBody:")
    if request_body == -1:
        return None
    responses = block.find("responses:", request_body)
    body_block = block[request_body : responses if responses != -1 else len(block)]

    match = re.search(r"required:\s*\[([^\]]*)\]", body_block)
    if not match:
        return None
    return {f.strip().strip("'\"") for f in match.group(1).split(",") if f.strip()}


def handshake_response_fields(text: str) -> set[str] | None:
    """Property names the contract declares on the handshake RESPONSE.

    The request-side comparison has a blind spot the manager named: it checks
    what this client SENDS against what the contract REQUIRES, so a
    RESPONSE-side addition is invisible to it. `entities` was added to the
    handshake and shipped, and the drift check said "no drift" throughout —
    correctly, and uselessly, because it was answering a different question.
    """
    start = text.find("\n  /v1/sync/handshake:")
    if start == -1:
        return None
    end = text.find("\n  /", start + 1)
    block = text[start : end if end != -1 else len(text)]
    properties = block.find("properties:")
    if properties == -1:
        return None
    # Anchor to the FIRST indent level under `properties:` — not "18 or more
    # spaces", which is how the earlier version returned `type`, `description`,
    # `enum`, `example` and `items` as if they were response fields. That is
    # the same scraping defect I had already fixed once on the request side by
    # reading `required:` instead of guessing, and I reproduced it one function
    # over. A parser whose output contains obvious garbage cannot be trusted
    # for its verdict even when the verdict looks plausible.
    tail = block[properties:].splitlines()[1:]
    indents = [len(ln) - len(ln.lstrip()) for ln in tail if ln.strip() and ln.lstrip()[0] != "#"]
    if not indents:
        return None
    field_indent = indents[0]
    names = [
        ln.strip().split(":", 1)[0]
        for ln in tail
        if ln.strip()
        and len(ln) - len(ln.lstrip()) == field_indent
        and re.match(r"^[a-z_][a-z0-9_]*:", ln.strip())
    ]
    return set(names) or None


def main() -> int:
    if not CONTRACT.exists():
        print(f"CONTRACT NOT FOUND at {CONTRACT} — cannot compare. Not a pass.")
        return 2

    text = CONTRACT.read_text()
    fake = VENDORED_FAKE.read_text() if VENDORED_FAKE.exists() else ""
    print(f"contract: {CONTRACT}")
    print(f"  vendored from Tracker commit {VENDORED_AT} "
          f"— every verdict below judges THAT contract, not a live tree")

    drift = 0
    for path, sends in CLIENT_SENDS.items():
        required = declared_required(text, path)
        print(f"\n{path}")
        print(f"  client sends      : {sorted(sends)}")

        # Control: a failed parse must not read as "nothing is required".
        if required is None:
            print("  PARSE FAILED — no requestBody `required:` list found for this path.")
            print("  This check cannot conclude anything. Not a pass.")
            return 2

        print(f"  contract requires : {sorted(required)}")

        undocumented = sorted(sends - required)
        missing = sorted(required - sends)
        for field in undocumented:
            in_fake = "yes" if field in fake else "NO"
            print(
                f"  DRIFT: '{field}' is sent by this client and is NOT in the contract's "
                f"required list (present in vendored faketracker: {in_fake})"
            )
            drift += 1
        for field in missing:
            print(f"  DRIFT: the contract requires '{field}' and this client does not send it")
            drift += 1

    # RESPONSE side: fields the contract declares that this client ignores.
    # Not automatically a defect — a client may legitimately not need a field —
    # but it is exactly how `entities` shipped and went unread for a release.
    declared = handshake_response_fields(text)
    print("\n/v1/sync/handshake (response)")
    if declared is None:
        print("  PARSE FAILED — cannot list declared response fields. Not a pass.")
        return 2
    print(f"  contract declares : {sorted(declared)}")
    print(f"  client reads      : {sorted(CLIENT_READS_HANDSHAKE)}")
    ignored = sorted(declared - CLIENT_READS_HANDSHAKE)
    for field in ignored:
        print(f"  UNREAD: the contract declares '{field}' and this client never reads it")
        drift += 1

    if drift:
        print(
            f"\n{drift} drift(s). A field known to the client but not the contract was "
            f"learned from prose, an example, or a live error — a path no fixture checks."
        )
        return 1

    print("\nNo drift: what this client sends matches what the contract requires.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
