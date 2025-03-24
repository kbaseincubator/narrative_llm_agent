from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.blobstore import convert_report_url
from narrative_llm_agent.util.workspace import WorkspaceUtil
from tests.test_data.test_data import load_test_data_json
from pathlib import Path
import pytest
import zipfile
import uuid

# just need to mock a single workspace call
token = "not_a_token"


@pytest.fixture
def mocked_ws_util(mocker):
    """
    Returns a WorkspaceUtil object with a mocked Workspace client that
    only gets the given report data object
    """

    def make_mocked_util(report):
        ws_util = WorkspaceUtil(token=token)
        mocker.patch.object(ws_util._ws, "get_objects", return_value=[report])
        return ws_util

    return make_mocked_util


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


def test_init():
    ws_util = WorkspaceUtil(token=token)
    assert ws_util._token == token
    assert isinstance(ws_util._ws, Workspace)


def test_get_report_fastqc_ok(mocked_ws_util, test_data_path: Path, requests_mock):
    reports_path = test_data_path / "reports" / "fastqc"
    report_zip_path = reports_path / "test_fastqc_report.zip"
    report = load_test_data_json(reports_path / "test_fastqc_report.json")
    ws_util = mocked_ws_util(report)
    with open(reports_path / "fastqc_data.txt") as report_file:
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


def test_get_report_checkm_ok(mocked_ws_util, test_data_path: Path, requests_mock):
    reports_path = test_data_path / "reports" / "checkm"
    report_zip_path = reports_path / "checkm.zip"
    report = load_test_data_json(reports_path / "test_checkm_report.json")
    ws_util = mocked_ws_util(report)
    with open(reports_path / "CheckM_summary_table.tsv") as table_file:
        table_text = table_file.read()
    expected_report = "CheckM summary table:\n" + table_text
    run_get_report_test(
        ws_util,
        report,
        [report_zip_path, report_zip_path, report_zip_path],
        [report_zip_path],
        expected_report,
        requests_mock,
    )


def test_get_report_checkm_no_file(mocked_ws_util, test_data_path: Path, requests_mock):
    reports_path = test_data_path / "reports" / "checkm"
    report = load_test_data_json(reports_path / "test_checkm_report.json")
    # remove first file link - that's the one the report interpreter cares about
    report["data"]["file_links"].pop(0)
    ws_util = mocked_ws_util(report)
    expected_report = "CheckM summary table:\nnot found"
    assert ws_util.get_report("1/2/3") == expected_report


gtdb_cases = [(False, False), (False, True), (True, False), (True, True)]


@pytest.mark.parametrize("with_archaea,with_bacteria", gtdb_cases)
def test_get_report_gtdb_ok(
    with_archaea: bool,
    with_bacteria: bool,
    mocked_ws_util,
    test_data_path: Path,
    tmpdir,
    requests_mock,
):
    reports_path = test_data_path / "reports" / "gtdbtk"
    id_map_path = reports_path / "id_to_name.map"
    archaea_path = reports_path / "gtdbtk.ar53.summary.tsv"
    bacteria_path = reports_path / "gtdbtk.bac120.summary.tsv"
    report_zip_path = tmpdir / f"gtdbtk-{uuid.uuid4()}.zip"
    files_to_zip = {id_map_path.name: id_map_path}
    expected_report = "id mapping - use this table to map summary ids to data objects. Each row has two elements - the first is the id of the archaea or bacteria finding, the second is the data object name."
    with open(id_map_path) as map_file:
        expected_report += "\n" + map_file.read() + "\n\n"
    if with_archaea:
        files_to_zip[archaea_path.name] = archaea_path
        with open(archaea_path) as arc_file:
            expected_report += "GTDB Classification Summary - this table summarizes the archaeal findings from GTDB\n"
            expected_report += arc_file.read() + "\n\n"
    if with_bacteria:
        files_to_zip[bacteria_path.name] = bacteria_path
        with open(bacteria_path) as bac_file:
            expected_report += "GTDB Classification Summary - this table summarizes the bacterial findings from GTDB\n"
            expected_report += bac_file.read()
    with zipfile.ZipFile(report_zip_path, mode="w") as report_zip:
        for filename, filepath in files_to_zip.items():
            report_zip.write(filepath, arcname=filename)

    report = load_test_data_json(reports_path / "test_gtdbtk_report.json")
    ws_util = mocked_ws_util(report)
    run_get_report_test(
        ws_util,
        report,
        [report_zip_path, report_zip_path, report_zip_path],
        [report_zip_path],
        expected_report,
        requests_mock,
    )


def test_get_report_gtdb_missing_zip(
    mocked_ws_util, test_data_path: Path, requests_mock
):
    reports_path = test_data_path / "reports" / "gtdbtk"
    report = load_test_data_json(reports_path / "test_gtdbtk_report.json")
    report["data"]["file_links"] = []
    ws_util = mocked_ws_util(report)
    assert ws_util.get_report("1/2/3") == "report file not found"


def test_get_report_bad_info(mocked_ws_util, test_data_path: Path):
    report = load_test_data_json(
        test_data_path / "reports" / "fastqc" / "test_fastqc_report.json"
    )
    report["info"] = []
    ws_util = mocked_ws_util(report)
    with pytest.raises(
        ValueError,
        match="Object with UPA 1/2/3 does not appear to be properly formatted.",
    ):
        ws_util.get_report("1/2/3")


def test_get_report_bad_type(mocked_ws_util, test_data_path: Path):
    report = load_test_data_json(
        test_data_path / "reports" / "fastqc" / "test_fastqc_report.json"
    )
    wrong_type = "NotAReport.Object-1.0"
    report["info"][2] = wrong_type
    ws_util = mocked_ws_util(report)
    with pytest.raises(
        ValueError, match=f"Object with UPA 1/2/3 is not a report but a {wrong_type}."
    ):
        ws_util.get_report("1/2/3")


def test_get_html_report(mocked_ws_util, test_data_path: Path, requests_mock):
    report = load_test_data_json(
        test_data_path / "reports" / "html" / "test_report_html_links.json"
    )
    ws_util = mocked_ws_util(report)
    expected = (
        "message: \ndirect html: \nhtml report: html file:\n<html>some html</html>\n"
    )
    run_get_report_test(
        ws_util,
        report,
        [],
        [test_data_path / "reports" / "html" / "test_html_report.zip"],
        expected,
        requests_mock,
    )


def test_get_html_report_bad_file(mocked_ws_util, test_data_path: Path, requests_mock):
    report = load_test_data_json(
        test_data_path / "reports" / "html" / "test_report_html_links.json"
    )
    report["data"]["html_links"][0]["name"] = "not_found_file.html"
    ws_util = mocked_ws_util(report)
    expected = "message: \ndirect html: \nhtml report: html file:\n"
    run_get_report_test(
        ws_util,
        report,
        [],
        [test_data_path / "reports" / "html" / "test_html_report.zip"],
        expected,
        requests_mock,
    )


def test_get_report_bad_dl(mocked_ws_util, test_data_path: Path, requests_mock):
    report = load_test_data_json(
        test_data_path / "reports" / "html" / "test_report_html_links.json"
    )
    mock_url = report["data"]["html_links"][0]["URL"]
    requests_mock.get(convert_report_url(mock_url), text="failed", status_code=500)
    ws_util = mocked_ws_util(report)
    expected = "message: \ndirect html: \nhtml report: html file:\n"
    assert ws_util.get_report("1/2/3") == expected
