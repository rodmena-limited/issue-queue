# signin / signout: Tracker credentials outside the database

- **Ticket:** issuedb #4
- **Version:** 2.15.0
- **Modules:** `issuedb/sync/_credentials.py`, `issuedb/sync/_auth_commands.py`
- **Tests:** `tests/test_sync_credentials.py`

## EARS spec

- The issuedb CLI shall store Tracker credentials in `$XDG_CONFIG_HOME/issuedb/` (defaulting to `~/.config/issuedb/`), never inside `.issue.db` and never in the working directory.
- When the user runs signin or signout, the issuedb CLI shall complete the command without opening or creating an issue database.
- When a credential file is written, the issuedb CLI shall create it with mode 0600 and its directory with mode 0700.
- When the user runs signout, the issuedb CLI shall REMOVE the stored credential file rather than blanking or deactivating it.
- If the user runs signout when no credential is stored, then the issuedb CLI shall report that no credential was present and shall exit successfully.
- If a credential file exists with permissions more permissive than 0600, then the issuedb CLI shall tighten them when it next writes.
- The issuedb CLI shall key stored credentials by server URL so two servers do not overwrite one another.
- The issuedb CLI shall not print the secret portion of a credential in any output.
- The issuedb sync layer shall depend on the Python standard library only.

**Out of scope** (manager's call — add when a user asks): token refresh, device
flow, multi-account switching.

## Design decisions

**Not in the database.** `.issue.db` is committed to git in 22 of the 42 repos
in this estate. A credential stored there is pushed to a remote by the next
`git add -A`, and it is in history the moment it lands — no care at the call
site can undo it.

**Not in the working directory** either: a file written to `$PWD` appears
wherever the user happened to be standing, and one of those places is a repo.
Same defect as the stray `.issue.db`, wearing a token.

**Short-circuited before `CLI(args.db)`** in `issuedb/cli/_main.py`. That
constructor creates `.issue.db` in the current directory when absent — right
for `create`, wrong for `signin`. Signing in is a statement about a machine,
not about a project.

**Written via `mkstemp` + `os.replace`.** A plain `open(); write(); chmod()`
leaves a window in which the file exists, holds the secret, and is
world-readable.

**Signout removes the file.** Not blanking, not a flag. "Signed out" while the
token sits on disk readable is the shape of every logout bug.

**`forget()` returns whether it removed anything**, so a signout that removed
nothing can say so rather than reporting success for a token still on disk.

## Verification

Exercised through the real CLI from an empty directory, not just via unit
tests: `signin` stored the credential, **no `.issue.db` appeared in the cwd**,
`stat` reported 700 on the directory and 600 on the file, and the secret was
absent from all output.

For signout, the test greps the bytes — after first confirming the secret **was**
there. A check that has never produced a positive is not evidence of a negative.

### Mutations

| Mutation | Result |
|---|---|
| File mode 0644 | 4 failed |
| Directory mode 0755 | 2 failed |
| Signout blanks the entry, leaves the file | 2 failed |
| `forget()` reports True when nothing matched | 1 failed |
| Corrupt store silently returns empty | 1 failed |
| Post-rename `chmod` removed | **survived — the line was a no-op** |
| `os.fchmod` removed | **survived — `mkstemp` already creates 0600** |
| **`mkstemp` swapped for plain `open()`** | **4 failed** |

The last three together are the interesting result. Both explicit permission
calls are redundant: `tempfile.mkstemp` creates 0600 regardless of umask and
`os.replace` preserves the source mode. The redundant post-rename `chmod` was
removed — a line no test can observe is untested code, not defence in depth.

`fchmod` was kept as an explicit statement of intent, and the *property*
remains guarded: swapping `mkstemp` for the naive `open()` a future refactor
would reach for takes four tests red. The tests assert the outcome rather than
the mechanism, which is why they survive an implementation change while still
catching the regression.

Gates: 735 tests pass, mypy clean over 69 source files, ruff clean, stdlib only.

## Not yet done

No network call is made. `signin` stores a key; it does **not** verify the key
against Tracker, because `/v1/sync/handshake` is not implemented yet. A stored
credential therefore means "a well-formed key was saved", never "the key
works" — and nothing in the output claims otherwise.
