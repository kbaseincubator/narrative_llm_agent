from narrative_llm_agent.kbase.objects.report import KBaseReport, LinkedFile, is_report
import pytest


@pytest.mark.parametrize(
    "type_str,expected",
    [
        ("KBaseReport.Report", True),
        ("KBaseReport.Report-1.0", True),
        ("NotAReport", False),
        (None, False),
        (1, False),
        (["not", "a", "report"], False),
        ({"not": "a report"}, False),
    ],
)
def test_is_report(type_str, expected):
    assert is_report(type_str) == expected


def test_linked_file():
    my_file = {
        "handle": "some_file_handle_id",
        "description": "a_file",
        "name": "FooFile",
        "label": "ItIsAFile",
        "URL": "https://totally-a-file.com",
    }

    linked = LinkedFile(**my_file)
    assert linked.handle == my_file["handle"]
    assert linked.description == my_file["description"]
    assert linked.name == my_file["name"]
    assert linked.label == my_file["label"]
    assert linked.URL == my_file["URL"]


@pytest.fixture
def sample_report_obj():
    """Provides a sample report object for testing."""
    return {
        "text_message": "Sample text message",
        "direct_html": "<html></html>",
        "direct_html_link_index": 0,
        "warnings": ["warning1", "warning2"],
        "html_links": [{"name": "link1", "url": "http://example.com"}],
        "file_links": [{"name": "file1", "url": "http://examplefile.com"}],
    }


def test_report_init(sample_report_obj):
    """Test the initialization of KBaseReport."""
    report = KBaseReport(**sample_report_obj)

    assert report.text_message == sample_report_obj["text_message"]
    assert report.direct_html == sample_report_obj["direct_html"]
    assert report.direct_html_link_index == sample_report_obj["direct_html_link_index"]
    assert report.warnings == sample_report_obj["warnings"]
    assert all(isinstance(link, LinkedFile) for link in report.html_links)
    assert all(isinstance(link, LinkedFile) for link in report.file_links)


def test_report_init_with_missing_fields():
    """Test the initialization with missing fields in the report object."""
    report_obj = {}
    report = KBaseReport(**report_obj)

    assert report.text_message == ""
    assert report.direct_html == ""
    assert report.direct_html_link_index is None
    assert report.warnings == []
    assert report.html_links == []
    assert report.file_links == []
