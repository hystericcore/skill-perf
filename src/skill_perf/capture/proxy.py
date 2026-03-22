"""Manage llm-interceptor (lli) proxy lifecycle."""

from __future__ import annotations

import os
import subprocess
import time


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
                stdin=subprocess.PIPE,
            )
            time.sleep(3)  # Wait for proxy readiness
            if self._process.poll() is not None:
                stderr = ""
                if self._process.stderr:
                    stderr = self._process.stderr.read().decode(errors="replace")
                raise RuntimeError(f"lli proxy failed to start: {stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                "lli not found. Install with: pip install llm-interceptor"
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
            subprocess.run(
                ["lli", "merge", "--input", raw_path, "--output", merged_path],
                capture_output=True,
            )

            # Split into individual request/response JSON files
            if os.path.exists(merged_path) and os.path.getsize(merged_path) > 0:
                subprocess.run(
                    [
                        "lli", "split",
                        "--input", merged_path,
                        "--output-dir", split_dir,
                    ],
                    capture_output=True,
                )

    def __enter__(self) -> ProxyManager:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
