# First-contact probe harness for the live Tracker sync API

- **Ticket:** issuedb #7
- **Script:** `audit/evaluations/first_contact_probe.py`
- **Run:** `python3 audit/evaluations/first_contact_probe.py`

## EARS spec

- The first-contact probe shall issue control requests to endpoints known to exist before probing the sync endpoints.
- If a control request does not succeed, then the probe shall report PROBE BROKEN and shall not report any conclusion about the sync endpoints.
- The probe shall distinguish NOT IMPLEMENTED (the endpoint is absent) from FAILED (the endpoint exists and behaves wrongly).
- The probe shall report the served commit of the host it probed.
- The probe shall state whether a passing result came from the production host or another server, and shall never present a non-production result as first contact.
- The probe shall exit non-zero when a control fails or when an implemented endpoint behaves wrongly, and shall exit zero when endpoints are merely absent.
- The probe shall depend on the Python standard library only.

## Why the controls are the load-bearing part

A 404 from a misconfigured probe looks exactly like a 404 from a missing route.
Without controls, "Tracker has not implemented this" is an unfounded accusation
against another team. The probe proves it can reach endpoints known to exist
before it says anything about the ones that are missing.

## Verification: all four verdicts proven reachable

A probe that has only ever produced one verdict is a check that cannot go red.
Each path was exercised and the exit code captured directly (not through a
pipe — `$?` after a pipeline reports the *last* command's status, which
silently invalidated an earlier reading of mine).

| Target | Verdict | Exit |
|---|---|---|
| Live Tracker (`acab54e`) | `NOT IMPLEMENTED` | 0 |
| Unreachable port | `PROBE BROKEN` | 2 |
| Local FakeTracker | round trip succeeded, **explicitly not first contact** | 0 |
| Stub answering with `uid_algorithm: md5`, empty `project_uid`, zero retention | `FAILED`, three DIVERGENCE lines | 1 |

## A defect in the probe, found by running it

The first working version printed **"TWO IMPLEMENTATIONS HAVE EXCHANGED A
BYTE"** on a green run against FakeTracker. That is false: FakeTracker is a
fixture written from the same document as the client, so a pass there is the
fixture agreeing with itself.

The probe now branches on whether the target is the production host, prints a
`NON-PRODUCTION TARGET` banner up front, and refuses to use the words "first
contact" for anything else. A probe that overclaims is worse than no probe,
because its output is what gets quoted.

## Incidental findings while building it

- **`8099` is nginx** on this host. Binding a test server there would have
  collided with a real service; the failure surfaced as `Address already in
  use`, and the port was checked rather than force-freed.
- **`8123` is the `rodmena.co.uk` node server** (pid checked before any kill).
  Two ports that looked free were both real services — `ss -ltnp` and `ps -p`
  before `kill`, every time.
- Test servers now bind port `0` and let the OS choose.
