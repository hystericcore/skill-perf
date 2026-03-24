"""Tests for snapshot and diff commands."""

import os
import tempfile
import time

import pytest
from typer.testing import CliRunner

from skill_perf.cli import app
from skill_perf.commands.snapshot import run_diff, run_list_snapshots, run_snapshot


SAMPLE_SKILL = """\
---
name: test-skill
description: A test skill for unit tests.
---

## Instructions

Do the thing.
"""

UPDATED_SKILL = """\
---
name: test-skill
description: A test skill for unit tests.
---

## Instructions

Do the thing.
ALWAYS check output before finishing.
"""


def _make_skill_dir(content: str = SAMPLE_SKILL) -> str:
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, "SKILL.md"), "w") as f:
        f.write(content)
    return tmpdir


class TestRunSnapshot:
    def test_creates_snapshot_file(self) -> None:
        skill_dir = _make_skill_dir()
        path = run_snapshot(skill_dir)
        assert os.path.exists(path)
        assert path.endswith(".md")

    def test_snapshot_content_matches(self) -> None:
        skill_dir = _make_skill_dir()
        path = run_snapshot(skill_dir)
        with open(path) as f:
            content = f.read()
        assert content == SAMPLE_SKILL

    def test_snapshot_saved_in_snapshots_dir(self) -> None:
        skill_dir = _make_skill_dir()
        path = run_snapshot(skill_dir)
        assert os.path.join(skill_dir, ".snapshots") in path

    def test_multiple_snapshots_accumulate(self) -> None:
        skill_dir = _make_skill_dir()
        run_snapshot(skill_dir)
        time.sleep(1)  # ensure different timestamps
        run_snapshot(skill_dir)
        snaps = os.listdir(os.path.join(skill_dir, ".snapshots"))
        assert len(snaps) == 2

    def test_missing_skill_md_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(SystemExit):
                run_snapshot(tmpdir)


class TestRunDiff:
    def test_no_diff_when_unchanged(self, capsys) -> None:
        skill_dir = _make_skill_dir()
        run_snapshot(skill_dir)
        # no changes — diff should report nothing
        run_diff(skill_dir)  # should not raise

    def test_diff_shows_added_lines(self, capsys) -> None:
        skill_dir = _make_skill_dir(SAMPLE_SKILL)
        run_snapshot(skill_dir)
        # update the working copy
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write(UPDATED_SKILL)
        run_diff(skill_dir)  # should not raise

    def test_no_snapshots_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "SKILL.md"), "w") as f:
                f.write(SAMPLE_SKILL)
            with pytest.raises(SystemExit):
                run_diff(tmpdir)

    def test_explicit_from_snapshot(self) -> None:
        skill_dir = _make_skill_dir(SAMPLE_SKILL)
        snap = run_snapshot(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write(UPDATED_SKILL)
        run_diff(skill_dir, from_snapshot=snap)  # should not raise


class TestRunListSnapshots:
    def test_empty_when_no_snapshots(self, capsys) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_list_snapshots(tmpdir)  # should not raise

    def test_lists_existing_snapshots(self, capsys) -> None:
        skill_dir = _make_skill_dir()
        run_snapshot(skill_dir)
        run_list_snapshots(skill_dir)  # should not raise


class TestGlobalSnapshotDir:
    def test_env_var_redirects_snapshot(self, tmp_path, monkeypatch) -> None:
        skill_dir = _make_skill_dir()
        global_dir = str(tmp_path / "global-snaps")
        monkeypatch.setenv("SKILL_PERF_SNAPSHOT_DIR", global_dir)
        path = run_snapshot(skill_dir)
        assert global_dir in path
        assert ".snapshots" not in path

    def test_env_var_not_set_uses_local(self, monkeypatch) -> None:
        monkeypatch.delenv("SKILL_PERF_SNAPSHOT_DIR", raising=False)
        skill_dir = _make_skill_dir()
        path = run_snapshot(skill_dir)
        assert ".snapshots" in path

    def test_slug_derived_from_skill_path(self, tmp_path, monkeypatch) -> None:
        skill_dir = _make_skill_dir()
        global_dir = str(tmp_path / "snaps")
        monkeypatch.setenv("SKILL_PERF_SNAPSHOT_DIR", global_dir)
        path = run_snapshot(skill_dir)
        # slug should contain parts of the resolved path
        from pathlib import Path
        slug = Path(skill_dir).resolve().as_posix().lstrip("/").replace("/", "-")
        assert slug in path


class TestSnapshotCLI:
    runner = CliRunner()

    def test_snapshot_command(self) -> None:
        skill_dir = _make_skill_dir()
        result = self.runner.invoke(app, ["snapshot", skill_dir])
        assert result.exit_code == 0
        assert "Snapshot saved" in result.output

    def test_diff_command_no_change(self) -> None:
        skill_dir = _make_skill_dir()
        self.runner.invoke(app, ["snapshot", skill_dir])
        result = self.runner.invoke(app, ["diff", skill_dir])
        assert result.exit_code == 0

    def test_diff_list_flag(self) -> None:
        skill_dir = _make_skill_dir()
        self.runner.invoke(app, ["snapshot", skill_dir])
        result = self.runner.invoke(app, ["diff", skill_dir, "--list"])
        assert result.exit_code == 0
        assert "SKILL_" in result.output
