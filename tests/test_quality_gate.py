"""Tests for startup quality checks and entry scripts."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

import quality_gate
import run_app


class TestRunStartupQuality:
    def test_returns_ruff_check_failure(self):
        with patch("quality_gate.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert quality_gate.run_startup_quality() == 1

    def test_returns_ruff_format_failure(self):
        with patch("quality_gate.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),
                MagicMock(returncode=2),
            ]
            assert quality_gate.run_startup_quality() == 2

    def test_returns_pytest_exit_code(self):
        with (
            patch("quality_gate.subprocess.run") as mock_run,
            patch("quality_gate.pytest.main", return_value=0) as mock_pytest,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            assert quality_gate.run_startup_quality() == 0
            mock_pytest.assert_called_once_with(["-q"])

    def test_propagates_pytest_failure(self):
        with (
            patch("quality_gate.subprocess.run") as mock_run,
            patch("quality_gate.pytest.main", return_value=1),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            assert quality_gate.run_startup_quality() == 1


class TestRunApp:
    def test_starts_streamlit_module(self):
        with patch("run_app.subprocess.run") as mock_run:
            run_app.main()
            mock_run.assert_called_once()
            command = mock_run.call_args[0][0]
            assert command[-2:] == ["run", "main.py"]


class TestMainStartupGuard:
    def test_skips_when_gate_already_done(self):
        import main as main_module

        with patch.dict(os.environ, {"_AI_QUALITY_GATE_DONE": "1"}):
            assert main_module._should_run_startup_quality() is False

    def test_skips_while_pytest_is_running(self):
        import main as main_module

        assert main_module._should_run_startup_quality() is False

    def test_runs_when_not_under_pytest_and_not_done(self):
        import main as main_module

        modules_without_pytest = {
            key: value for key, value in sys.modules.items() if key != "pytest"
        }
        with (
            patch.dict(sys.modules, modules_without_pytest, clear=True),
            patch.dict(os.environ, {}, clear=True),
        ):
            assert main_module._should_run_startup_quality() is True

    def test_import_time_gate_exits_on_failure(self):
        import main as main_module

        with (
            patch.object(main_module, "_should_run_startup_quality", return_value=True),
            patch(
                "quality_gate.run_startup_quality",
                return_value=1,
            ),
            pytest.raises(SystemExit),
        ):
            main_module.run_import_time_quality_gate()

    def test_import_time_gate_sets_done_flag(self):
        import main as main_module

        with (
            patch.object(main_module, "_should_run_startup_quality", return_value=True),
            patch("quality_gate.run_startup_quality", return_value=0),
            patch.dict(os.environ, {}, clear=True),
        ):
            main_module.run_import_time_quality_gate()
            assert os.environ["_AI_QUALITY_GATE_DONE"] == "1"

    def test_import_time_gate_skips_when_not_needed(self):
        import main as main_module

        with (
            patch.object(
                main_module,
                "_should_run_startup_quality",
                return_value=False,
            ),
            patch("quality_gate.run_startup_quality") as mock_gate,
        ):
            main_module.run_import_time_quality_gate()
            mock_gate.assert_not_called()
