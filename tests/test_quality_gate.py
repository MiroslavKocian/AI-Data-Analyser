"""Tests for quality_gate helper and run_app launcher."""

from unittest.mock import MagicMock, patch

import pytest

import quality_gate
import run_app


class TestRunQualityChecks:
    def test_returns_ruff_check_failure(self):
        with patch("quality_gate.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert quality_gate.run_quality_checks() == 1

    def test_returns_ruff_format_failure(self):
        with patch("quality_gate.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),
                MagicMock(returncode=2),
            ]
            assert quality_gate.run_quality_checks() == 2

    def test_returns_pytest_exit_code(self):
        with patch("quality_gate.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),
                MagicMock(returncode=0),
                MagicMock(returncode=0),
            ]
            assert quality_gate.run_quality_checks() == 0
            pytest_cmd = mock_run.call_args_list[2][0][0]
            assert pytest_cmd[-3:-1] == ["-m", "pytest"]

    def test_propagates_pytest_failure(self):
        with patch("quality_gate.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),
                MagicMock(returncode=0),
                MagicMock(returncode=1),
            ]
            assert quality_gate.run_quality_checks() == 1


class TestRunApp:
    def test_starts_streamlit_module(self):
        with patch("run_app.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with pytest.raises(SystemExit) as exc_info:
                run_app.main()
            assert exc_info.value.code == 0
            mock_run.assert_called_once()
            command = mock_run.call_args[0][0]
            assert command[-2:] == ["run", "main.py"]

    def test_keyboard_interrupt_exits_cleanly(self):
        with patch("run_app.subprocess.run", side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                run_app.main()
            assert exc_info.value.code == 0


class TestMainEntry:
    def test_streamlit_entry_imports_app(self):
        import main as main_module

        assert main_module.main is not None
