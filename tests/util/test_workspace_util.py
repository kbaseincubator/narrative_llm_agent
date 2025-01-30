from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.blobstore import convert_report_url
from narrative_llm_agent.util.workspace import WorkspaceUtil
from tests.test_data.test_data import load_test_data_json
from pathlib import Path
import pytest
import json

# just need to mock a single workspace call
token = "not_a_token"


@pytest.fixture
def mocked_ws_util(mocker):
    """
    Returns a WorkspaceUtil object with a mocked Workspace client that
    only gets the given report data object
    """

    def make_mocked_util(report):
        # mocker.patch("narrative_llm_agent.util.workspace.WS_ENDPOINT", endpoint)
        ws_util = WorkspaceUtil(token=token)
        mocker.patch.object(ws_util._ws, "get_objects", return_value=[report])
        return ws_util

    return make_mocked_util


def test_init():
    ws_util = WorkspaceUtil(token=token)
    assert ws_util._token == token
    assert isinstance(ws_util._ws, Workspace)


def test_get_report_fastqc_ok(mocked_ws_util, test_data_path: Path, requests_mock):
    report_zip_path = test_data_path / "test_report_dir.zip"
    report = load_test_data_json(test_data_path / "test_fastqc_report.json")
    ws_util = mocked_ws_util(report)
    with open(test_data_path / "test_report_dir" / "fastqc_data.txt") as report_file:
        report_text = report_file.read()
    expected_report = []
    for idx, file in enumerate(report["data"]["file_links"]):
        expected_report.append(f"file {idx + 1}: {file['name']}:")
        expected_report.append(report_text)
    run_get_report_test(
        ws_util,
        report,
        [report_zip_path, report_zip_path],
        [report_zip_path],
        "\n".join(expected_report),
        requests_mock,
    )


def test_get_report_fastqc_shock(mocker, requests_mock):
    pass


def test_get_report_bad_dl(mocker, requests_mock):
    pass


def test_get_report_bad_info(mocked_ws_util, test_data_path: Path):
    report = load_test_data_json(test_data_path / "test_fastqc_report.json")
    report["info"] = []
    ws_util = mocked_ws_util(report)
    with pytest.raises(
        ValueError,
        match="Object with UPA 1/2/3 does not appear to be properly formatted.",
    ):
        ws_util.get_report("1/2/3")


def test_get_report_bad_type(mocked_ws_util, test_data_path: Path):
    report = load_test_data_json(test_data_path / "test_fastqc_report.json")
    wrong_type = "NotAReport.Object-1.0"
    report["info"][2] = wrong_type
    ws_util = mocked_ws_util(report)
    with pytest.raises(
        ValueError, match=f"Object with UPA 1/2/3 is not a report but a {wrong_type}."
    ):
        ws_util.get_report("1/2/3")


def test_get_html_report(mocked_ws_util, test_data_path: Path, requests_mock):
    report = load_test_data_json(test_data_path / "test_report_html_links.json")
    ws_util = mocked_ws_util(report)
    expected = (
        "message: \ndirect html: \nhtml report: html file:\n<html>some html</html>\n"
    )
    run_get_report_test(
        ws_util,
        report,
        [],
        [test_data_path / "test_html_report.zip"],
        expected,
        requests_mock,
    )


def run_get_report_test(
    ws_util: WorkspaceUtil,
    report: dict,
    file_paths: list[Path],
    html_paths: list[Path],
    expected: str,
    requests_mock,
):
    if len(file_paths) != len(report["data"]["file_links"]):
        raise ValueError(
            "The number of file paths to mock must match the number of file links in the report object"
        )
    if len(html_paths) != len(report["data"]["html_links"]):
        raise ValueError(
            "The number of html paths to mock must match the number of html links in the report object"
        )
    for idx, file_path in enumerate(file_paths):
        with open(file_path, "rb") as archive:
            file_archive = archive.read()
            requests_mock.get(
                convert_report_url(report["data"]["file_links"][idx]["URL"]),
                content=file_archive,
            )
    for idx, html_path in enumerate(html_paths):
        with open(html_path, "rb") as archive:
            html_archive = archive.read()
            requests_mock.get(
                convert_report_url(report["data"]["html_links"][idx]["URL"]),
                content=html_archive,
            )
    assert ws_util.get_report("1/2/3") == expected
