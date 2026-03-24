"""Tests for the capture module and measure command."""


import json
import os
import tempfile

import pytest
from typer.testing import CliRunner

from skill_perf.capture.proxy import ProxyManager
from skill_perf.capture.runner import CLIRunner
from skill_perf.capture.suite import BenchCase, load_suite
from skill_perf.cli import app

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ── ProxyManager ──────────────────────────────────────────────


class TestProxyManager:
    def test_proxy_manager_init_defaults(self) -> None:
        pm = ProxyManager()
        assert pm.port == 9090
        assert pm.trace_dir == "./traces"
        assert pm._process is None

    def test_proxy_manager_init_custom(self) -> None:
        pm = ProxyManager(port=8080, trace_dir="/tmp/my-traces")
        assert pm.port == 8080
        assert pm.trace_dir == "/tmp/my-traces"


# ── CLIRunner ─────────────────────────────────────────────────


class TestCLIRunner:
    def test_build_command_claude(self) -> None:
        runner = CLIRunner(proxy_port=9090)
        cmd = runner._build_command("hello", cli="claude", max_turns=3, skill_dir=None)
        assert cmd == [
            "claude",
            "-p",
            "hello",
            "--output-format",
            "json",
            "--max-turns",
            "3",
            "--allowedTools",
            "*",
        ]

    def test_build_command_claude_with_skill(self) -> None:
        runner = CLIRunner()
        cmd = runner._build_command(
            "hello", cli="claude", max_turns=5, skill_dir="/tmp/skill"
        )
        assert "--cwd" in cmd
        assert "/tmp/skill" in cmd

    def test_build_command_aider(self) -> None:
        runner = CLIRunner()
        cmd = runner._build_command("fix bug", cli="aider", max_turns=3, skill_dir=None)
        assert cmd == [
            "aider",
            "--message",
            "fix bug",
            "--yes-always",
            "--no-auto-commits",
        ]

    def test_build_command_cursor(self) -> None:
        runner = CLIRunner()
        cmd = runner._build_command("do thing", cli="cursor", max_turns=3, skill_dir=None)
        assert cmd[0] == "agent"
        assert "-p" in cmd
        assert "--output-format" in cmd
        assert "--force" in cmd

    def test_build_command_cursor_with_model(self) -> None:
        runner = CLIRunner()
        cmd = runner._build_command(
            "do thing", cli="cursor", max_turns=3, skill_dir=None, model="sonnet-4"
        )
        assert "--model" in cmd
        assert "sonnet-4" in cmd

    def test_build_command_cursor_with_workspace(self) -> None:
        runner = CLIRunner()
        cmd = runner._build_command(
            "do thing", cli="cursor", max_turns=3, skill_dir="/tmp/my-skill"
        )
        assert "--workspace" in cmd
        assert "/tmp/my-skill" in cmd

    def test_build_command_gemini(self) -> None:
        runner = CLIRunner()
        cmd = runner._build_command("do thing", cli="gemini", max_turns=3, skill_dir=None)
        assert cmd[0] == "gemini"
        assert "-p" in cmd
        assert "--output-format" in cmd
        assert "--yolo" in cmd

    def test_build_command_gemini_with_model(self) -> None:
        runner = CLIRunner()
        cmd = runner._build_command(
            "do thing", cli="gemini", max_turns=3, skill_dir=None, model="gemini-2.5-flash"
        )
        assert "--model" in cmd
        assert "gemini-2.5-flash" in cmd

    def test_build_command_generic(self) -> None:
        runner = CLIRunner()
        cmd = runner._build_command("do thing", cli="my-tool", max_turns=3, skill_dir=None)
        assert cmd == ["my-tool", "do thing"]

    def test_get_env_sets_proxy(self) -> None:
        runner = CLIRunner(proxy_port=7777)
        env = runner._get_env()
        assert env["HTTP_PROXY"] == "http://localhost:7777"
        assert env["HTTPS_PROXY"] == "http://localhost:7777"


# ── Suite loader ──────────────────────────────────────────────


class TestLoadSuite:
    def test_load_suite_fixture(self) -> None:
        suite_path = os.path.join(FIXTURES_DIR, "test-suite.json")
        cases = load_suite(suite_path)
        assert len(cases) == 2
        assert isinstance(cases[0], BenchCase)
        assert cases[0].label == "csv-parser"
        assert "CSV" in cases[0].prompt
        assert cases[1].label == "rest-client"

    def test_load_suite_from_temp(self) -> None:
        data = [
            {"label": "alpha", "prompt": "Do alpha"},
            {"label": "beta", "prompt": "Do beta"},
            {"label": "gamma", "prompt": "Do gamma"},
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            tmp_path = f.name

        try:
            cases = load_suite(tmp_path)
            assert len(cases) == 3
            assert cases[2].label == "gamma"
        finally:
            os.unlink(tmp_path)

    def test_load_suite_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_suite("/nonexistent/path/suite.json")


# ── CLI integration ───────────────────────────────────────────


class TestMeasureCLI:
    runner = CliRunner()

    def test_measure_no_args_shows_error(self) -> None:
        result = self.runner.invoke(app, ["measure"])
        assert result.exit_code != 0
        assert "prompt" in result.output.lower() or "suite" in result.output.lower()
