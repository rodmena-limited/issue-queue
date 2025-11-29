"""Ollama client for natural language command generation."""

import json
import os
import re
import subprocess
import sys
from typing import Optional, Tuple
from urllib import request
from urllib.error import HTTPError, URLError


class OllamaClient:
    """Client for interacting with Ollama API."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        model: Optional[str] = None,
    ) -> None:
        """Initialize Ollama client.

        Args:
            host: Ollama server host (default: from OLLAMA_HOST env or 'localhost')
            port: Ollama server port (default: from OLLAMA_PORT env or 11434)
            model: Model to use (default: from OLLAMA_MODEL env or 'llama3')
        """
        self.host = host or os.getenv("OLLAMA_HOST", "localhost")
        self.port = port or int(os.getenv("OLLAMA_PORT", "11434"))
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3")
        self.base_url = f"http://{self.host}:{self.port}"

    def check_server(self) -> Tuple[bool, Optional[str]]:
        """Check if Ollama server is available.

        Returns:
            Tuple of (is_available, error_message)
        """
        try:
            # Try to connect to the /api/tags endpoint to list models
            url = f"{self.base_url}/api/tags"
            req = request.Request(url, method="GET")
            req.add_header("Content-Type", "application/json")

            with request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    return True, None
                return False, f"Server returned status {response.status}"
        except URLError as e:
            return False, f"Cannot connect to Ollama server at {self.base_url}: {e.reason}"
        except Exception as e:
            return False, f"Error connecting to Ollama: {str(e)}"

    def generate_command(
        self, user_request: str, system_prompt: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Generate issuedb-cli command from natural language request.

        Args:
            user_request: User's natural language request
            system_prompt: System prompt with command guidelines

        Returns:
            Tuple of (generated_command, error_message)
        """
        try:
            # Construct the full prompt
            full_prompt = f"""{system_prompt}

User request: {user_request}

Generate the issuedb-cli command:"""

            # Prepare request body
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent output
                    "top_p": 0.9,
                },
            }

            # Make API request
            url = f"{self.base_url}/api/generate"
            data = json.dumps(payload).encode("utf-8")

            req = request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")

            with request.urlopen(req, timeout=60) as response:
                if response.status != 200:
                    return None, f"Ollama API returned status {response.status}"

                response_data = json.loads(response.read().decode("utf-8"))
                generated_text = response_data.get("response", "").strip()

                if not generated_text:
                    return None, "Ollama returned empty response"

                # Extract command from response
                command = self._extract_command(generated_text)

                if not command:
                    return (
                        None,
                        f"Could not extract valid command from response: {generated_text[:100]}",
                    )

                return command, None

        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return None, f"HTTP Error {e.code}: {error_body[:200]}"
        except URLError as e:
            return None, f"Connection error: {e.reason}"
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON response from Ollama: {str(e)}"
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"

    def _extract_command(self, text: str) -> Optional[str]:
        """Extract issuedb-cli command from generated text.

        Args:
            text: Generated text from Ollama

        Returns:
            Extracted command or None if not found
        """
        # Remove markdown code blocks if present
        text = re.sub(r"```(?:bash|shell|sh)?\n?", "", text)
        text = re.sub(r"```", "", text)

        # Split into lines and find lines containing issuedb-cli
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        for line in lines:
            # Look for lines starting with issuedb-cli (possibly with $ or #)
            line = re.sub(r"^[$#]\s*", "", line)

            if line.startswith("issuedb-cli"):
                # Clean up the command
                command = line.strip()

                # Validate basic structure
                if len(command) > 11 and " " in command:  # "issuedb-cli" + space + something
                    return command

        # If no valid command found in lines, try to find it anywhere in text
        match = re.search(r"issuedb-cli\s+\S+.*", text)
        if match:
            return match.group(0).strip()

        return None

    def execute_command(
        self, command: str, dry_run: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """Execute the generated issuedb-cli command.

        Args:
            command: Command to execute
            dry_run: If True, only show command without executing

        Returns:
            Tuple of (success, stdout, stderr)
        """
        if dry_run:
            return True, f"Would execute: {command}", None

        try:
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            success = result.returncode == 0
            return success, result.stdout, result.stderr if not success else None

        except subprocess.TimeoutExpired:
            return False, "", "Command execution timed out after 30 seconds"
        except Exception as e:
            return False, "", f"Error executing command: {str(e)}"


def handle_ollama_request(
    user_request: str,
    prompt_text: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    model: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """Handle Ollama-based command generation and execution.

    Args:
        user_request: User's natural language request
        prompt_text: System prompt content
        host: Ollama server host
        port: Ollama server port
        model: Ollama model to use
        dry_run: If True, show command without executing

    Returns:
        Exit code (0 for success, 1 for error)
    """
    client = OllamaClient(host=host, port=port, model=model)

    # Check server availability
    print(f"Connecting to Ollama at {client.base_url}...", file=sys.stderr)
    is_available, error_msg = client.check_server()

    if not is_available:
        print(f"Error: {error_msg}", file=sys.stderr)
        print("\nMake sure Ollama is running. Install and start it with:", file=sys.stderr)
        print("  curl https://ollama.ai/install.sh | sh", file=sys.stderr)
        print(f"  ollama serve  # or: ollama run {client.model}", file=sys.stderr)
        return 1

    print(f"Connected! Using model: {client.model}", file=sys.stderr)
    print(f'Generating command for: "{user_request}"', file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    # Generate command
    command, error_msg = client.generate_command(user_request, prompt_text)

    if error_msg:
        print(f"Error generating command: {error_msg}", file=sys.stderr)
        return 1

    if not command:
        print("Error: Could not generate valid command", file=sys.stderr)
        return 1

    print("\nGenerated command:", file=sys.stderr)
    print(f"  {command}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    if dry_run:
        print("\nDry run mode - command not executed", file=sys.stderr)
        return 0

    # Execute command
    print("\nExecuting command...", file=sys.stderr)
    success, stdout, stderr = client.execute_command(command)

    if stdout:
        print(stdout)

    if not success:
        print(f"\nCommand failed: {stderr}", file=sys.stderr)
        return 1

    return 0
