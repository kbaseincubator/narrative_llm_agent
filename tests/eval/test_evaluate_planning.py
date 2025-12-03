import json
from pathlib import Path

import pytest

from narrative_llm_agent.eval import evaluate_planning


def test_slugify_basic():
    assert evaluate_planning.slugify("Hello World!") == "Hello-World"
    assert evaluate_planning.slugify("alpha/beta_gamma") == "alpha-beta_gamma"


def test_load_metadata_reads_file(tmp_path: Path):
    payload = {"isolates": [{"narrative_id": 1}]}
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps(payload), encoding="utf-8")

    result = evaluate_planning.load_metadata(meta_path)

    assert result == payload


def test_build_descriptions_includes_fields():
    metadata = {
        "isolates": [
            {
                "narrative_id": "42",
                "species": "Bacillus testus",
                "strain": "SC001",
                "number_of_reads": 12345,
            }
        ]
    }

    descriptions = evaluate_planning.build_descriptions(metadata, sequencing_platform="NovaSeq")

    assert set(descriptions.keys()) == {"42"}
    text = descriptions["42"]
    assert "NovaSeq" in text
    assert "Bacillus testus" in text
    assert "SC001" in text
    assert "12345" in text


def test_create_workflow_json_writes_steps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class DummyAppCell:
        def __init__(self, app_id, app_name):
            self.app_id = app_id
            self.app_name = app_name

    class DummyNarrative:
        def __init__(self, cells):
            self.cells = cells

    monkeypatch.setattr(evaluate_planning, "AppCell", DummyAppCell)
    monkeypatch.setattr(
        evaluate_planning,
        "get_narrative_from_wsid",
        lambda narrative_id, ws: DummyNarrative(
            [
                DummyAppCell("kb/app1", "App One"),
                DummyAppCell("kb/app2", "App Two"),
            ]
        ),
    )

    out_path = evaluate_planning.create_workflow_json(
        narrative_id=101, workspace=object(), output_dir=tmp_path
    )

    assert out_path.exists()
    written = json.loads(out_path.read_text())
    assert written == {
        "step1": {"app_name": "App One", "app_id": "kb/app1"},
        "step2": {"app_name": "App Two", "app_id": "kb/app2"},
    }
