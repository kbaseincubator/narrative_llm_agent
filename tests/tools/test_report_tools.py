from pytest_mock import MockerFixture
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine, JobState
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.blobstore import Blobstore, convert_report_url
from narrative_llm_agent.tools.report_tools import (
    get_report,
    get_report_from_job_id,
    _parse_fastqc_report,
    _round_floats_in_line,
    _process_fastqc_module,
)
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


# Tests for _parse_fastqc_report and helper functions


class TestRoundFloatsInLine:
    """Tests for the _round_floats_in_line helper function."""

    def test_round_simple_float(self):
        """Test rounding a simple floating point number."""
        result = _round_floats_in_line("1\t31.953190445790447\t33.0")
        assert result == "1\t31.95\t33.00"

    def test_preserve_integers(self):
        """Test that integers without decimal points are not modified."""
        result = _round_floats_in_line("4\t5\t100")
        assert result == "4\t5\t100"

    def test_preserve_filename_with_underscores(self):
        """Test that filenames with underscores are not modified."""
        result = _round_floats_in_line("Filename\tBsubtilis_rawdata_231783_2_1.rev.fastq")
        assert result == "Filename\tBsubtilis_rawdata_231783_2_1.rev.fastq"

    def test_preserve_paths(self):
        """Test that file paths are not modified."""
        result = _round_floats_in_line("Path\t/home/user/data_file_123.txt")
        assert result == "Path\t/home/user/data_file_123.txt"

    def test_round_range_values(self):
        """Test that range values with integers are not rounded."""
        result = _round_floats_in_line("10-14\t36.26104977967395\t37.4")
        assert result == "10-14\t36.26\t37.40"

    def test_round_small_scientific_notation(self):
        """Test rounding of very small scientific notation to keep scientific form."""
        result = _round_floats_in_line("1\t3.7577475519157133E-4\t-0.39234694690636474")
        # Very small numbers stay in scientific notation with 2 sig figs
        assert result == "1\t3.76E-04\t-0.39"

    def test_round_negative_small_numbers(self):
        """Test rounding of small negative numbers to scientific notation."""
        result = _round_floats_in_line("1\t-2.6426837828009912E-5\t-0.144989755655331")
        assert result == "1\t-2.64E-05\t-0.14"

    def test_no_modification_for_non_numeric(self):
        """Test that non-numeric fields are unchanged."""
        result = _round_floats_in_line("#Base\tMean\tMedian")
        assert result == "#Base\tMean\tMedian"

    def test_preserve_text_with_dots(self):
        """Test that text fields with special characters are preserved."""
        result = _round_floats_in_line("Encoding\tSanger / Illumina 1.9")
        # Should NOT round because field contains "/" which indicates it's text
        assert result == "Encoding\tSanger / Illumina 1.9"

    def test_mixed_content(self):
        """Test a line with mixed numeric and string fields."""
        result = _round_floats_in_line("Total Sequences\t256892.0")
        assert result == "Total Sequences\t256892.00"

    def test_example_from_issue(self):
        """Test the exact example from the GitHub issue."""
        result = _round_floats_in_line("4\t0.0\t2.6426837828009912E-5\t0.0\t0.0\t7.928051348402974E-5\t7.928051348402974E-5")
        assert result == "4\t0.00\t2.64E-05\t0.00\t0.00\t7.93E-05\t7.93E-05"


class TestProcessFastqcModule:
    """Tests for the _process_fastqc_module helper function."""

    def test_remove_large_per_tile_quality_block(self):
        """Test that Per tile sequence quality blocks exceeding limit are removed."""
        # Create a module with 401 data rows, which will be 404 total (including header, comment, END)
        # exceeding default limit of 400
        lines = [">>Per tile sequence quality\tpass", "#Tile\tBase\tMean"]
        for i in range(401):
            lines.append(f"1\t{i}\t0.5")
        lines.append(">>END_MODULE")

        parse_info = {}
        result = _process_fastqc_module(lines, parse_info)

        # Should be replaced with placeholder
        assert len(result) == 3
        assert result[0] == ">>Per tile sequence quality\tpass"
        assert "This block was too large to include." in result[1]
        assert result[2] == ">>END_MODULE"

        # Should record in parse_info (404 total rows = 401 data + header + comment + END)
        assert "per_tile_sequence_quality_removed" in parse_info
        assert "404 rows" in parse_info["per_tile_sequence_quality_removed"]
        assert "400 limit" in parse_info["per_tile_sequence_quality_removed"]

    def test_keep_small_per_tile_quality_block(self):
        """Test that Per tile sequence quality blocks with ≤200 rows are kept and rounded."""
        lines = [">>Per tile sequence quality\tpass", "#Tile\tBase\tMean"]
        for i in range(50):
            lines.append(f"{i}\t1\t0.53245")
        lines.append(">>END_MODULE")

        parse_info = {}
        result = _process_fastqc_module(lines, parse_info)

        # Should be kept but numbers rounded
        assert len(result) == 53  # header + comment + 50 data + END
        assert "per_tile_sequence_quality_removed" not in parse_info
        # Check that numbers were rounded - all fields should be .00 or .53
        for line in result[2:-1]:  # Skip header, comment, and END
            assert "0.53" in line  # The mean value should be rounded to 0.53

    def test_round_floats_in_other_modules(self):
        """Test that floats are rounded in non-removed modules."""
        lines = [
            ">>Basic Statistics\tpass",
            "#Measure\tValue",
            "Total Sequences\t256892.123456",
            ">>END_MODULE",
        ]

        parse_info = {}
        result = _process_fastqc_module(lines, parse_info)

        assert result[2] == "Total Sequences\t256892.12"
        assert parse_info == {}

    def test_preserve_integers_in_modules(self):
        """Test that integer values in modules are not modified."""
        lines = [
            ">>Sequence Duplication Levels\tpass",
            "#Duplication Level\tPercentage",
            "1\t79.973",
            "2\t14.681",
            ">>END_MODULE",
        ]

        parse_info = {}
        result = _process_fastqc_module(lines, parse_info)

        # Integer "1" and "2" should stay as is, but floats rounded
        assert result[2] == "1\t79.97"
        assert result[3] == "2\t14.68"
        assert parse_info == {}

    def test_preserve_comments_and_headers(self):
        """Test that comment and header lines are preserved."""
        lines = [
            ">>Per base sequence quality\tpass",
            "#Base\tMean\tMedian",
            "1\t31.953190445790447\t33.0",
            ">>END_MODULE",
        ]

        parse_info = {}
        result = _process_fastqc_module(lines, parse_info)

        assert result[0] == ">>Per base sequence quality\tpass"
        assert result[1] == "#Base\tMean\tMedian"
        # "1" is an integer so it's not modified, but floats are rounded
        assert result[2] == "1\t31.95\t33.00"
        assert result[3] == ">>END_MODULE"

    def test_empty_module(self):
        """Test handling of empty module."""
        lines = []
        parse_info = {}
        result = _process_fastqc_module(lines, parse_info)
        assert result == []


class TestParseFastqcReport:
    """Tests for the _parse_fastqc_report main function."""

    def test_parse_basic_report(self):
        """Test parsing a minimal valid FastQC report."""
        report = """##FastQC\t0.12.1
>>Basic Statistics\tpass
#Measure\tValue
Total Sequences\t256892.0
>>END_MODULE
>>Per base sequence quality\tpass
#Base\tMean\tMedian
1\t31.953190445790447\t33.0
2\t32.21115488220731\t33.0
>>END_MODULE
"""
        result, parse_info = _parse_fastqc_report(report)

        # Should have rounded floats but preserved integers
        assert "256892.00" in result
        assert "31.95" in result
        assert "32.21" in result
        # Integer "1" and "2" should remain as is
        assert "\n1\t" in result
        assert "\n2\t" in result

        # No modules should have been removed
        assert parse_info == {}

    def test_parse_report_removes_large_per_tile_block(self):
        """Test that large Per tile sequence quality block is removed."""
        # Create report with large per tile block (exceeding default 400 row limit)
        lines = [
            "##FastQC\t0.12.1",
            ">>Per tile sequence quality\tpass",
            "#Tile\tBase\tMean",
        ]
        for i in range(401):
            lines.append(f"1\t{i}\t0.5")
        lines.extend([">>END_MODULE", ">>Per base sequence quality\tpass"])

        report = "\n".join(lines)
        result, parse_info = _parse_fastqc_report(report)

        # Should indicate removal (404 total rows = 401 data + header + comment + END)
        assert "per_tile_sequence_quality_removed" in parse_info
        assert "404 rows" in parse_info["per_tile_sequence_quality_removed"]

        # Block should be replaced with message
        assert "This block was too large to include." in result

    def test_parse_report_preserves_filenames(self):
        """Test that filenames are preserved correctly."""
        report = """##FastQC\t0.12.1
>>Basic Statistics\tpass
#Measure\tValue
Filename\tBsubtilis_rawdata_231783_2_1.rev.fastq
>>END_MODULE
"""
        result, parse_info = _parse_fastqc_report(report)

        # Filename should be preserved exactly
        assert "Bsubtilis_rawdata_231783_2_1.rev.fastq" in result
        # Should NOT be rounded to have underscores with .00
        assert "231783.00_2.00_1.00" not in result

    def test_parse_report_multiple_modules(self):
        """Test parsing report with multiple modules."""
        report = """##FastQC\t0.12.1
>>Basic Statistics\tpass
#Measure\tValue
Total Sequences\t256892.0
>>END_MODULE
>>Per sequence quality scores\tpass
#Quality\tCount
20\t218.0
30\t1853.0
>>END_MODULE
>>Adapter Content\tpass
#Position\tAdapter1
1\t0.0
2\t0.00001234567
>>END_MODULE
"""
        result, parse_info = _parse_fastqc_report(report)

        # Check all modules are present with rounded values
        assert "256892.00" in result
        assert "218.00" in result
        assert "1853.00" in result

        # First adapter value should be 0.00, second should be in scientific notation (very small)
        lines = result.split("\n")
        adapter_section = False
        for line in lines:
            if "Adapter Content" in line:
                adapter_section = True
            if adapter_section and line.startswith("1\t"):
                assert "0.00" in line
            if adapter_section and line.startswith("2\t"):
                # Very small number should be in scientific notation
                assert "E-0" in line or "e-0" in line.upper()
                break

    def test_parse_report_with_exact_400_rows(self):
        """Test that ~400-row Per tile block is kept (boundary condition)."""
        lines = [
            "##FastQC\t0.12.1",
            ">>Per tile sequence quality\tpass",
            "#Tile\tBase\tMean",
        ]
        # Add enough data rows to keep total <= 400
        for i in range(397):
            lines.append(f"1\t{i}\t0.5")
        lines.append(">>END_MODULE")

        report = "\n".join(lines)
        result, parse_info = _parse_fastqc_report(report)

        # Should NOT be removed - total should be <= 400
        assert "per_tile_sequence_quality_removed" not in parse_info

    def test_parse_report_with_401_rows(self):
        """Test that >400-row Per tile block is removed (boundary condition)."""
        lines = [
            "##FastQC\t0.12.1",
            ">>Per tile sequence quality\tpass",
            "#Tile\tBase\tMean",
        ]
        # Add enough data rows to exceed 400 total
        for i in range(398):
            lines.append(f"1\t{i}\t0.5")
        lines.append(">>END_MODULE")

        report = "\n".join(lines)
        result, parse_info = _parse_fastqc_report(report)

        # Should be removed - total should exceed 400
        assert "per_tile_sequence_quality_removed" in parse_info
        assert "exceeding the 400 limit" in parse_info["per_tile_sequence_quality_removed"]

    def test_parse_report_scientific_notation(self):
        """Test handling of very small scientific notation in the report."""
        report = """##FastQC\t0.12.1
>>Adapter Content\tpass
#Position\tIllumina Universal Adapter
1\t3.7577475519157133E-4
15\t6.228298273204304E-4
>>END_MODULE
"""
        result, parse_info = _parse_fastqc_report(report)

        # Scientific notation should be preserved but with 2 sig figs
        assert "3.76E-04" in result
        assert "6.23E-04" in result
        # Integers should remain unchanged
        assert "\n1\t" in result
        assert "\n15\t" in result
        # Verify the module is present
        assert "Adapter Content" in result

    def test_parse_report_negative_values(self):
        """Test handling of negative numbers."""
        report = """##FastQC\t0.12.1
>>Per tile sequence quality\tpass
#Tile\tBase\tMean
1101\t1\t-0.39234694690636474
1101\t2\t-0.144989755655331
>>END_MODULE
"""
        result, parse_info = _parse_fastqc_report(report)

        # Negative values should be preserved and rounded
        assert "-0.39" in result
        assert "-0.14" in result

    def test_parse_report_with_range_values(self):
        """Test handling of range values like '10-14'."""
        report = """##FastQC\t0.12.1
>>Per base sequence quality\tpass
#Base\tMean
10-14\t36.26104977967395
15-19\t37.45383741027358
>>END_MODULE
"""
        result, parse_info = _parse_fastqc_report(report)

        # Range values with integers should not be rounded, but floats are rounded to 2 decimals
        assert "10-14\t36.26" in result
        assert "15-19\t37.45" in result

    def test_parse_report_empty_lines(self):
        """Test handling of empty lines in the report."""
        report = """##FastQC\t0.12.1
>>Basic Statistics\tpass

#Measure\tValue
Total Sequences\t256892.0

>>END_MODULE
"""
        result, parse_info = _parse_fastqc_report(report)

        # Should handle empty lines gracefully
        assert "256892.00" in result
        lines = result.split("\n")
        # Empty lines should be preserved
        assert "" in lines

    def test_parse_report_return_type(self):
        """Test that function returns correct types."""
        report = "##FastQC\t0.12.1\n>>Basic Statistics\tpass\n>>END_MODULE"
        result = _parse_fastqc_report(report)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)
