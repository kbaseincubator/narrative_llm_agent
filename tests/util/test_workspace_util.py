from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.util.workspace import WorkspaceUtil
from tests.test_data.test_data import get_test_report
from pathlib import Path
import pytest
import json

# just need to mock a single workspace call
token = "not_a_token"
# endpoint = "https://notreal.kbase.us/services/"

@pytest.fixture
def mocked_ws_util(mocker):
    """
    Returns a WorkspaceUtil object with a mocked Workspace client that
    only gets the given report data object
    """
    def make_mocked_util(report):
        # mocker.patch("narrative_llm_agent.util.workspace.WS_ENDPOINT", endpoint)
        ws_util = WorkspaceUtil(token)
        mocker.patch.object(ws_util._ws, "get_objects", return_value=[report])
        return ws_util
    return make_mocked_util

def test_init():
    ws_util = WorkspaceUtil(token)
    assert ws_util._token == token
    assert isinstance(ws_util._ws, Workspace)

def test_get_report_fastqc_ok(mocked_ws_util, requests_mock):
    file_url = "https://notreal.kbase.us/file/report_file"
    report_zip_path = Path(__file__).parent / ".." / "test_data" / "test_report_dir.zip"
    report = get_test_report("fastqc", file_url=file_url)
    ws_util = mocked_ws_util(report)
    with open(report_zip_path, "rb") as archive:
        report_archive = archive.read()
    requests_mock.get(file_url, content=report_archive)
    with open(Path(__file__).parent / ".." / "test_data" / "test_report_dir" / "fastqc_data.txt") as report_file:
        report_text = report_file.read()
    expected_report = []
    for idx, file in enumerate(report["data"]["file_links"]):
        expected_report.append(f"file {idx+1}: {file['name']}:")
        expected_report.append(report_text)
    assert ws_util.get_report("1/2/3") == "\n".join(expected_report)

def test_get_report_fastqc_shock(mocker, requests_mock):
    pass

def test_get_report_bad_dl(mocker, requests_mock):
    pass

def test_get_report_bad_info(mocked_ws_util):
    report = get_test_report("fastqc")
    report["info"] = []
    ws_util = mocked_ws_util(report)
    with pytest.raises(ValueError, match="Object with UPA 1/2/3 does not appear to be properly formatted."):
        ws_util.get_report("1/2/3")

def test_get_report_bad_type(mocked_ws_util):
    report = get_test_report("fastqc")
    wrong_type = "NotAReport.Object-1.0"
    report["info"][2] = wrong_type
    ws_util = mocked_ws_util(report)
    with pytest.raises(ValueError, match=f"Object with UPA 1/2/3 is not a report but a {wrong_type}."):
        ws_util.get_report("1/2/3")

def test_get_other_report(mocked_ws_util):
    report = get_test_report("other")
    ws_util = mocked_ws_util(report)
    assert ws_util.get_report("1/2/3") == json.dumps(report)
