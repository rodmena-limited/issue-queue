"""Tests for Ollama client."""

import argparse
import json
import urllib.error

from issuedb import ollama_client
from issuedb.ollama_client import (
    MAX_REQUEST_CHARS,
    TRUNCATION_MARKER,
    OllamaClient,
)


class TestOllamaClient:
    """Test OllamaClient class."""

    def test_init_with_defaults(self):
        """Test client initialization with default values."""
        client = OllamaClient()
        assert client.host == "localhost"
        assert client.port == 11434
        assert client.model == "llama3"
        assert client.base_url == "http://localhost:11434"

    def test_init_with_custom_values(self):
        """Test client initialization with custom values."""
        client = OllamaClient(host="192.168.1.1", port=8080, model="mistral")
        assert client.host == "192.168.1.1"
        assert client.port == 8080
        assert client.model == "mistral"
        assert client.base_url == "http://192.168.1.1:8080"

    def test_extract_command_simple(self):
        """Test extracting simple command."""
        client = OllamaClient()

        # Test simple command
        text = "issuedb-cli create -t 'Test' -p MyProject"
        result = client._extract_command(text)
        assert result == "issuedb-cli create -t 'Test' -p MyProject"

    def test_extract_command_with_markdown(self):
        """Test extracting command from markdown code block."""
        client = OllamaClient()

        text = """Here's the command:
```bash
issuedb-cli list --project WebApp --status open
```
"""
        result = client._extract_command(text)
        assert result == "issuedb-cli list --project WebApp --status open"

    def test_extract_command_with_shell_prefix(self):
        """Test extracting command with shell prefix."""
        client = OllamaClient()

        # Test with $ prefix
        text = "$ issuedb-cli get-next --project MyApp"
        result = client._extract_command(text)
        assert result == "issuedb-cli get-next --project MyApp"

        # Test with # prefix
        text = "# issuedb-cli delete 42"
        result = client._extract_command(text)
        assert result == "issuedb-cli delete 42"

    def test_extract_command_multiline(self):
        """Test extracting command from multiline text."""
        client = OllamaClient()

        text = """The command you need is:

issuedb-cli create -t "Fix bug" -p Backend --priority high

This will create a new issue."""
        result = client._extract_command(text)
        assert result == 'issuedb-cli create -t "Fix bug" -p Backend --priority high'

    def test_extract_command_none(self):
        """Test extracting command when none is present."""
        client = OllamaClient()

        text = "There is no valid command here"
        result = client._extract_command(text)
        assert result is None

    def test_extract_command_invalid(self):
        """Test extracting invalid issuedb-cli command."""
        client = OllamaClient()

        # Just "issuedb-cli" without arguments
        text = "issuedb-cli"
        result = client._extract_command(text)
        assert result is None

    def test_extract_command_with_quotes(self):
        """Test extracting command with quoted strings."""
        client = OllamaClient()

        text = 'issuedb-cli create -t "Fix login bug" -p "Auth Service" --priority critical'
        result = client._extract_command(text)
        assert (
            result == 'issuedb-cli create -t "Fix login bug" -p "Auth Service" --priority critical'
        )

    def test_extract_command_with_explanation(self):
        """Test extracting command when LLM adds explanation."""
        client = OllamaClient()

        text = """Based on your request, here is the command:

```
issuedb-cli search -k "database" --project Backend
```

This will search for issues containing "database" in the Backend project."""

        result = client._extract_command(text)
        assert result == 'issuedb-cli search -k "database" --project Backend'

    def test_execute_command_dry_run(self):
        """Test command execution in dry run mode."""
        client = OllamaClient()

        command = "issuedb-cli list"
        success, stdout, stderr = client.execute_command(command, dry_run=True)

        assert success is True
        assert "Would execute:" in stdout
        assert stderr is None


class TestExecuteCommandSecurity:
    """Regression tests for command-injection hardening in execute_command."""

    def _capture_run(self, monkeypatch):
        """Monkeypatch subprocess.run to capture how it is invoked.

        Returns a dict that will hold the captured args/kwargs if run is
        ever called.
        """
        captured: dict = {}

        class _FakeResult:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def fake_run(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return _FakeResult()

        monkeypatch.setattr(ollama_client.subprocess, "run", fake_run)
        return captured

    def test_injection_not_run_through_shell(self, monkeypatch):
        """A `;`-injected payload must not be executed via a shell."""
        captured = self._capture_run(monkeypatch)
        client = OllamaClient()

        success, _stdout, _stderr = client.execute_command(
            "issuedb-cli list; rm -rf /tmp/should_not_exist"
        )

        # subprocess.run was called with an argv list, not a shell string.
        assert "args" in captured, "subprocess.run should have been called"
        argv = captured["args"][0]
        assert isinstance(argv, list)
        # shell must never be True.
        assert captured["kwargs"].get("shell") is not True
        # The command runs this installation's CLI module (not whatever
        # issuedb-cli is on PATH); the injected payload is just an argument,
        # never interpreted by a shell.
        import sys as _sys

        assert argv[:3] == [_sys.executable, "-m", "issuedb.cli"]
        assert "rm" in argv  # passed as a literal arg, not a separate command
        assert success is True

    def test_command_not_starting_with_cli_is_rejected(self, monkeypatch):
        """A command whose argv[0] != 'issuedb-cli' is rejected, run not called."""
        captured = self._capture_run(monkeypatch)
        client = OllamaClient()

        success, stdout, stderr = client.execute_command("rm -rf /tmp/should_not_exist")

        assert success is False
        assert stdout == ""
        assert stderr is not None and "issuedb-cli" in stderr
        # subprocess.run must never have been invoked.
        assert "args" not in captured

    def test_empty_command_is_rejected(self, monkeypatch):
        """An empty command is rejected without invoking subprocess.run."""
        captured = self._capture_run(monkeypatch)
        client = OllamaClient()

        success, stdout, stderr = client.execute_command("   ")

        assert success is False
        assert stderr is not None
        assert "args" not in captured

    def test_unbalanced_quotes_is_handled(self, monkeypatch):
        """Unbalanced quotes are handled as a failed command, not a crash."""
        captured = self._capture_run(monkeypatch)
        client = OllamaClient()

        success, stdout, stderr = client.execute_command('issuedb-cli list "unterminated')

        assert success is False
        assert stderr is not None and "parse" in stderr.lower()
        assert "args" not in captured

    def test_valid_command_still_runs(self, monkeypatch):
        """A valid issuedb-cli command is still executed (happy path)."""
        captured = self._capture_run(monkeypatch)
        client = OllamaClient()

        success, stdout, _stderr = client.execute_command(
            'issuedb-cli create -t "Fix bug" -p Backend'
        )

        assert success is True
        assert stdout == "ok"
        argv = captured["args"][0]
        import sys as _sys

        assert argv == [
            _sys.executable,
            "-m",
            "issuedb.cli",
            "create",
            "-t",
            "Fix bug",
            "-p",
            "Backend",
        ]
        assert captured["kwargs"].get("shell") is not True


class TestCheckServerHttpError:
    """Regression tests for check_server HTTPError reporting."""

    def test_http_error_reports_status_code(self, monkeypatch):
        """A non-2xx HTTPError surfaces the real status code, not a generic error."""

        def fake_urlopen(*_args, **_kwargs):
            raise urllib.error.HTTPError(
                url="http://localhost:11434/api/tags",
                code=503,
                msg="Service Unavailable",
                hdrs=None,  # type: ignore[arg-type]
                fp=None,
            )

        monkeypatch.setattr(ollama_client.request, "urlopen", fake_urlopen)
        client = OllamaClient()

        is_available, error_msg = client.check_server()

        assert is_available is False
        assert error_msg is not None
        assert "503" in error_msg


class TestGenerateCommandLimits:
    """Regression tests for prompt/response size limits in generate_command."""

    def _patch_urlopen(self, monkeypatch, response_text="issuedb-cli list"):
        """Monkeypatch request.urlopen to capture the POSTed body.

        Returns a dict that records the JSON payload sent to Ollama. The fake
        response mimics the bits generate_command uses: a context manager with
        a `status` and a `read(n)` method.
        """
        captured: dict = {}

        class _FakeResponse:
            status = 200

            def __init__(self, body: bytes) -> None:
                self._body = body

            def __enter__(self) -> "_FakeResponse":
                return self

            def __exit__(self, *_exc: object) -> bool:
                return False

            def read(self, amt: int = -1) -> bytes:
                # Honour the byte cap the client passes, like a real response.
                if amt is None or amt < 0:
                    return self._body
                return self._body[:amt]

        body = json.dumps({"response": response_text}).encode("utf-8")

        def fake_urlopen(req, *_args, **_kwargs):
            captured["data"] = req.data
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(body)

        monkeypatch.setattr(ollama_client.request, "urlopen", fake_urlopen)
        return captured

    def test_long_request_is_truncated_in_payload(self, monkeypatch):
        """A very long user_request is truncated before being POSTed."""
        captured = self._patch_urlopen(monkeypatch)
        client = OllamaClient()

        long_request = "A" * 50_000
        command, error = client.generate_command(long_request, "SYSTEM PROMPT")

        assert error is None
        assert command == "issuedb-cli list"

        # The full 50k-char request must not appear in the POSTed prompt.
        prompt = captured["payload"]["prompt"]
        assert long_request not in prompt
        # The embedded request is capped at MAX_REQUEST_CHARS (+ short marker).
        assert prompt.count("A") <= MAX_REQUEST_CHARS
        assert TRUNCATION_MARKER in prompt
        # The serialized body stays bounded (head + marker + framing).
        assert len(captured["data"]) < MAX_REQUEST_CHARS + len("SYSTEM PROMPT") + 200

    def test_short_request_unchanged(self, monkeypatch):
        """A normal short request produces the expected command, untruncated."""
        captured = self._patch_urlopen(monkeypatch)
        client = OllamaClient()

        command, error = client.generate_command(
            "list all open issues", "SYSTEM PROMPT"
        )

        assert error is None
        assert command == "issuedb-cli list"
        prompt = captured["payload"]["prompt"]
        assert "list all open issues" in prompt
        assert TRUNCATION_MARKER not in prompt


class TestOllamaArgParsing:
    """Test --ollama argument parsing behavior."""

    def test_ollama_remainder_parsing(self):
        """Test that --ollama captures all remaining words without quotes."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--ollama-model", type=str, default=None)
        parser.add_argument("--ollama", nargs=argparse.REMAINDER)

        # Simulate: issuedb-cli --ollama-model llama3 --ollama create a high priority bug
        args = parser.parse_args(
            ["--ollama-model", "llama3", "--ollama", "create", "a", "high", "priority", "bug"]
        )

        assert args.ollama_model == "llama3"
        assert args.ollama == ["create", "a", "high", "priority", "bug"]
        assert " ".join(args.ollama) == "create a high priority bug"

    def test_ollama_empty_request(self):
        """Test that empty --ollama request is handled."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--ollama", nargs=argparse.REMAINDER)

        args = parser.parse_args(["--ollama"])
        assert args.ollama == []
        assert " ".join(args.ollama) == ""

    def test_ollama_with_quoted_request(self):
        """Test that quoted request still works."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--ollama", nargs=argparse.REMAINDER)

        # Quoted request will be a single element
        args = parser.parse_args(["--ollama", "create a high priority bug"])
        assert args.ollama == ["create a high priority bug"]
        assert " ".join(args.ollama) == "create a high priority bug"

    def test_ollama_flags_before_request(self):
        """Test that ollama flags must come before --ollama."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--ollama-model", type=str, default=None)
        parser.add_argument("--ollama-host", type=str, default=None)
        parser.add_argument("--ollama-port", type=int, default=None)
        parser.add_argument("--ollama", nargs=argparse.REMAINDER)

        args = parser.parse_args(
            [
                "--ollama-model",
                "mistral",
                "--ollama-host",
                "192.168.1.1",
                "--ollama-port",
                "8080",
                "--ollama",
                "list",
                "all",
                "open",
                "issues",
            ]
        )

        assert args.ollama_model == "mistral"
        assert args.ollama_host == "192.168.1.1"
        assert args.ollama_port == 8080
        assert " ".join(args.ollama) == "list all open issues"
