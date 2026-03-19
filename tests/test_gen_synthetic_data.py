from __future__ import annotations

from pathlib import Path

from agent.output.models import ApplicationInput
from scripts.gen_synthetic_data import generate_applications, write_jsonl


def test_generate_applications_and_write_jsonl(tmp_path):
    applications = generate_applications(count=5, seed=7)

    assert len(applications) == 5
    for application in applications:
        ApplicationInput.model_validate(
            {key: value for key, value in application.items() if key != "synthetic_profile"}
        )

    output_path = tmp_path / "synthetic.jsonl"
    write_jsonl(applications, output_path)

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 5
