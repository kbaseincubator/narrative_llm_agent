from narrative_llm_agent.kbase.objects.narrative import (
    AppCell,
    BulkImportCell,
    Cell,
    CodeCell,
    KBaseCell,
    MarkdownCell,
    OutputCell,
    RawCell,
    Narrative,
    NarrativeMetadata,
    is_narrative
)
import pytest

@pytest.mark.parametrize("type_str,expected", [
    ("KBaseNarrative.Narrative", True),
    ("KBaseNarrative.Narrative-1.0", True),
    ("NotANarrative", False),
    (None, False),
    (1, False),
    (["not", "a", "narrative"], False),
    ({"not": "a narrative"}, False)
])
def test_is_narrative(type_str, expected):
    assert is_narrative(type_str) == expected
