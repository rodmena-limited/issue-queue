#!/usr/bin/env python3
# VENDORED from Tracker contracts/sync/faketracker.py at e33c48b.
# DO NOT EDIT HERE. Copied so issuedb's client tests RUN rather than skip when
# the Tracker checkout is absent (CI, a fresh clone) -- a skipped test is a check
# that cannot go red. Refresh deliberately when the contract version changes.
# It is NOT Tracker: no tenancy, no authorization, no durability, no concurrency,
# and its database is a dict. Passing against it proves this client obeys
# PROTOCOL.md; it proves nothing about the real server.
"""FakeTracker — a reference sync server on the Python standard library alone.

Ticket #11. For `issuedb-ed3d5e`, so the client half can be built and tested with
no network, no Postgres, and no Tracker checkout.

    $ python3 faketracker.py --port 8099
    $ python3 faketracker.py --self-test        # replays every frozen vector

STDLIB ONLY, and that is a hard constraint rather than a preference. issuedb is a
zero-dependency project; a fixture that drags in a stack is one they cannot run,
and an unusable fixture is worse than none because it still looks like an option.
If this file ever needs a third-party import, it does not ship — the vectors ship
alone and the reason is stated.

WHAT THIS IS NOT. It is not Tracker. It has no tenancy, no authorization harness,
no durability and no concurrency control, and its "database" is a dict that dies
with the process. It exists to be a correct-enough counterparty for the RULES IN
`PROTOCOL.md` — idempotency, conflict outcomes, tombstones, cursor refusal,
revocation mid-sync. Passing against this proves a client obeys the contract; it
does not prove the client works against Tracker, and no test here should ever be
described as if it did.

The rules it implements are the ones a client can get wrong silently. Anything
that fails loudly against a real server is deliberately left out.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

PROTOCOL_MIN = 1
PROTOCOL_MAX = 1
TOMBSTONE_RETENTION_DAYS = 180

# Seeded credentials. key_id is a lowercase ULID and is NOT secret.
VALID_KEY = "trk_01k1x9m4rjq7v2n8p3d5wtzabc_s3cr3t"
REVOKED_KEY = "trk_01k1x9m4rjq7v2n8p3d5wtzxyz_r3v0k3d"

PROJECT_UID = "prj_01k1x9m4rjq7v2n8p3d5wtzqqq"

# The PRODUCTION vocabulary is empty in v1: relation_type is unvalidated free
# text in issuedb, so "which types are symmetric" is not answerable from the
# schema. See PROTOCOL.md §2.
#
# `x-test-symmetric` is a PROVISIONAL type that exists only here and in the
# vectors, never in production vocabulary. issuedb asked for it and the reason
# is the rule this project keeps rediscovering: with a genuinely empty set,
# vectors 8-10 exercise a code path no data can reach. They would be written,
# they would pass trivially, and a passing suite would be read as evidence the
# rule works. A check that cannot go green cannot go red. With this type the
# rule is exercised from day one instead of first running in front of a user.
#
# Tracker in production advertises the real (empty) set. A client MUST read
# `symmetric_relation_types` from the handshake and never hardcode one.
SYMMETRIC_RELATION_TYPES: frozenset[str] = frozenset({"x-test-symmetric"})


# --- the canonical form, which is the whole point of shipping this file -----


def derived_uid(entity: str, *fields: str) -> str:
    """The frozen canonicalisation from PROTOCOL.md §2.

    Length-prefixed, NFC-normalised, no separator, NO casefolding. A client that
    computes a different uid here will produce duplicate rows that nothing
    errors on, so this function is the single most important thing in the file.
    """
    tag = {"issue_tag": "itag", "issue_dependency": "idep", "issue_relation": "irel"}[entity]
    parts = [tag, *fields]
    canonical = b""
    for part in parts:
        raw = unicodedata.normalize("NFC", part).encode("utf-8")
        canonical += f"{len(raw)}:".encode() + raw
    return "s256t128:" + hashlib.sha256(canonical).hexdigest()[:32]


def relation_uid(
    project_uid: str,
    source: str,
    rel_type: str,
    target: str,
    symmetric: frozenset[str] = SYMMETRIC_RELATION_TYPES,
) -> str:
    """Symmetric types sort their endpoints; directional types keep position.

    `symmetric` is a PARAMETER on both sides now. Tracker's server-side
    canonicaliser and this file were derived from the same frozen vectors and
    STILL disagreed on their first cross-check, because this file's set contains
    the provisional test type and production's does not -- both implementations
    correct, the contract silently ambiguous about which applied. The vectors
    now declare `symmetric_types` per derivation. Hardcoding it would be the
    reference implementation making the exact mistake the handshake tells
    clients not to make.
    """
    if rel_type in symmetric:
        source, target = min(source, target), max(source, target)
    return derived_uid("issue_relation", project_uid, source, rel_type, target)


def relation_content_hash(
    source: str,
    rel_type: str,
    target: str,
    symmetric: frozenset[str] = SYMMETRIC_RELATION_TYPES,
    **rest: str,
) -> str:
    """The content hash for a relation. For SYMMETRIC types the endpoints are
    sorted, exactly as in the uid — so the endpoints do not identify the version.

    issuedb's D3, taken as written, and it is the better fix. The alternative was
    a special case: "for symmetric types, an opposite-direction push is a no-op."
    That works and it requires both codebases to remember the caveat forever, in
    an update path neither of them exercises often — and the vector for it passes
    only if both remembered.

    Excluding the endpoints from the hash instead makes an opposite-direction
    push produce an IDENTICAL (uid, content_hash). The idempotency clause that is
    already frozen then fires unmodified and "no-op, return the existing row"
    falls out of it. No special case anywhere, and the vector passes structurally
    rather than by two implementations agreeing to remember something.

    The direction still travels in the payload and is still stored. It is simply
    not part of what identifies the version — which is the frozen principle (uid
    is identity, direction is payload) carried one step further.
    """
    if rel_type in symmetric:
        source, target = min(source, target), max(source, target)
    fields = [source, rel_type, target, *(f"{k}={v}" for k, v in sorted(rest.items()))]
    raw = b""
    for field in fields:
        encoded = unicodedata.normalize("NFC", field).encode("utf-8")
        raw += f"{len(encoded)}:".encode() + encoded
    return "s256t128:" + hashlib.sha256(raw).hexdigest()[:32]


# --- state ------------------------------------------------------------------


class Store:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.seq = 0
        # Numbers that arrived on a PUSH, per project. The counter never issued
        # them, so it cannot be the authority on which numbers exist.
        self.pushed_numbers: dict[str, set[int]] = {}
        self.counters: dict[str, int] = {}
        # uid -> canonical number, so a replay is not mistaken for a collision.
        self.assigned_numbers: dict[str, dict[str, int]] = {}
        # Everything below this cursor has had its tombstones collected, so a
        # cursor older than it cannot be served without risking resurrection.
        self.horizon = 0
        self.revoked: set[str] = {REVOKED_KEY}

    def _next(self) -> int:
        self.seq += 1
        return self.seq

    def claim_issue_number(self, project: str, uid: str, wanted: int | None) -> dict[str, Any]:
        """Honour a pushed local number when free; alias it when taken.

        issuedb's finding, and it is the MAJORITY case rather than an edge. Two
        clones of a repo that commits `.issue.db` allocate `issues.id` from the
        same AUTOINCREMENT counter independently, so two developers working
        offline both mint `#3` for DIFFERENT issues. Both replicas are correct
        and neither did anything wrong. The first `#3` lands; the second cannot,
        and the earlier "the server shall never reissue a pushed number" clause
        made it UNSATISFIABLE -- a hard failure the second developer to sync a
        tracked repo could not resolve.

        Renumbering is closed off too: `git_utils.py:171 parse_issue_refs` reads
        `#123` out of COMMIT MESSAGES, which are immutable. Renumbering silently
        repoints every commit that referenced an issue at a different one -- it
        does not break loudly, it starts pointing at someone else's work.

        THE REFRAME THAT RESOLVES IT: the ambiguity already exists before any
        server. In that repo `#3` is ALREADY ambiguous between A's and B's. Sync
        does not create the collision, it makes it visible, so we are not obliged
        to preserve an invariant that was never true. What we must not do is
        silently repoint anything.

        So: uid is identity, THE NUMBER IS A LOCAL ALIAS.

          * a pushed number is taken as the canonical number when free;
          * when taken by a different uid, the server assigns the next free
            canonical number and RECORDS the pushed number as an alias;
          * an alias is keyed by (project, REPLICA, number) -- not by number
            alone, or the alias table has the very collision it exists to
            resolve, because both replicas claim `#3`;
          * a canonical number, once assigned, is never changed, and an alias is
            never repointed.

        A checkout then resolves `#3` through its own replica's aliases, which is
        deterministic and correct for that checkout's history; the server
        resolves it through the canonical number. Nothing is ever silently
        redirected, and no commit message stops meaning what it meant.
        """
        used = self.pushed_numbers.setdefault(project, set())
        assigned = self.assigned_numbers.setdefault(project, {})

        if wanted is not None and wanted not in used:
            used.add(wanted)
            assigned[uid] = wanted
            return {"number": wanted, "aliased": False}

        if wanted is not None and assigned.get(uid) == wanted:
            # A replay of the same entry, not a collision.
            return {"number": wanted, "aliased": False}

        canonical = self.next_issue_number(project)
        return {"number": canonical, "aliased": True, "local_number": wanted}

    def next_issue_number(self, project: str) -> int:
        """Allocate a number the way a SERVER-SIDE create must.

        GREATEST(counter, max pushed number) + 1, never counter + 1. A pushed
        issue carries the number it had in `.issue.db`; the server's counter
        never issued it and does not know about it. Allocating from the counter
        alone reissues a number that already exists.

        This is a CONTRACT fact rather than a server implementation detail,
        which is why it is modelled here: a client may push any local number and
        must be able to rely on the server not reusing it afterwards. Tracker
        shipped the counter-only version and it 500'd on the first real request
        against a database holding pushed rows.
        """
        used = self.pushed_numbers.setdefault(project, set())
        counter = self.counters.get(project, 0)
        number = max(counter, max(used) if used else 0) + 1
        self.counters[project] = number
        used.add(number)
        return number

    def record_pushed_number(self, project: str, number: int | None) -> None:
        if number is not None:
            self.pushed_numbers.setdefault(project, set()).add(int(number))

    def apply(self, entry: dict[str, Any]) -> dict[str, Any]:
        """One push entry. The outcome vocabulary IS the contract."""
        uid = entry["uid"]
        op = entry.get("op", "upsert")
        payload = entry.get("payload") or {}
        number_result: dict[str, Any] | None = None
        if entry.get("entity", "issue") == "issue" and payload.get("number") is not None:
            number_result = self.claim_issue_number(
                str(payload.get("project", "default")), uid, int(payload["number"])
            )
        content_hash = entry.get("content_hash")
        existing = self.rows.get(uid)

        if op == "delete":
            if existing is None:
                # Deleting something we never saw is not an error: absence is
                # not evidence, and refusing here would make a retried delete
                # look like corruption.
                self.rows[uid] = {
                    "uid": uid,
                    "entity": entry.get("entity", "issue"),
                    "version": 1,
                    "content_hash": content_hash,
                    "payload": entry.get("payload", {}),
                    "deleted": True,
                    "seq": self._next(),
                }
                return {"uid": uid, "version": 1, "outcome": "deleted"}
            existing["deleted"] = True
            existing["version"] += 1
            existing["seq"] = self._next()
            # The payload is KEPT. A tombstone with no last-known value is an
            # unrecoverable delete, and with N offline replicas that is not a
            # tradeoff anyone gets to make on a user's behalf.
            return {"uid": uid, "version": existing["version"], "outcome": "deleted"}

        if existing is None:
            self.rows[uid] = {
                "uid": uid,
                "entity": entry.get("entity", "issue"),
                "version": 1,
                "content_hash": content_hash,
                "payload": entry.get("payload", {}),
                "deleted": False,
                "seq": self._next(),
            }
            created: dict[str, Any] = {"uid": uid, "version": 1, "outcome": "created"}
            if number_result is not None:
                created["number"] = number_result["number"]
                # The client is TOLD when its local number was aliased, so it can
                # display "#3 (TRK-118)" rather than silently disagreeing with
                # the server about what #3 means.
                if number_result["aliased"]:
                    created["number_aliased"] = True
                    created["local_number"] = number_result["local_number"]
            return created

        if existing["deleted"]:
            # Delete wins, recoverably -- and the response CARRIES THE TOMBSTONE.
            #
            # issuedb's D4. A bare "here is the existing row" is not enough: a
            # replica that was offline through the delete pushes its own copy,
            # reads 200, and keeps a local row the server considers deleted. Its
            # next pull shows no change, because absence is not deletion. The row
            # then lives locally forever, undeletable, with nothing erroring.
            #
            # `deleted: True` is what lets the client tell "your write is already
            # there" from "your write is superseded by a delete".
            return {
                "uid": uid,
                "version": existing["version"],
                "outcome": "gone",
                "deleted": True,
                "restorable": True,
                "tombstone": {"payload": existing["payload"], "version": existing["version"]},
            }

        # NOTE the absence of a special case for issue_relation here. There was
        # one, and issuedb (D3) replaced it with something better: symmetric
        # relations exclude their endpoints from the content hash, so an
        # opposite-direction push arrives as an ordinary replay and the clause
        # below handles it with no relation-specific code at all. See
        # `relation_content_hash`.

        if existing["content_hash"] == content_hash:
            # THE REPLAY CASE. A different replica pushing work already applied
            # gets the existing version. A spurious 409 here is as broken as a
            # duplicate, and it is the failure the git-tracked outbox produces.
            return {"uid": uid, "version": existing["version"], "outcome": "existing"}

        base = entry.get("base_version")
        if base is not None and base != existing["version"]:
            # The losing value is preserved, never dropped.
            existing.setdefault("conflicts", []).append(
                {"base_version": base, "payload": entry.get("payload", {})}
            )
            existing["seq"] = self._next()
            return {
                "uid": uid,
                "version": existing["version"],
                "outcome": "conflict",
                "losing_value_retained": True,
            }

        existing["content_hash"] = content_hash
        existing["payload"] = entry.get("payload", {})
        existing["version"] += 1
        existing["seq"] = self._next()
        return {"uid": uid, "version": existing["version"], "outcome": "updated"}


# --- transport --------------------------------------------------------------


def problem(code: str, title: str, status: int, detail: str = "") -> tuple[int, dict[str, Any]]:
    return status, {
        "type": f"about:blank#{code}",
        "title": title,
        "status": status,
        "code": code,
        "detail": detail,
    }


class Handler(BaseHTTPRequestHandler):
    store: Store

    def log_message(self, *args: Any) -> None:  # keep the console quiet
        pass

    # -- helpers

    def _auth(self) -> tuple[int, dict[str, Any]] | None:
        raw = self.headers.get("Authorization", "")
        if not raw.startswith("Bearer trk_"):
            return problem("invalid_api_key", "Invalid API Key", 401, "malformed or missing")
        key = raw[len("Bearer ") :]
        if key in self.store.revoked:
            # Deliberately the SAME code and body as an unknown key: telling an
            # unauthenticated caller that a key EXISTS but is revoked is an
            # enumeration oracle.
            return problem("invalid_api_key", "Invalid API Key", 401, "malformed or missing")
        if key != VALID_KEY:
            return problem("invalid_api_key", "Invalid API Key", 401, "malformed or missing")
        return None

    def _protocol(self) -> tuple[int, dict[str, Any]] | None:
        raw = self.headers.get("X-IssueDB-Protocol")
        if raw is None:
            return None
        try:
            version = int(raw)
        except ValueError:
            return problem("protocol_unsupported", "Protocol Unsupported", 409, f"bad: {raw!r}")
        if not PROTOCOL_MIN <= version <= PROTOCOL_MAX:
            return problem(
                "protocol_unsupported",
                "Protocol Unsupported",
                409,
                f"this server speaks {PROTOCOL_MIN}..{PROTOCOL_MAX}",
            )
        return None

    def _send(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode()
        ctype = "application/problem+json" if status >= 400 else "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    # -- routes

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/v1/sync/handshake":
            # Preflight is UNAUTHENTICATED on purpose: a client must be able to
            # discover a protocol mismatch before it has a usable credential,
            # and before it writes anything locally.
            failed = self._protocol()
            if failed:
                return self._send(*failed)
            return self._send(
                200,
                {
                    "protocol_min": PROTOCOL_MIN,
                    "protocol_max": PROTOCOL_MAX,
                    "project_uid": PROJECT_UID,
                    "tombstone_retention_days": TOMBSTONE_RETENTION_DAYS,
                    "symmetric_relation_types": sorted(SYMMETRIC_RELATION_TYPES),
                    "uid_algorithm": "s256t128",
                },
            )

        if parsed.path == "/v1/sync/pull":
            for check in (self._protocol(), self._auth()):
                if check:
                    return self._send(*check)
            raw = parse_qs(parsed.query).get("cursor", ["c:0"])[0]
            try:
                cursor = int(raw.split(":", 1)[1])
            except (IndexError, ValueError):
                return self._send(*problem("bad_cursor", "Bad Cursor", 400, raw))
            if cursor < self.store.horizon:
                # REFUSING is the load-bearing half. Serving this cursor would
                # let a replica that sat untouched past the horizon re-create
                # everything the team deleted, with no error at any point.
                return self._send(
                    *problem(
                        "cursor_too_old",
                        "Cursor Too Old",
                        409,
                        "re-seed required; tombstones past this cursor have been collected",
                    )
                )
            rows = sorted(
                (r for r in self.store.rows.values() if r["seq"] > cursor),
                key=lambda r: r["seq"],
            )
            return self._send(
                200,
                {
                    "changes": rows,
                    "cursor": f"c:{self.store.seq}",
                    "safe_horizon": f"c:{self.store.seq}",
                    "has_more": False,
                },
            )

        self._send(*problem("not_found", "Not Found", 404, parsed.path))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/v1/sync/push":
            return self._send(*problem("not_found", "Not Found", 404, parsed.path))
        for check in (self._protocol(), self._auth()):
            if check:
                return self._send(*check)
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")

        results = []
        for entry in payload.get("entries", []):
            results.append(self.store.apply(entry))
        # The cursor advances only to what was DURABLY applied.
        self._send(200, {"results": results, "cursor": f"c:{self.store.seq}"})


# --- self-test: the vectors are executable or they are fiction ---------------


def _replay(store: Store, step: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Run one vector step against the Store directly, no socket needed."""
    req = step["request"]
    if req["path"].startswith("/v1/sync/push"):
        if req.get("key") == "revoked":
            return problem("invalid_api_key", "Invalid API Key", 401, "malformed or missing")
        return 200, {
            "results": [store.apply(e) for e in req["body"]["entries"]],
            "cursor": f"c:{store.seq}",
        }
    if req["path"].startswith("/v1/issues"):
        # A SERVER-SIDE create -- what the web UI does. Modelled here because the
        # collision only appears at the seam between a pushed issue and a
        # locally created one, and no sync-only vector can reach that seam.
        project = req.get("project", "default")
        return 200, {"number": store.next_issue_number(project)}

    if req["path"].startswith("/v1/sync/pull"):
        cursor = int(parse_qs(urlparse(req["path"]).query).get("cursor", ["c:0"])[0].split(":")[1])
        if cursor < store.horizon:
            return problem("cursor_too_old", "Cursor Too Old", 409, "re-seed required")
        rows = sorted((r for r in store.rows.values() if r["seq"] > cursor), key=lambda r: r["seq"])
        return 200, {"changes": rows, "cursor": f"c:{store.seq}"}
    raise AssertionError(f"vector uses an unknown path: {req['path']}")


def _http_smoke() -> int:
    """Drive the real HTTP surface on an ephemeral port. Returns a failure count."""
    import threading
    import urllib.error
    import urllib.request

    Handler.store = Store()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    failures = 0

    def call(
        path: str, body: dict[str, Any] | None = None, key: str | None = VALID_KEY, proto: str = "1"
    ) -> tuple[int, dict[str, Any], str]:
        req = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            method="POST" if body is not None else "GET",
        )
        req.add_header("X-IssueDB-Protocol", proto)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read()), resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read()), exc.headers.get("Content-Type", "")

    def check(label: str, got: Any, want: Any) -> None:
        nonlocal failures
        if got != want:
            print(f"FAIL http:{label}: {got!r} != {want!r}")
            failures += 1

    try:
        status, body, _ = call("/v1/sync/handshake", key=None)
        check("handshake status", status, 200)
        check("handshake uid_algorithm", body.get("uid_algorithm"), "s256t128")
        # Empty in v1 and a client must READ it rather than hardcoding one.
        # A client must READ this list rather than hardcoding one. FakeTracker
        # advertises the provisional test type; Tracker in production advertises
        # the real (empty) set. A client that hardcodes either is wrong.
        check(
            "handshake advertises the symmetric set",
            body.get("symmetric_relation_types"),
            ["x-test-symmetric"],
        )

        status, body, _ = call("/v1/sync/handshake", key=None, proto="99")
        check("protocol mismatch status", status, 409)
        check("protocol mismatch code", body.get("code"), "protocol_unsupported")

        entry = {
            "uid": "s256t128:" + "0" * 32,
            "entity": "issue",
            "op": "upsert",
            "content_hash": "h1",
            "payload": {"title": "smoke"},
        }
        status, body, _ = call("/v1/sync/push", {"entries": [entry]})
        check("push status", status, 200)
        check("push outcome", body["results"][0]["outcome"], "created")
        status, body, _ = call("/v1/sync/push", {"entries": [entry]})
        check("replayed push is a no-op", body["results"][0]["outcome"], "existing")

        status, body, ctype = call("/v1/sync/push", {"entries": []}, key=REVOKED_KEY)
        check("revoked status", status, 401)
        check("revoked code", body.get("code"), "invalid_api_key")
        # The envelope is part of the contract: a client that branches on `code`
        # cannot do so if an error arrives as text/html from an edge proxy.
        check("problem envelope", ctype.split(";")[0], "application/problem+json")

        status, body, _ = call("/v1/sync/pull?cursor=c:0")
        check("pull status", status, 200)
        check("pull returned the pushed row", len(body["changes"]), 1)
    finally:
        server.shutdown()
        server.server_close()

    if not failures:
        print(
            "  ok  http surface                     handshake, protocol 409, push, replay, 401, pull"
        )
    return failures


def self_test(directory: Path) -> int:
    """Replay every frozen vector. Exit non-zero on the first mismatch.

    A vector nobody runs is a comment. This is what makes the files in
    `vectors/` a contract rather than documentation of an intention.
    """
    files = sorted(directory.glob("*.json"))
    if not files:
        # An empty run reporting success is the exact vacuous-check failure this
        # project keeps finding, so it is a hard error.
        print(f"FAIL: no vectors found in {directory}", file=sys.stderr)
        return 2

    failures = 0
    derivations_checked = 0
    for path in files:
        vector = json.loads(path.read_text())
        store = Store()
        store.horizon = vector.get("setup", {}).get("horizon", 0)

        # RE-DERIVE, never replay. The first version of this self-test only
        # replayed the uids written into the vectors, so reintroducing the
        # casefold defect -- the exact bug vector 7 exists to catch -- left it
        # GREEN. A vector that hardcodes the answer cannot check the function
        # that produces it. Found by pointing a known-negative at it, which is
        # the only reason it is not still true.
        for spec in vector.get("uid_derivation", []):
            derivations_checked += 1
            if "distinct" in spec:
                if len(set(spec["distinct"])) != len(spec["distinct"]):
                    print(f"FAIL {path.name}: values that must differ are equal -- {spec['note']}")
                    failures += 1
                continue
            if "equal" in spec:
                if len(set(spec["equal"])) != 1:
                    print(f"FAIL {path.name}: values that must match differ -- {spec['note']}")
                    failures += 1
                continue
            # The symmetric set comes from the VECTOR, not from this module's
            # constant -- see relation_uid's docstring for the divergence that
            # forced it.
            sym = frozenset(spec.get("symmetric_types", ()))
            if spec.get("kind") == "relation_content_hash":
                # Unpacked positionally: `*fields, symmetric=` reads as a
                # possible duplicate binding, because `symmetric` is also a
                # positional parameter.
                src, rtype, tgt = spec["fields"]
                got = relation_content_hash(src, rtype, tgt, sym)
            elif spec["entity"] == "issue_relation":
                proj, src, rtype, tgt = spec["fields"]
                got = relation_uid(proj, src, rtype, tgt, sym)
            else:
                got = derived_uid(spec["entity"], *spec["fields"])
            if got != spec["expect"]:
                print(f"FAIL {path.name}: derived {got}, frozen {spec['expect']}")
                failures += 1

        for index, step in enumerate(vector["steps"]):
            status, body = _replay(store, step)
            want = step["response"]
            if status != want["status"]:
                print(f"FAIL {path.name} step {index}: status {status} != {want['status']}")
                failures += 1
                continue
            for key, expected in want.get("body", {}).items():
                actual = body.get(key)
                if actual != expected:
                    print(f"FAIL {path.name} step {index}: {key} = {actual!r}, want {expected!r}")
                    failures += 1
        if not failures:
            print(f"  ok  {path.stem:<32} {vector['why'][:70]}")

    # EXERCISE THE SOCKET, not only the Store. Everything above replays vectors
    # in-process, which proves the RULES and proves nothing about the thing
    # issuedb will actually run. A handler that 500s on every request would have
    # passed every check above -- the same "verify the served artifact, not its
    # generator" rule that this project applies to its own deploys.
    failures += _http_smoke()

    if not derivations_checked:
        # The derivation checks are what make the canonical form testable at
        # all. Zero of them running is the vacuous case, so it is an error.
        print("FAIL: no uid derivations were checked", file=sys.stderr)
        return 2

    print(f"\n{len(files)} vectors, {derivations_checked} uid derivations, {failures} failure(s)")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--vectors", type=Path, default=Path(__file__).parent / "vectors")
    args = parser.parse_args()

    if args.self_test:
        return self_test(args.vectors)

    Handler.store = Store()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"FakeTracker on http://127.0.0.1:{args.port}  key={VALID_KEY}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
