from pytest_mock import MockerFixture
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine, JobState
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.blobstore import Blobstore, convert_report_url
from narrative_llm_agent.tools.report_tools import get_report, get_report_from_job_id
from tests.test_data.test_data import load_test_data_json
from pathlib import Path
import pytest
import zipfile
import uuid

# just need to mock a single workspace call
token = "not_a_token"


@pytest.fixture
def mocked_ws(mocker: MockerFixture):
    """
    Returns a mocked Workspace client object that only gets the given report data object
    """

    def make_mocked_client(report):
        ws = Workspace(token=token)
        mocker.patch.object(ws, "get_objects", return_value=[report])
        return ws

    return make_mocked_client


def run_get_report_test(
    ws: Workspace,
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
    # TODO: this is too deep in the code. Should mock blobstore instead.
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
    assert get_report("1/2/3", ws, Blobstore(token=token)) == expected


def test_get_report_fastqc_ok(mocked_ws, test_data_path: Path, requests_mock):
    reports_path = test_data_path / "reports" / "fastqc"
    report_zip_path = reports_path / "test_fastqc_report.zip"
    report = load_test_data_json(reports_path / "test_fastqc_report.json")
    ws = mocked_ws(report)
    with open(reports_path / "fastqc_data.txt") as report_file:
        report_text = report_file.read()
    expected_report = []
    for idx, file in enumerate(report["data"]["file_links"]):
        expected_report.append(f"file {idx + 1}: {file['name']}:")
        expected_report.append(report_text)
    run_get_report_test(
        ws,
        report,
        [report_zip_path, report_zip_path],
        [report_zip_path],
        "\n".join(expected_report),
        requests_mock,
    )


def test_get_report_fastqc_shock(mocker, requests_mock):
    pass


def test_get_report_checkm_ok(mocked_ws, test_data_path: Path, requests_mock):
    reports_path = test_data_path / "reports" / "checkm"
    report_zip_path = reports_path / "checkm.zip"
    report = load_test_data_json(reports_path / "test_checkm_report.json")
    ws = mocked_ws(report)
    with open(reports_path / "CheckM_summary_table.tsv") as table_file:
        table_text = table_file.read()
    expected_report = "CheckM summary table:\n" + table_text
    run_get_report_test(
        ws,
        report,
        [report_zip_path, report_zip_path, report_zip_path],
        [report_zip_path],
        expected_report,
        requests_mock,
    )


def test_get_report_checkm_no_file(mocked_ws, test_data_path: Path):
    reports_path = test_data_path / "reports" / "checkm"
    report = load_test_data_json(reports_path / "test_checkm_report.json")
    # remove first file link - that's the one the report interpreter cares about
    report["data"]["file_links"].pop(0)
    ws = mocked_ws(report)
    expected_report = "CheckM summary table:\nnot found"
    assert get_report("1/2/3", ws, Blobstore()) == expected_report


gtdb_cases = [(False, False), (False, True), (True, False), (True, True)]


@pytest.mark.parametrize("with_archaea,with_bacteria", gtdb_cases)
def test_get_report_gtdb_ok(
    with_archaea: bool,
    with_bacteria: bool,
    mocked_ws,
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
    ws = mocked_ws(report)
    run_get_report_test(
        ws,
        report,
        [report_zip_path, report_zip_path, report_zip_path],
        [report_zip_path],
        expected_report,
        requests_mock,
    )


def test_get_report_gtdb_missing_zip(mocked_ws, test_data_path: Path):
    reports_path = test_data_path / "reports" / "gtdbtk"
    report = load_test_data_json(reports_path / "test_gtdbtk_report.json")
    report["data"]["file_links"] = []
    ws = mocked_ws(report)
    assert get_report("1/2/3", ws, Blobstore()) == "report file not found"


def test_get_report_bad_info(mocked_ws, test_data_path: Path):
    report = load_test_data_json(
        test_data_path / "reports" / "fastqc" / "test_fastqc_report.json"
    )
    report["info"] = []
    ws = mocked_ws(report)
    with pytest.raises(
        ValueError,
        match="Object with UPA 1/2/3 does not appear to be properly formatted.",
    ):
        get_report("1/2/3", ws, Blobstore())


def test_get_report_bad_type(mocked_ws, test_data_path: Path):
    report = load_test_data_json(
        test_data_path / "reports" / "fastqc" / "test_fastqc_report.json"
    )
    wrong_type = "NotAReport.Object-1.0"
    report["info"][2] = wrong_type
    ws = mocked_ws(report)
    with pytest.raises(
        ValueError, match=f"Object with UPA 1/2/3 is not a report but a {wrong_type}."
    ):
        get_report("1/2/3", ws, Blobstore())


def test_get_html_report(mocked_ws, test_data_path: Path, requests_mock):
    report = load_test_data_json(
        test_data_path / "reports" / "html" / "test_report_html_links.json"
    )
    ws = mocked_ws(report)
    expected = (
        "message: \ndirect html: \nhtml report: html file:\n<html>some html</html>\n"
    )
    run_get_report_test(
        ws,
        report,
        [],
        [test_data_path / "reports" / "html" / "test_html_report.zip"],
        expected,
        requests_mock,
    )


def test_get_html_report_bad_file(mocked_ws, test_data_path: Path, requests_mock):
    report = load_test_data_json(
        test_data_path / "reports" / "html" / "test_report_html_links.json"
    )
    report["data"]["html_links"][0]["name"] = "not_found_file.html"
    ws = mocked_ws(report)
    expected = "message: \ndirect html: \nhtml report: html file:\n"
    run_get_report_test(
        ws,
        report,
        [],
        [test_data_path / "reports" / "html" / "test_html_report.zip"],
        expected,
        requests_mock,
    )


def test_get_report_bad_dl(mocked_ws, test_data_path: Path, requests_mock):
    report = load_test_data_json(
        test_data_path / "reports" / "html" / "test_report_html_links.json"
    )
    mock_url = report["data"]["html_links"][0]["URL"]
    requests_mock.get(convert_report_url(mock_url), text="failed", status_code=500)
    ws = mocked_ws(report)
    expected = "message: \ndirect html: \nhtml report: html file:\n"
    assert get_report("1/2/3", ws, Blobstore()) == expected


"""
cases to cover:
1. Bad job id
2. x job queued
3. x job running
4. x job error'd
5. x job terminated
6. x job complete, no outputs
7. x job complete, no report
8. job complete, has report - happy path?
9. job complete, report ref isn't a report
10. x job complete, no result field
"""
job_id_report_cases = [
    ("queued", None, "The job is not yet complete"),
    ("running", None, "The job is not yet complete"),
    (
        "error",
        None,
        "The job did not finish successfully, so there is no report to return.",
    ),
    (
        "terminated",
        None,
        "The job did not finish successfully, so there is no report to return.",
    ),
    ("other", None, "Unknown job status 'other'"),
    ("completed", None, "The job was completed, but no job output was found."),
    (
        "completed",
        {},
        "The job output seems to be malformed, there is no 'result' field.",
    ),
    (
        "completed",
        {"result": [{"stuff": "things"}]},
        "No report object was found in the job results.",
    ),
]


@pytest.mark.parametrize("status,job_output,expected", job_id_report_cases)
def test_get_report_from_job_id_no_report(
    status, job_output, expected, mock_job_states, mocker
):
    job_id = "job_id_1"
    state = mock_job_states[job_id].copy()
    state["status"] = status
    state["job_output"] = job_output
    ee_mock = mocker.Mock(spec=ExecutionEngine)
    ee_mock.check_job.return_value = JobState(state)
    assert get_report_from_job_id(job_id, ee_mock, Workspace(), Blobstore()) == expected


def test_get_report_from_job_id_ok(mock_job_states, mocker):
    job_id = "job_id_1"
    some_report = "this is a report"
    state = mock_job_states[job_id].copy()
    report_ref = "11/22/33"
    state["job_output"] = {"result": [{"report_ref": report_ref}]}
    ee_mock = mocker.Mock(spec=ExecutionEngine)
    ee_mock.check_job.return_value = JobState(state)
    report_mock = mocker.patch(
        "narrative_llm_agent.tools.report_tools.get_report", return_value=some_report
    )
    ws = Workspace()
    blobstore = Blobstore()
    assert get_report_from_job_id(job_id, ee_mock, ws, blobstore) == some_report
    report_mock.assert_called_once_with(report_ref, ws, blobstore)
