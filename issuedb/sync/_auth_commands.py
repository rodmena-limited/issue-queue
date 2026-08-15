"""``issuedb-cli signin`` and ``issuedb-cli signout``.

These run BEFORE any database is opened. Every other command constructs
``CLI(args.db)``, which creates ``.issue.db`` in the current directory if it
is absent — correct for ``create`` and ``list``, wrong here. Signing in is not
a statement about a project, and a user who signs in from their home directory
should not find a mystery issue database there afterwards.

The functions return an exit code and print to stdout/stderr rather than
raising, because they are invoked directly from the argument dispatcher.
"""

from __future__ import annotations

import sys
from typing import Any

from issuedb.sync._credentials import (
    Credential,
    CredentialError,
    credentials_path,
    forget,
    list_servers,
    load,
    parse_token,
    permissions,
)

DEFAULT_SERVER = "https://tracker.rodmena.co.uk"


def _read_token(supplied: str | None, stdin: Any = None) -> str:
    """Take the token from the flag, or from stdin when it is piped.

    A token on the command line lands in the shell history file, so a pipe is
    offered and preferred. getpass is deliberately NOT used when stdin is not
    a terminal, or piping would hang waiting for a tty that is not there.
    """
    if supplied:
        return supplied

    stream = sys.stdin if stdin is None else stdin
    if not stream.isatty():
        return stream.read().strip()

    import getpass

    return getpass.getpass("Tracker API key (trk_...): ")


def signin(
    token: str | None = None,
    server: str = DEFAULT_SERVER,
    env: dict[str, str] | None = None,
    stdin: Any = None,
) -> int:
    """Store a Tracker API key. No database is opened."""
    try:
        raw = _read_token(token, stdin)
    except (EOFError, KeyboardInterrupt):
        print("Aborted.", file=sys.stderr)
        return 1

    if not raw:
        print("Error: no API key provided.", file=sys.stderr)
        return 1

    try:
        key_id, secret = parse_token(raw)
    except CredentialError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    credential = Credential(server_url=server, key_id=key_id, secret=secret)
    try:
        path = credential_path = _store(credential, env)
    except OSError as exc:
        print(f"Error: could not write the credential store: {exc}", file=sys.stderr)
        return 1

    file_mode, dir_mode = permissions(credential_path)
    # The secret is never printed; the key_id is not secret and is what makes
    # "which key was that?" answerable later.
    print(f"Signed in to {server} as {credential.redacted()}")
    print(f"Credential stored at {path} (mode {file_mode:04o}, directory {dir_mode:04o})")
    return 0


def _store(credential: Credential, env: dict[str, str] | None) -> Any:
    from issuedb.sync._credentials import store

    return store(credential, env)


def signout(
    server: str | None = DEFAULT_SERVER,
    all_servers: bool = False,
    env: dict[str, str] | None = None,
) -> int:
    """Remove a stored credential. No database is opened.

    Removal is real: the entry goes, and the file itself is deleted when
    nothing is left. A signout that leaves the token on disk while reporting
    success is the shape of every logout bug.
    """
    target = None if all_servers else server
    try:
        removed = forget(target, env)
    except OSError as exc:
        print(f"Error: could not update the credential store: {exc}", file=sys.stderr)
        return 1

    if not removed:
        # Reporting honestly that nothing was there beats a bare "signed out",
        # which is indistinguishable from a removal that silently failed.
        where = "any server" if all_servers else server
        print(f"No stored credential for {where}; nothing to remove.")
        return 0

    if all_servers:
        print("Signed out of all servers. Credential store removed.")
    else:
        print(f"Signed out of {server}. Credential removed.")
        remaining = list_servers(env)
        if remaining:
            print(f"Still signed in to: {', '.join(remaining)}")
    return 0


def whoami(server: str = DEFAULT_SERVER, env: dict[str, str] | None = None) -> int:
    """Report whether a credential is stored, without revealing the secret."""
    credential = load(server, env)
    if credential is None:
        print(f"Not signed in to {server}.")
        print(f"Run: issuedb-cli signin --server {server}")
        return 1

    file_mode, dir_mode = permissions(credentials_path(env))
    print(f"Signed in to {server} as {credential.redacted()}")
    print(f"Credential at {credentials_path(env)} (mode {file_mode:04o}, directory {dir_mode:04o})")
    return 0
