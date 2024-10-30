from pathlib import Path
from narrative_llm_agent.kbase.clients.execution_engine import JobState
from narrative_llm_agent.kbase.objects.narrative import (
    AppCell,
    BulkImportCell,
    Cell,
    CodeCell,
    DataCell,
    KBaseCell,
    MarkdownCell,
    OutputCell,
    RawCell,
    Narrative,
    NarrativeMetadata,
    is_narrative,
)
from tests.test_data.test_data import load_test_data_json
import json
import pytest


@pytest.mark.parametrize(
    "type_str,expected",
    [
        ("KBaseNarrative.Narrative", True),
        ("KBaseNarrative.Narrative-1.0", True),
        ("NotANarrative", False),
        (None, False),
        (1, False),
        (["not", "a", "narrative"], False),
        ({"not": "a narrative"}, False),
    ],
)
def test_is_narrative(type_str, expected):
    assert is_narrative(type_str) == expected


class TestCell:
    def test_init(self):
        cell_dict = {"source": "some code"}
        cell = Cell("test_cell", cell_dict)
        assert cell.cell_type == "test_cell"
        assert cell.source == "some code"

    def test_get_info_str(self):
        cell = Cell("test_cell", {})
        assert cell.get_info_str() == "jupyter.test_cell"

    def test_to_dict(self):
        cell_dict = {"source": "some source"}
        cell = Cell("test_cell", cell_dict)
        assert cell.to_dict() == cell_dict


# Similarly, write tests for CodeCell, RawCell, MarkdownCell, KBaseCell, and their subclasses


class TestCodeCell:
    def test_init_with_outputs(self):
        cell_dict = {"source": "some source", "outputs": ["output1", "output2"]}
        cell = CodeCell(cell_dict)
        assert cell.outputs == ["output1", "output2"]
        assert cell.cell_type == "code"

    def test_init_no_outputs(self):
        cell_dict = {"source": "some code"}
        cell = CodeCell(cell_dict)
        assert cell.outputs == []

    def test_get_info_str(self):
        cell = CodeCell({})
        assert cell.get_info_str() == "jupyter.code"


class TestMarkdownCell:
    def test_init(self):
        cell_dict = {"source": "some markdown"}
        cell = MarkdownCell(cell_dict)
        assert cell.cell_type == "markdown"
        assert cell.source == "some markdown"

    def test_get_info_str(self):
        cell = MarkdownCell({})
        assert cell.get_info_str() == "jupyter.markdown"


class TestRawCell:
    def test_init(self):
        cell_dict = {"source": "some raw text"}
        cell = RawCell(cell_dict)
        assert cell.cell_type == "raw"
        assert cell.source == "some raw text"

    def test_get_info_str(self):
        cell = RawCell({})
        assert cell.get_info_str() == "jupyter.raw"


# Continue with similar tests for RawCell, MarkdownCell


class TestAppCell:
    @pytest.fixture
    def sample_cell_dict(self):
        return {
            "metadata": {
                "kbase": {
                    "appCell": {
                        "app": {
                            "id": "app_id",
                            "gitCommitHash": "commit_hash",
                            "spec": {"info": {"id": "app_id", "name": "App Name"}},
                        }
                    }
                }
            }
        }

    def test_init(self, sample_cell_dict):
        cell = AppCell(sample_cell_dict)
        assert (
            cell.app_spec
            == sample_cell_dict["metadata"]["kbase"]["appCell"]["app"]["spec"]
        )
        assert cell.app_id == "app_id"
        assert cell.app_name == "App Name"
        assert cell.job_state is None  # TODO
        assert cell.cell_type == "code"
        assert cell.kb_cell_type == "KBaseApp"

    def test_get_info_str(self, sample_cell_dict):
        cell = AppCell(sample_cell_dict)
        assert cell.get_info_str() == "method.app_id/commit_hash"


class TestBulkImportCell:
    def test_init(self):
        cell = BulkImportCell({})
        assert cell.cell_type == "code"
        assert cell.kb_cell_type == "KBaseBulkImport"

    def test_get_info_str(self):
        cell = BulkImportCell({})
        assert cell.get_info_str() == "kbase.bulk_import"


class TestDataCell:
    def test_init(self):
        cell = DataCell({})
        assert cell.cell_type == "code"
        assert cell.kb_cell_type == "KBaseData"

    def test_get_info_str(self):
        cell = DataCell({})
        assert cell.get_info_str() == "kbase.data_viewer"


class TestOutputCell:
    def test_init(self):
        cell = OutputCell({})
        assert cell.cell_type == "code"
        assert cell.kb_cell_type == "KBaseOutput"

    def test_get_info_str(self):
        cell = OutputCell({})
        assert cell.get_info_str() == "kbase.app_output"


class TestKBaseCell:
    kb_type = "some_kbase_cell"

    def test_init(self):
        cell = KBaseCell(self.kb_type, {})
        assert cell.cell_type == "code"
        assert cell.kb_cell_type == self.kb_type

    def test_get_info_str(self):
        cell = KBaseCell(self.kb_type, {})
        assert cell.get_info_str() == "kbase." + self.kb_type


class TestNarrativeMetadata:
    @pytest.fixture
    def sample_narrative_metadata(self):
        """Provides a sample narrative metadata for testing."""
        return {
            "creator": "A KBase User",
            "data_dependencies": ["1/2/3", "4/5/6"],
            "description": "Sample description",
            "format": "ipynb",
            "name": "Sample Narrative",
            "is_temporary": True,
        }

    def test_init(self, sample_narrative_metadata):
        """Test the init of NarrativeMetadata."""
        narr_meta = NarrativeMetadata(sample_narrative_metadata)

        assert narr_meta.creator == sample_narrative_metadata["creator"]
        assert (
            narr_meta.data_dependencies
            == sample_narrative_metadata["data_dependencies"]
        )
        assert narr_meta.description == sample_narrative_metadata["description"]
        assert narr_meta.format == sample_narrative_metadata["format"]
        assert narr_meta.name == sample_narrative_metadata["name"]
        assert narr_meta.is_temporary is True
        assert narr_meta.raw == sample_narrative_metadata

    def test_init_with_defaults(self):
        """Test init with missing fields and default values."""
        narr_meta = NarrativeMetadata({})

        assert narr_meta.creator == "unknown"
        assert narr_meta.data_dependencies == []
        assert narr_meta.description == ""
        assert narr_meta.format == "ipynb"
        assert narr_meta.name == "unknown narrative"
        assert not narr_meta.is_temporary

    def test_to_dict(self, sample_narrative_metadata):
        """Test the to_dict method."""
        narr_meta = NarrativeMetadata(sample_narrative_metadata)
        assert narr_meta.to_dict() == sample_narrative_metadata


class TestNarrative:
    def test_init(self, sample_narrative_json):
        test_narr = sample_narrative_json
        narr_dict = json.loads(test_narr)
        narr = Narrative(narr_dict)
        assert narr.raw == narr_dict
        assert narr.nbformat == narr_dict["nbformat"]
        assert narr.nbformat_minor == narr_dict["nbformat_minor"]
        for cell in narr.cells:
            assert isinstance(cell, Cell)

    def test_init_fail(self):
        with pytest.raises(ValueError) as err:
            Narrative({})
        assert "'cells' key not found" in str(err.value)

    def test_to_str(self, sample_narrative_json):
        narr_dict = json.loads(sample_narrative_json)
        narr = Narrative(narr_dict)
        assert str(narr) == json.dumps(narr_dict)

    def test_add_markdown_cell(self, sample_narrative_json):
        test_markdown = "# This is some test markdown."
        narr = Narrative(json.loads(sample_narrative_json))
        num_cells = len(narr.cells)
        new_cell = narr.add_markdown_cell(test_markdown)
        assert len(narr.cells) == num_cells + 1
        assert new_cell == narr.cells[-1]
        assert isinstance(new_cell, MarkdownCell)
        assert new_cell.source == test_markdown

    def test_add_code_cell(self, sample_narrative_json):
        test_source = "print('this is valid code.')"
        outputs = [
            {
                "data": {"text/plain": ["'this is valid code.'"]},
                "execution_count": 5,
                "metadata": {},
                "output_type": "execute_result",
            }
        ]
        narr = Narrative(json.loads(sample_narrative_json))
        num_cells = len(narr.cells)
        new_cell = narr.add_code_cell(test_source, outputs=outputs)
        assert len(narr.cells) == num_cells + 1
        assert new_cell == narr.cells[-1]
        assert isinstance(new_cell, CodeCell)
        assert new_cell.source == test_source
        assert new_cell.outputs == outputs

    def test_add_code_cell_no_outputs(self, sample_narrative_json):
        test_source = "some other source"
        narr = Narrative(json.loads(sample_narrative_json))
        num_cells = len(narr.cells)
        new_cell = narr.add_code_cell(test_source)
        assert len(narr.cells) == num_cells + 1
        assert new_cell == narr.cells[-1]
        assert isinstance(new_cell, CodeCell)
        assert new_cell.source == test_source
        assert new_cell.outputs == []

    def test_get_cell_counts(self, sample_narrative_json):
        narr = Narrative(json.loads(sample_narrative_json))
        counts = narr.get_cell_counts()
        assert isinstance(counts, dict)
        total_cells = sum(list(counts.values()))
        assert total_cells == len(narr.cells)

    def test_add_app_cell(self, sample_narrative_json, app_spec):
        narr = Narrative(json.loads(sample_narrative_json))
        num_cells = len(narr.cells)
        job_state = JobState(
            load_test_data_json(Path("app_spec_data") / "app_spec_job_state.json")
        )
        new_cell = narr.add_app_cell(job_state, app_spec)
        assert new_cell.app_id == app_spec["info"]["id"]
        assert new_cell.app_name == app_spec["info"]["name"]
        assert new_cell.cell_type == "code"
        assert new_cell.kb_cell_type == "KBaseApp"
        assert len(narr.cells) == num_cells + 1
