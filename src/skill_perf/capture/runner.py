"""Run editor CLIs (claude, aider, cursor) non-interactively."""


import os
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class RunResult:
    """Result of a single CLI run."""

    exit_code: int
    duration_ms: int
    stdout: str
    stderr: str


class CLIRunner:
    """Runs editor CLIs (claude, aider, cursor) non-interactively."""

    def __init__(self, proxy_port: int = 9090) -> None:
        self.proxy_port = proxy_port

    def _get_env(self) -> dict[str, str]:
        """Get environment with proxy settings."""
        env = os.environ.copy()
        env["HTTPS_PROXY"] = f"http://localhost:{self.proxy_port}"
        env["HTTP_PROXY"] = f"http://localhost:{self.proxy_port}"
        # Trust the proxy CA
        # lli uses mitmproxy under the hood
        ca_path = os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.pem")
        if os.path.exists(ca_path):
            env["NODE_EXTRA_CA_CERTS"] = ca_path
        return env

    def _check_proxy_ready(self) -> bool:
        """Check if the proxy port is reachable."""
        try:
            sock = socket.create_connection(
                ("localhost", self.proxy_port), timeout=2
            )
            sock.close()
            return True
        except OSError:
            return False

    def run(
        self,
        prompt: str,
        cli: str = "claude",
        max_turns: int = 3,
        timeout: int = 120,
        skill_dir: Optional[str] = None,
        allowed_tools: str = "*",
    ) -> RunResult:
        """Run CLI tool with given prompt."""
        if not self._check_proxy_ready():
            return RunResult(
                exit_code=-1,
                duration_ms=0,
                stdout="",
                stderr=f"Proxy not reachable on port {self.proxy_port}",
            )

        cmd = self._build_command(
            prompt, cli, max_turns, skill_dir, allowed_tools=allowed_tools
        )
        env = self._get_env()

        start = time.time()
        try:
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, timeout=timeout
            )
            duration_ms = int((time.time() - start) * 1000)
            return RunResult(
                exit_code=result.returncode,
                duration_ms=duration_ms,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start) * 1000)
            return RunResult(
                exit_code=-1,
                duration_ms=duration_ms,
                stdout="",
                stderr="Timeout",
            )
        except OSError as exc:
            duration_ms = int((time.time() - start) * 1000)
            return RunResult(
                exit_code=-1,
                duration_ms=duration_ms,
                stdout="",
                stderr=str(exc),
            )

    def _build_command(
        self,
        prompt: str,
        cli: str,
        max_turns: int,
        skill_dir: Optional[str],
        allowed_tools: str = "*",
    ) -> list[str]:
        """Build the CLI command for the specified tool."""
        if cli == "claude":
            cmd = [
                "claude",
                "-p",
                prompt,
                "--output-format",
                "json",
                "--max-turns",
                str(max_turns),
                "--allowedTools",
                allowed_tools,
            ]
            if skill_dir:
                cmd.extend(["--cwd", skill_dir])
            return cmd
        elif cli == "aider":
            return [
                "aider",
                "--message",
                prompt,
                "--yes-always",
                "--no-auto-commits",
            ]
        else:
            return [cli, prompt]
