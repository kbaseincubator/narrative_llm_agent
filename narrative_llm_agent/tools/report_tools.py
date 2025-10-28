from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.blobstore import Blobstore
from bs4 import BeautifulSoup

import zipfile
import io
from pathlib import Path
from narrative_llm_agent.kbase.objects.report import (
    KBaseReport,
    LinkedFile,
    is_report,
)
import re


def get_report(upa: str, ws: Workspace, blobstore: Blobstore) -> str:
    """
    Fetches a report object and returns the relevant portion, depending on what it's
    a report for. Which is hard to say. Maybe it needs the app name?
    """
    # get and test it's a report
    obj = ws.get_objects([upa])[0]
    if "info" not in obj or len(obj["info"]) < 10:
        raise ValueError(
            f"Object with UPA {upa} does not appear to be properly formatted."
        )
    if not is_report(obj["info"][2]):
        raise ValueError(
            f"Object with UPA {upa} is not a report but a {obj['info'][2]}."
        )
    # check report source from provenance and process based on its service and method
    report_source = _get_report_source(obj["provenance"])
    report = KBaseReport(**obj["data"])
    if report_source == "fastqc":
        return _translate_fastqc_report(report, blobstore)
    elif report_source == "checkm":
        return _translate_checkm_report(report, blobstore)
    elif report_source == "gtdbtk":
        return _translate_gtdb_report(report, blobstore)
    else:
        return _default_translate_report(report, blobstore)


def get_report_from_job_id(
    job_id: str, ee: ExecutionEngine, ws: Workspace, blobstore: Blobstore
) -> str:
    """
    Uses the job id to fetch a report from the workspace service.
    This fetches the job information from the Execution Engine service first.
    If the job is not complete, this returns a string saying so.
    If the job is complete, but there is no report object in the output, this returns a
    string saying so.
    If the job is complete and has a report in its outputs, this tries to fetch
    the report using the UPA of the report object.
    """
    state = ee.check_job(job_id)
    if state.status in ["queued", "running"]:
        return "The job is not yet complete"
    if state.status in ["terminated", "error"]:
        return "The job did not finish successfully, so there is no report to return."
    if state.status != "completed":
        return f"Unknown job status '{state.status}'"
    if state.job_output is not None:
        # look for report_ref or report_name. Maybe just name?
        # Note: I checked out all app specs in production - report_ref and report_name are both
        # used as "magic values" in the narrative to denote a report object. So really we just need
        # to look for the report_ref one. They're both present in each app that makes a report.
        # So, we need to some sifting here
        if "result" in state.job_output and isinstance(
            state.job_output["result"], list
        ):
            if "report_ref" in state.job_output["result"][0]:
                return get_report(
                    state.job_output["result"][0]["report_ref"], ws, blobstore
                )
            else:
                return "No report object was found in the job results."
        else:
            return "The job output seems to be malformed, there is no 'result' field."
    return "The job was completed, but no job output was found."


def _get_report_source(provenance: list[dict]) -> str:
    """
    Parses the object provenance to get the most likely source method for that report
    so we can tease apart the structure and return what's necessary for the LLM to do its
    thing. Should be in the first provenance action.

    Tuned for fastqc right now. Others to come!
    """
    recent = provenance[0]
    method = recent.get("method", "").lower()
    service = recent.get("service", "").lower()
    if method == "runfastqc" and service == "kb_fastqc":
        return "fastqc"
    elif method == "run_checkm_lineage_wf" and service == "kb_msuite":
        return "checkm"
    elif method == "run_kb_gtdbtk_classify_wf" and service == "kb_gtdbtk":
        return "gtdbtk"
    return "other"


def _default_translate_report(report: KBaseReport, blobstore: Blobstore) -> str:
    """
    The default version of a report fetcher. This tries to help the LLM
    by fetching report information. It does this by concatenating together
    different bits of report information. In order of appearance, these are:
    1. text message
    2. direct html
    3. HTML scraped from html links, with direct_html_link_index being first,
        if applicable
    """
    message = report.text_message or ""
    direct_html = report.direct_html or ""
    html_texts = []
    for link in report.html_links:
        html_texts.append(
            link.label
            + ":\n"
            + _minimize_html_report(_fetch_html_file(link, blobstore))
        )
    html_text = "\n".join(html_texts)
    return "\n".join(
        [
            f"message: {message}",
            f"direct html: {direct_html}",
            f"html report: {html_text}",
        ]
    )


def _translate_gtdb_report(report: KBaseReport, blobstore: Blobstore) -> str:
    id_map = Path("id_to_name.map")
    archaea_summary = Path("gtdbtk.ar53.summary.tsv")
    bac_summary = Path("gtdbtk.bac120.summary.tsv")
    file_url = _get_file_url("GTDB-Tk_classify_wf.zip", report)
    if file_url is None:
        return "report file not found"
    extracted_files = _extract_report_files(
        file_url, [id_map, archaea_summary, bac_summary], blobstore
    )
    summary = ""

    if extracted_files[id_map] is not None:
        summary += (
            "id mapping - use this table to map summary ids to data objects. Each row has two elements - the first is the id of the archaea or bacteria finding, the second is the data object name.\n"
            + extracted_files[id_map]
            + "\n\n"
        )
    if extracted_files[archaea_summary] is not None:
        summary += (
            "GTDB Classification Summary - this table summarizes the archaeal findings from GTDB\n"
            + extracted_files[archaea_summary]
            + "\n\n"
        )
    if extracted_files[bac_summary] is not None:
        summary += (
            "GTDB Classification Summary - this table summarizes the bacterial findings from GTDB\n"
            + extracted_files[bac_summary]
        )
    return summary


def _translate_checkm_report(report: KBaseReport, blobstore: Blobstore) -> str:
    summary_header = "CheckM summary table:"
    target_file_name = "CheckM_summary_table.tsv.zip"
    target_unzipped_file = "CheckM_summary_table.tsv"
    target_url = _get_file_url(target_file_name, report)
    summary = None
    if target_url is not None:
        file_data = _extract_report_files(
            target_url, [target_unzipped_file], blobstore, only_check_filename=True
        )
        summary = file_data[target_unzipped_file]
    if summary is None:
        summary = "not found"
    return "\n".join([summary_header, summary])


def _translate_fastqc_report(report: KBaseReport, blobstore: Blobstore) -> str:
    """
    Downloads the report files, which are zipped.
    Unzips and extracts the relevant report info from "fastqc_data.txt"
    """
    report_data = {report_file.name: None for report_file in report.file_links}
    target_file_name = "fastqc_data.txt"
    for report_file in report.file_links:
        file_data = _extract_report_files(
            report_file.URL, [target_file_name], blobstore, only_check_filename=True
        )
        parsed, parse_info = _parse_fastqc_report(file_data[target_file_name])
        if "per_tile_sequence_quality_removed" in parse_info:
            parsed = parse_info["per_tile_sequence_quality_removed"] + "\n\n" + parsed
        report_data[report_file.name] = parsed
    report_result = []
    for idx, [name, value] in enumerate(report_data.items()):
        report_result.append(f"file {idx + 1}: {name}:")
        report_result.append(value)
    return "\n".join(report_result)


def _parse_fastqc_report(report: str, tile_quality_limit: int=400) -> tuple[str, dict[str, str]]:
    """
    Parses and modifies a FastQC report file (e.g. fastqc_data.txt). Expects the file to be in
    the FastQC format. Each block in this format is defined as starting with `>>title`
    and ending with `>>END_MODULE`
    For example:

    >>Basic Statistics	pass
    #Measure	Value
    Filename	Bsubtilis_rawdata_231783_2_1.rev.fastq
    File type	Conventional base calls
    Encoding	Sanger / Illumina 1.9
    Total Sequences	256892
    Total Bases	38.2 Mbp
    Sequences flagged as poor quality	0
    Sequence length	35-151
    %GC	43
    >>END_MODULE

    and

    >>Per base sequence quality	pass
    #Base	Mean	Median	Lower Quartile	Upper Quartile	10th Percentile	90th Percentile
    1	31.953190445790447	33.0	32.0	33.0	32.0	34.0
    2	32.21115488220731	33.0	32.0	34.0	32.0	34.0
    3	32.60782352116843	33.0	32.0	34.0	32.0	34.0
    4	32.62077838157669	33.0	32.0	34.0	32.0	34.0
    5	32.696927113339456	33.0	32.0	34.0	32.0	34.0
    ...etc
    >>END_MODULE

    This parser does the following.
    1. Convert any floating point numerical value to have a fixed amount of digits - 2
    2. Remove the `Per tile sequence quality` block if it's very long (more than 200 rows) and put in
        a message saying it was too long.
    3. Return it to being a string.

    This returns the converted string and a dictionary with information about what was
    changed or removed and why. It also includes extra prompt information for the LLM that
    will be doing the data interpretation.
    """
    lines = report.split("\n")
    parsed_lines = []
    parse_info = {}
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is the start of a module
        if line.startswith(">>"):
            module_header = line
            module_lines = [module_header]
            i += 1

            # Collect all lines until >>END_MODULE
            while i < len(lines) and not lines[i].startswith(">>END_MODULE"):
                module_lines.append(lines[i])
                i += 1

            # Add the >>END_MODULE line
            if i < len(lines) and lines[i].startswith(">>END_MODULE"):
                module_lines.append(lines[i])

            # Process the module
            processed_module = _process_fastqc_module(module_lines, parse_info, tile_quality_limit=tile_quality_limit)
            parsed_lines.extend(processed_module)
        else:
            # Regular lines (like ##FastQC header)
            parsed_lines.append(line)
        i += 1

    result_string = "\n".join(parsed_lines)
    return result_string, parse_info


def _process_fastqc_module(module_lines: list[str], parse_info: dict, tile_quality_limit: int=400) -> list[str]:
    """
    Process a single FastQC module block.
    1. Check if it's "Per tile sequence quality" and if it has more than 200 data rows
    2. Round floating point numbers to 2 decimal places
    3. Return the processed lines
    """
    if not module_lines:
        return module_lines

    header = module_lines[0]

    # Check if this is the "Per tile sequence quality" block
    if "Per tile sequence quality" in header and len(module_lines) > tile_quality_limit:
        parse_info["per_tile_sequence_quality_removed"] = (
            f"Per tile sequence quality block was removed because it contained {len(module_lines)} rows, "
            f"exceeding the {tile_quality_limit} limit. This block details quality scores per tile and sequencing position. "
            "The data was too verbose for LLM processing, so it was omitted."
        )
        return [header, "This block was too large to include.", ">>END_MODULE"]

    # Process all lines to round floating point numbers
    processed_lines = []
    for line in module_lines:
        if line.startswith(">>") or line.startswith("#") or not line.strip():
            # Header, comment, or empty lines - keep as-is
            processed_lines.append(line)
        else:
            # Data line - process floating point numbers (values separated by tabs/spaces)
            # This is a tab or space-delimited data line, so we can safely round all numbers
            processed_line = _round_floats_in_line(line)
            processed_lines.append(processed_line)

    return processed_lines


def _round_floats_in_line(line: str) -> str:
    """
    Round floating point numbers in a line. Integers are left unchanged.
    Regular floats are rounded to 2 decimal places. Very small numbers
    (< 0.01) in scientific notation are kept as scientific with 2 sig figs.

    This operates on tab-separated fields to avoid rounding numbers
    embedded in filenames or other strings with underscores/special chars.

    Examples:
    - 4 -> 4 (unchanged, it's an integer)
    - 4.0 -> 4.00 (float, 2 decimal places)
    - 31.953190445790447 -> 31.95 (float, 2 decimal places)
    - 0.0 -> 0.00 (float, 2 decimal places)
    - 2.6426837828009912E-5 -> 2.64E-5 (very small, 2 sig figs in scientific)
    - 0.0001234567 -> 1.23E-4 (very small, converted to scientific)
    """

    # Split by tabs (FastQC uses tabs for data fields)
    fields = line.split("\t")

    def round_float_in_field(field):
        """Round floats in a single field, preserving integers."""
        # Skip fields that contain underscores or other file-like characters
        # mixed with numbers (likely filenames or paths)
        if "_" in field or "/" in field:
            return field

        # Try to parse as a pure float/number first
        try:
            num = float(field)
            # Check if it's an integer (no decimal point or E notation in original field)
            if "." not in field and "e" not in field.lower():
                # It's an integer, leave it unchanged
                return field
            # It's a float, format with appropriate precision
            return _format_float_value(num)
        except ValueError:
            pass

        # For fields with ranges like "10-14" or scientific notation
        # Only process if the field is mostly numeric (numbers, dots, dashes, E)
        if not re.match(r"^[\d.\-eE\s]+$", field):
            return field

        def round_float(match):
            try:
                num = float(match.group())
                original = match.group()
                # Check if this is an integer value
                if "." not in original and "e" not in original.lower():
                    return original
                return _format_float_value(num)
            except ValueError:
                return match.group()

        # Round floating point numbers
        pattern = r"-?\d+\.?\d*([eE][+-]?\d+)?|-?\d+\.\d+"
        return re.sub(pattern, round_float, field)

    processed_fields = [round_float_in_field(field) for field in fields]
    return "\t".join(processed_fields)


def _format_float_value(num: float) -> str:
    """
    Format a float value, choosing appropriate precision based on magnitude.
    - Regular floats (>= 0.01): 2 decimal places
    - Very small floats (< 0.01): scientific notation with 2 significant figures

    Examples:
    - 31.953 -> "31.95"
    - 0.0 -> "0.00"
    - 0.00001234567 -> "1.23E-5"
    """
    if num == 0:
        return "0.00"

    # Check if the absolute value is very small (less than 0.01)
    if abs(num) < 0.01:
        # Use scientific notation with 2 significant figures
        # Format to 2 decimal places in the mantissa (1 digit before decimal, 1 after)
        formatted = f"{num:.2e}".upper()
        return formatted
    else:
        # Regular decimal format with 2 decimal places
        return f"{num:.2f}"


def _fetch_html_file(html_file: LinkedFile, blobstore: Blobstore) -> str:
    """
    Uses the information in the given LinkedFile to fetch the html report
    and return it as a string.

    If any errors happen, or the expected file isn't found in the HTML
    archive, an empty string is returned.
    """
    try:
        resp = blobstore.download_report_file(html_file.URL)
        comp_file = zipfile.ZipFile(io.BytesIO(resp.content))
    except ValueError:
        return ""

    # skim through and find the file with the given name in the zip
    for data_file in comp_file.filelist:
        if Path(data_file.filename).name == html_file.name:
            with comp_file.open(data_file) as infile:
                return infile.read().decode("utf-8")
    return ""


def _minimize_html_report(html_text: str) -> str:
    """
    Minimizes html reports by removing styles and javascript.
    This removes <head>, <script> and <style> tags.
    TODO: add more, alter per-app?
    """
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup.find_all(["head", "script", "style"]):
        tag.decompose()
    return str(soup)


def _extract_report_files(
    zip_file_url: str,
    files_of_interest: list[str | Path],
    blobstore: Blobstore,
    only_check_filename: bool = False,
) -> dict[Path, str]:
    """
    Extracts and loads specific files out of a zip file, by its url.
    It does the following:
    1. Download the zip file at the given zip_file_url in the Blobstore.
    2. Extract files of interest by their path.
    3. Build a dictionary of path -> file contents and return it.
    If a path doesn't exist, that value is None in the return dictionary.
    If zip_file_url is invalid or otherwise inaccessible, a ValueError is raised.
    If the file at zip_file_url isn't a zip file (or something that can be opened with the zipfile
    package), a ValueError is raised.

    :param zip_file_url: This is the URL of the zip file to pull and extract. It should be
    hosted in the KBase blobstore, likely given by a file link in a report object.
    :param files_of_interest: This is a list of Paths to files in the zip file to extract.
    They should all be relative to the root of the zip file. The Path object itself will
    be used as the key in the returned dictionary.
    :param only_check_filenames: If true, this will find the filename of the path in any directory
    of the downloaded zip file. This assumes that the given paths in files_of_interest is a string,
    and not a Path. Paths will always return None in this case.
    If there are multiple files with the same name, only one gets returned.
    """
    resp = blobstore.download_report_file(zip_file_url)
    comp_file = zipfile.ZipFile(io.BytesIO(resp.content))
    extracted = {file_path: None for file_path in files_of_interest}
    for data_file in comp_file.filelist:
        data_path = Path(data_file.filename)
        compare_name = data_path.name if only_check_filename else data_path
        if compare_name in extracted:
            with comp_file.open(data_file) as infile:
                extracted[compare_name] = infile.read().decode("utf-8")
    return extracted


def _get_file_url(filename: str, report: KBaseReport) -> str | None:
    """
    Gets the URL of a file with a given name from a report object, if present.
    If not, this returns None.
    """
    for report_file in report.file_links:
        if report_file.name == filename:
            return report_file.URL
    return None
