"""Where Tracker credentials live, and why it is not in the database.

``.issue.db`` is committed to git in 22 of the 42 repos in this estate. A
credential stored there would be pushed to a remote by the next ``git add
-A``, and no amount of care at the call site can undo that — the token is in
history the moment it lands. So credentials live in
``$XDG_CONFIG_HOME/issuedb/`` (``~/.config/issuedb/`` by default), which is
per user, per machine, and outside every checkout.

The same reasoning rules out the working directory. A file written to ``$PWD``
is the same defect as the stray ``.issue.db`` that ``signin`` is careful not
to create: it appears wherever the user happened to be standing, and one of
those places is a repo.

Two properties are enforced rather than documented, because a credential file
that is merely *intended* to be private is a public file:

* mode 0600 on the file and 0700 on the directory, applied on every write —
  not just at creation, so a file that was somehow loosened is tightened the
  next time it is touched;
* ``forget()`` REMOVES the file. Not blanking it, not marking it inactive.
  "Signed out" while the token sits on disk readable is the shape of every
  logout bug there has ever been.

Credentials are keyed by server URL so that signing in to a second Tracker
does not silently evict the first.

Standard library only.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

CONFIG_DIR_MODE = 0o700
CREDENTIAL_FILE_MODE = 0o600
CREDENTIALS_FILENAME = "credentials.json"


class Credential(NamedTuple):
    """A stored Tracker API key, split into its public and secret halves.

    Tracker issues ``trk_<key_id>_<secret>``. ``key_id`` is a non-secret
    lowercase ULID and is safe to log — it is what makes "which key was that?"
    answerable afterwards. ``secret`` never appears in output.
    """

    server_url: str
    key_id: str
    secret: str

    @property
    def token(self) -> str:
        """The full bearer token, for the Authorization header only."""
        return f"trk_{self.key_id}_{self.secret}"

    def redacted(self) -> str:
        """A form safe to print, log, or put in an error message."""
        return f"trk_{self.key_id}_<secret>"


class CredentialError(Exception):
    """A credential could not be parsed or stored."""


def parse_token(token: str) -> tuple[str, str]:
    """Split ``trk_<key_id>_<secret>`` into its two halves.

    Raises CredentialError with a message that does NOT echo the token: an
    invalid-token error is a thing users paste into bug reports.
    """
    parts = token.strip().split("_")
    if len(parts) != 3 or parts[0] != "trk" or not parts[1] or not parts[2]:
        raise CredentialError(
            "not a Tracker API key: expected the form trk_<key_id>_<secret>. "
            "Create one in Tracker under API keys."
        )
    return parts[1], parts[2]


def config_dir(env: dict[str, str] | None = None) -> Path:
    """The directory credentials live in, honouring XDG_CONFIG_HOME.

    ``env`` is injectable so tests exercise the real resolution logic instead
    of a parallel implementation of it.
    """
    environ = os.environ if env is None else env
    xdg = environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path(environ.get("HOME", "~")).expanduser() / ".config"
    return base / "issuedb"


def credentials_path(env: dict[str, str] | None = None) -> Path:
    return config_dir(env) / CREDENTIALS_FILENAME


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    # Applied every time, not only at creation: a directory that was created
    # loosely, or loosened later, is tightened whenever we touch it.
    path.chmod(CONFIG_DIR_MODE)


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write the store with the private mode applied BEFORE any content.

    A plain ``open(); write(); chmod()`` leaves a window in which the file
    exists, holds the secret, and is world-readable. The temporary file is
    created 0600 by mkstemp, filled, then renamed over the target — so the
    secret is never on disk at a wider mode, even briefly.
    """
    _ensure_dir(path.parent)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".credentials-")
    try:
        os.fchmod(handle, CREDENTIAL_FILE_MODE)
        with os.fdopen(handle, "w") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        # No chmod after the rename: mkstemp creates 0600 and os.replace
        # preserves the source's mode, so the file is already private and a
        # further chmod is a no-op. Verified by mutation — deleting a chmod
        # here changed no test, which is the signature of a line that does
        # nothing rather than a gap in coverage.
        os.replace(temporary, path)
    except BaseException:
        # The temporary file may hold the secret; remove it rather than
        # leaving it behind under a dot-prefixed name nobody will notice.
        Path(temporary).unlink(missing_ok=True)
        raise


def _load_store(env: dict[str, str] | None = None) -> dict[str, Any]:
    path = credentials_path(env)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CredentialError(
            f"the credential store at {path} could not be read: {exc}. "
            f"Delete it and sign in again."
        ) from exc
    if not isinstance(data, dict):
        raise CredentialError(f"the credential store at {path} is not a JSON object")
    return data


def store(credential: Credential, env: dict[str, str] | None = None) -> Path:
    """Persist a credential, keyed by server URL. Returns the file written."""
    path = credentials_path(env)
    data = _load_store(env)
    data[credential.server_url] = {
        "key_id": credential.key_id,
        "secret": credential.secret,
    }
    _write_atomic(path, data)
    return path


def load(server_url: str, env: dict[str, str] | None = None) -> Credential | None:
    """The credential for a server, or None if not signed in."""
    entry = _load_store(env).get(server_url)
    if not isinstance(entry, dict) or "key_id" not in entry or "secret" not in entry:
        return None
    return Credential(
        server_url=server_url, key_id=str(entry["key_id"]), secret=str(entry["secret"])
    )


def list_servers(env: dict[str, str] | None = None) -> list[str]:
    """Servers with a stored credential. Secrets are never returned."""
    return sorted(_load_store(env))


def forget(server_url: str | None = None, env: dict[str, str] | None = None) -> bool:
    """Remove a stored credential, or all of them when server_url is None.

    The file is DELETED when nothing is left, rather than being left as an
    empty object. Returns True if something was actually removed — a signout
    that removed nothing must be able to say so, rather than reporting success
    for a token still sitting on disk.
    """
    path = credentials_path(env)
    if not path.exists():
        return False

    if server_url is None:
        path.unlink()
        return True

    data = _load_store(env)
    if server_url not in data:
        return False
    del data[server_url]

    if data:
        _write_atomic(path, data)
    else:
        path.unlink()
    return True


def permissions(path: Path) -> tuple[int, int]:
    """(file mode, directory mode) as octal permission bits, for assertions."""
    return (
        stat.S_IMODE(path.stat().st_mode),
        stat.S_IMODE(path.parent.stat().st_mode),
    )
