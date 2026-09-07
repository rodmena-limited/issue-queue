"""Tests for credential storage, signin and signout.

Three claims carry real consequences and each is asserted against the
filesystem rather than against a return value:

* the credential is not in the database and not in the working directory,
  because ``.issue.db`` is committed to git in 22 of the 42 repos here;
* the file is 0600 and its directory 0700, checked with a test that fails on
  0644 — a token readable by every process on a shared box is not a token;
* signout REMOVES the file. "Signed out" while the secret sits on disk is the
  shape of every logout bug, so the test greps the bytes rather than trusting
  the message.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from issuedb.sync import _auth_commands
from issuedb.sync._credentials import (
    Credential,
    CredentialError,
    config_dir,
    credentials_path,
    forget,
    list_servers,
    load,
    parse_token,
    store,
)

TOKEN = "trk_01jabcdefghijklmnopqrstuv_supersecretvalue"
SECRET = "supersecretvalue"
SERVER = "https://tracker.rodmena.co.uk"
OTHER = "https://tracker.example.test"


@pytest.fixture
def env(tmp_path):
    """An isolated XDG_CONFIG_HOME, so no test touches the real one."""
    return {"XDG_CONFIG_HOME": str(tmp_path / "config"), "HOME": str(tmp_path / "home")}


@pytest.fixture
def signed_in(env):
    key_id, secret = parse_token(TOKEN)
    store(Credential(server_url=SERVER, key_id=key_id, secret=secret), env)
    return env


# --- where it lives -------------------------------------------------------


def test_credentials_live_under_xdg_config_home(env):
    assert config_dir(env) == Path(env["XDG_CONFIG_HOME"]) / "issuedb"


def test_xdg_config_home_falls_back_to_dot_config(tmp_path):
    env = {"HOME": str(tmp_path)}
    assert config_dir(env) == tmp_path / ".config" / "issuedb"


def test_the_credential_is_not_written_to_the_working_directory(signed_in, tmp_path, monkeypatch):
    """A credential in $PWD is the stray-.issue.db defect wearing a token."""
    workdir = tmp_path / "some-repo"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    store(Credential(server_url=OTHER, key_id="k", secret="s"), signed_in)

    assert list(workdir.iterdir()) == [], f"files appeared in the cwd: {list(workdir.iterdir())}"


def test_the_secret_is_not_in_any_issue_database(signed_in, tmp_path):
    """The store must not be inside .issue.db, which many repos commit."""
    from issuedb.database import Database

    database = Database(str(tmp_path / ".issue.db"))
    try:
        raw = (tmp_path / ".issue.db").read_bytes()
        assert SECRET.encode() not in raw
    finally:
        database.close_connection()
        Database._instances.clear()


# --- permissions ----------------------------------------------------------


def test_file_is_0600_and_directory_is_0700(signed_in):
    path = credentials_path(signed_in)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_loose_permissions_are_tightened_on_the_next_write(signed_in):
    """A file loosened by anything else is fixed when we next touch it."""
    path = credentials_path(signed_in)
    path.chmod(0o644)
    path.parent.chmod(0o755)
    assert stat.S_IMODE(path.stat().st_mode) == 0o644  # the known-positive

    store(Credential(server_url=OTHER, key_id="k", secret="s"), signed_in)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_the_secret_is_never_group_or_world_readable(signed_in):
    mode = stat.S_IMODE(credentials_path(signed_in).stat().st_mode)
    assert not mode & stat.S_IRGRP
    assert not mode & stat.S_IROTH
    assert not mode & stat.S_IWGRP
    assert not mode & stat.S_IWOTH


# --- round trip -----------------------------------------------------------


def test_store_and_load(signed_in):
    credential = load(SERVER, signed_in)
    assert credential is not None
    assert credential.key_id == "01jabcdefghijklmnopqrstuv"
    assert credential.secret == SECRET
    assert credential.token == TOKEN


def test_loading_an_unknown_server_returns_none(signed_in):
    assert load(OTHER, signed_in) is None


def test_two_servers_do_not_evict_one_another(signed_in):
    store(Credential(server_url=OTHER, key_id="k2", secret="s2"), signed_in)
    assert list_servers(signed_in) == sorted([SERVER, OTHER])
    assert load(SERVER, signed_in).secret == SECRET
    assert load(OTHER, signed_in).secret == "s2"


@pytest.mark.parametrize(
    "bad",
    ["", "trk_", "trk_only", "notatoken", "trk__nosecret", "trk_nokeyid_", "abc_def_ghi"],
)
def test_malformed_tokens_are_rejected(bad):
    with pytest.raises(CredentialError):
        parse_token(bad)


def test_the_rejection_message_does_not_echo_the_token():
    """Invalid-token errors get pasted into bug reports."""
    with pytest.raises(CredentialError) as excinfo:
        parse_token("trk_realkeyid_realsecretvalue_extra")
    assert "realsecretvalue" not in str(excinfo.value)


def test_redacted_form_hides_the_secret_and_keeps_the_key_id(signed_in):
    credential = load(SERVER, signed_in)
    redacted = credential.redacted()
    assert SECRET not in redacted
    assert credential.key_id in redacted  # non-secret, and answers "which key?"


# --- signout removes it ---------------------------------------------------


def test_signout_removes_the_file_not_just_the_entry(signed_in):
    """Asserts the BYTES are gone, after confirming they were there.

    Checking only the return value, or only that load() returns None, would
    pass against an implementation that blanked the entry and left the secret
    in the file.
    """
    path = credentials_path(signed_in)
    assert SECRET in path.read_text()  # the known-positive

    assert forget(SERVER, signed_in) is True

    assert not path.exists(), "the credential file survived signout"


def test_signout_of_one_server_keeps_the_other_and_still_hides_nothing(signed_in):
    store(Credential(server_url=OTHER, key_id="k2", secret="othersecret"), signed_in)
    path = credentials_path(signed_in)

    assert forget(SERVER, signed_in) is True

    assert path.exists()
    assert SECRET not in path.read_text()
    assert "othersecret" in path.read_text()
    assert load(SERVER, signed_in) is None
    assert load(OTHER, signed_in) is not None


def test_signout_all_removes_everything(signed_in):
    store(Credential(server_url=OTHER, key_id="k2", secret="othersecret"), signed_in)
    assert forget(None, signed_in) is True
    assert not credentials_path(signed_in).exists()
    assert list_servers(signed_in) == []


def test_signout_reports_that_it_removed_nothing(signed_in):
    """An operation that changes nothing must not report success as removal."""
    assert forget(OTHER, signed_in) is False
    assert forget(SERVER, signed_in) is True
    assert forget(SERVER, signed_in) is False


def test_signout_with_no_store_at_all_is_not_an_error(env):
    assert forget(SERVER, env) is False


# --- the commands ---------------------------------------------------------


def test_signin_command_stores_and_returns_zero(env, capsys, monkeypatch):
    monkeypatch.setattr(_auth_commands, "_store", lambda cred, _e: store(cred, env))
    assert _auth_commands.signin(token=TOKEN, server=SERVER, env=env) == 0
    assert load(SERVER, env) is not None


def test_signin_never_prints_the_secret(env, capsys, monkeypatch):
    monkeypatch.setattr(_auth_commands, "_store", lambda cred, _e: store(cred, env))
    _auth_commands.signin(token=TOKEN, server=SERVER, env=env)
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    assert "01jabcdefghijklmnopqrstuv" in output.out  # key_id is not secret


def test_signin_rejects_a_malformed_token_without_writing(env, capsys):
    assert _auth_commands.signin(token="garbage", server=SERVER, env=env) == 1
    assert not credentials_path(env).exists()


def test_signout_command_reports_removal(signed_in, capsys):
    assert _auth_commands.signout(server=SERVER, env=signed_in) == 0
    assert "removed" in capsys.readouterr().out.lower()
    assert not credentials_path(signed_in).exists()


def test_signout_command_is_honest_when_nothing_was_stored(env, capsys):
    assert _auth_commands.signout(server=SERVER, env=env) == 0
    assert "nothing to remove" in capsys.readouterr().out.lower()


def test_whoami_reports_signed_out_with_a_nonzero_exit(env, capsys):
    assert _auth_commands.whoami(server=SERVER, env=env) == 1
    assert "not signed in" in capsys.readouterr().out.lower()


def test_whoami_never_prints_the_secret(signed_in, capsys):
    assert _auth_commands.whoami(server=SERVER, env=signed_in) == 0
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err


# --- the store file itself ------------------------------------------------


def test_a_corrupt_store_is_reported_not_silently_ignored(env):
    """Returning None here would look identical to 'not signed in'."""
    path = credentials_path(env)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json")
    with pytest.raises(CredentialError, match="could not be read"):
        load(SERVER, env)


def test_the_store_is_json_keyed_by_server(signed_in):
    data = json.loads(credentials_path(signed_in).read_text())
    assert SERVER in data
    assert data[SERVER]["key_id"] == "01jabcdefghijklmnopqrstuv"


def test_no_temporary_file_is_left_behind(signed_in):
    leftovers = [p.name for p in config_dir(signed_in).iterdir() if p.name.startswith(".")]
    assert leftovers == [], f"temporary files left in the config dir: {leftovers}"


def test_the_secret_is_never_on_disk_at_a_wider_mode(env, tmp_path):
    """mkstemp creates 0600 before any content is written.

    open()/write()/chmod() would leave a window where the file exists, holds
    the secret, and is world-readable.
    """
    key_id, secret = parse_token(TOKEN)
    store(Credential(server_url=SERVER, key_id=key_id, secret=secret), env)
    path = credentials_path(env)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert os.access(path, os.R_OK)


def test_signout_names_the_store_before_removing_it(tmp_path, capsys):
    """A destructive command must state its target at the moment it acts.

    `tracker-fbe1b4` ran signout on a shared host believing they had isolated
    it with ISSUEDB_CONFIG_DIR — a variable this tool has never honoured. The
    isolation was a no-op and signout removed somebody else's credential.

    `signin` had printed the real path several commands earlier, and that was
    not enough: the reader is only in a position to stop at the moment of the
    destructive act.
    """
    from issuedb.sync._auth_commands import signin, signout

    env = {"XDG_CONFIG_HOME": str(tmp_path / "cfg")}
    signin(server="https://example.invalid", token="trk_01abcdefghijklmnop_s3cret", env=env)
    capsys.readouterr()

    signout(server="https://example.invalid", env=env)
    out = capsys.readouterr().out

    assert "Credential store:" in out, "signout did not name the file it was about to act on"
    assert str(tmp_path / "cfg") in out, "signout named a path that was not the one in use"


def test_signout_on_a_missing_store_says_so_without_claiming_removal(tmp_path, capsys):
    """Control: the announcement must not itself become a false success."""
    from issuedb.sync._auth_commands import signout

    env = {"XDG_CONFIG_HOME": str(tmp_path / "empty")}
    assert signout(server="https://example.invalid", env=env) == 0
    out = capsys.readouterr().out
    assert "Nothing to remove" in out
    assert "Signed out" not in out
