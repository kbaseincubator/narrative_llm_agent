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
        report_data[report_file.name] = file_data[target_file_name]
    report_result = []
    for idx, [name, value] in enumerate(report_data.items()):
        report_result.append(f"file {idx + 1}: {name}:")
        report_result.append(value)
    return "\n".join(report_result)


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
