from __future__ import annotations

from typer.testing import CliRunner

from ai_chain_radar.cli import app


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AI Chain Radar CLI" in result.stdout
