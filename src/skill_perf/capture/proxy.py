"""Manage llm-interceptor (lli) proxy lifecycle."""

from __future__ import annotations

import os
import subprocess
import time


class ProxyManager:
    """Manages llm-interceptor (lli) proxy lifecycle."""

    def __init__(self, port: int = 9090, trace_dir: str = "./traces") -> None:
        self.port = port
        self.trace_dir = trace_dir
        self._process: subprocess.Popen | None = None  # type: ignore[type-arg]

    def start(self) -> None:
        """Start the lli proxy. Raises RuntimeError if lli not found or fails to start."""
        os.makedirs(self.trace_dir, exist_ok=True)
        try:
            self._process = subprocess.Popen(
                [
                    "lli",
                    "watch",
                    "--port",
                    str(self.port),
                    "--output-dir",
                    self.trace_dir,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(2)  # Wait for proxy readiness
            if self._process.poll() is not None:
                raise RuntimeError("lli proxy failed to start")
        except FileNotFoundError:
            raise RuntimeError(
                "lli not found. Install with: pip install llm-interceptor"
            )

    def stop(self) -> None:
        """Stop the proxy gracefully."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    def __enter__(self) -> ProxyManager:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
