from pathlib import Path

import pytest

from app.dotenv_loader import load_dotenv


def test_loads_plain_export_and_quoted_values_without_expansion(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nA=plain\nexport B='quoted value'\nC=\"$A literal\"\nEMPTY=\n",
        encoding="utf-8",
    )
    env = {"A": "from-process"}
    loaded = load_dotenv(env_file, env)
    assert env == {
        "A": "from-process",
        "B": "quoted value",
        "C": "$A literal",
        "EMPTY": "",
    }
    assert loaded == ["B", "C", "EMPTY"]


def test_missing_file_is_ignored(tmp_path: Path):
    assert load_dotenv(tmp_path / "missing.env", {}) == []


@pytest.mark.parametrize("line", ["NOT_ASSIGNMENT", "BAD-KEY=value", "BROKEN='quote"])
def test_malformed_lines_fail_without_echoing_values(tmp_path: Path, line: str):
    env_file = tmp_path / ".env"
    env_file.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError) as error:
        load_dotenv(env_file, {})
    assert "line 1" in str(error.value)
    assert "value" not in str(error.value)
