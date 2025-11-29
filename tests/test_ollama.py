"""Tests for Ollama client."""

import argparse

from issuedb.ollama_client import OllamaClient


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
