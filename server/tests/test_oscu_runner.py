import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run-oscu-sandbox-check.py"


def test_runner_defaults_to_offline_dry_run_without_credentials(tmp_path: Path):
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"customerPin": "DO-NOT-PRINT"}), encoding="utf-8")
    env = os.environ.copy()
    for name in (
        "ETIMS_OSCU_CONSUMER_KEY",
        "ETIMS_OSCU_CONSUMER_SECRET",
        "ETIMS_OSCU_APP_ID",
        "ETIMS_OSCU_TIN",
        "ETIMS_OSCU_BHF_ID",
        "ETIMS_OSCU_CMC_KEY",
    ):
        env.pop(name, None)

    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--operation",
            "branch-list",
            "--payload",
            str(payload),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "DRY RUN" in result.stdout
    assert "No network request was made" in result.stdout
    assert "Payload field count: 1" in result.stdout
    assert "DO-NOT-PRINT" not in result.stdout
    assert "customerPin" not in result.stdout
    assert "Missing required environment variables" not in result.stderr


def test_runner_rejects_non_object_payload_before_any_network_call(tmp_path: Path):
    payload = tmp_path / "payload.json"
    payload.write_text("[]", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--operation",
            "branch-list",
            "--payload",
            str(payload),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Payload must be a JSON object" in result.stderr
