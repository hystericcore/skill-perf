"""Manage llm-interceptor (lli) proxy lifecycle."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time

from rich.console import Console

_console = Console()


class ProxyManager:
    """Manages llm-interceptor (lli) proxy lifecycle.

    lli watch captures all traffic to a raw JSONL file.
    After stopping, we run `lli merge` and `lli split` to produce
    structured session files our parser can read.
    """

    def __init__(self, port: int = 9090, trace_dir: str = "./traces") -> None:
        self.port = port
        self.trace_dir = trace_dir
        self._process: subprocess.Popen | None = None  # type: ignore[type-arg]

    def _wait_for_proxy(self, timeout: int = 10) -> bool:
        """Poll proxy port until it responds or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                sock = socket.create_connection(("localhost", self.port), timeout=1)
                sock.close()
                return True
            except OSError:
                time.sleep(0.3)
        return False

    @staticmethod
    def _find_lli() -> str:
        """Find the lli executable, checking the current Python env first."""
        # Check alongside the running Python (same venv/pipx env)
        bin_dir = os.path.dirname(sys.executable)
        local_lli = os.path.join(bin_dir, "lli")
        if os.path.isfile(local_lli):
            return local_lli
        # Fall back to PATH
        found = shutil.which("lli")
        if found:
            return found
        raise FileNotFoundError("lli command not found. Reinstall skill-perf.")

    def start(self) -> None:
        """Start the lli proxy. Raises RuntimeError if lli not found or fails to start."""
        os.makedirs(self.trace_dir, exist_ok=True)
        lli_cmd = self._find_lli()
        try:
            self._process = subprocess.Popen(
                [
                    lli_cmd,
                    "watch",
                    "--port",
                    str(self.port),
                    "--output-dir",
                    self.trace_dir,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
            )
            if self._process.poll() is not None:
                stderr = ""
                if self._process.stderr:
                    stderr = self._process.stderr.read().decode(errors="replace")
                raise RuntimeError(f"lli proxy failed to start: {stderr}")
            if not self._wait_for_proxy():
                raise RuntimeError(
                    f"lli proxy not reachable on port {self.port} after 10s"
                )
        except FileNotFoundError:
            raise RuntimeError(
                "lli command not found. Reinstall skill-perf."
            )

    def stop(self) -> None:
        """Stop the proxy gracefully, then merge and split the raw trace."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

        # Post-process: find the raw JSONL and run merge + split
        self._post_process()

    def _post_process(self) -> None:
        """Run lli merge + split on captured JSONL to produce structured output."""
        try:
            lli_cmd = self._find_lli()
        except FileNotFoundError:
            return

        # Find the raw JSONL file (lli names it all_captured_*.jsonl)
        raw_files = [
            f for f in os.listdir(self.trace_dir)
            if f.endswith(".jsonl") and os.path.getsize(
                os.path.join(self.trace_dir, f)
            ) > 0
        ]
        if not raw_files:
            return

        for raw_file in raw_files:
            raw_path = os.path.join(self.trace_dir, raw_file)
            merged_path = os.path.join(self.trace_dir, "merged.jsonl")
            split_dir = os.path.join(self.trace_dir, "split_output")

            # Merge streaming chunks into complete records
            merge_result = subprocess.run(
                [lli_cmd, "merge", "--input", raw_path, "--output", merged_path],
                capture_output=True,
            )
            if merge_result.returncode != 0:
                _console.print(
                    f"[yellow]Warning:[/yellow] lli merge failed "
                    f"(exit {merge_result.returncode}): "
                    f"{merge_result.stderr.decode(errors='replace').strip()}"
                )

            # Split into individual request/response JSON files
            if os.path.exists(merged_path) and os.path.getsize(merged_path) > 0:
                split_result = subprocess.run(
                    [
                        lli_cmd, "split",
                        "--input", merged_path,
                        "--output-dir", split_dir,
                    ],
                    capture_output=True,
                )
                if split_result.returncode != 0:
                    _console.print(
                        f"[yellow]Warning:[/yellow] lli split failed "
                        f"(exit {split_result.returncode}): "
                        f"{split_result.stderr.decode(errors='replace').strip()}"
                    )

    def __enter__(self) -> ProxyManager:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
