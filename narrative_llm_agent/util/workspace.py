from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.blobstore import Blobstore

# import requests
import zipfile
import io
from pathlib import Path
from narrative_llm_agent.kbase.objects.report import (
    KBaseReport,
    LinkedFile,
    is_report,
)


class WorkspaceUtil:
    _ws: Workspace
    _token: str

    def __init__(self, token: str = None):
        self._token = token
        self._ws = Workspace(token=self._token)

    def _get_report_source(self, provenance: list[dict]) -> str:
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
        return "other"

    def get_report(self, upa: str) -> str:
        """
        Fetches a report object and returns the relevant portion, depending on what it's
        a report for. Which is hard to say. Maybe it needs the app name?
        """
        # get and test it's a report
        obj = self._ws.get_objects([upa])[0]
        if "info" not in obj or len(obj["info"]) < 10:
            raise ValueError(
                f"Object with UPA {upa} does not appear to be properly formatted."
            )
        if not is_report(obj["info"][2]):
            raise ValueError(
                f"Object with UPA {upa} is not a report but a {obj['info'][2]}."
            )
        # check report source from provenance and process based on its service and method
        report_source = self._get_report_source(obj["provenance"])
        report = KBaseReport(**obj["data"])
        if report_source == "fastqc":
            return self.translate_fastqc_report(report)
        elif report_source == "checkm":
            return self.translate_checkm_report(report)
        else:
            return self.default_translate_report(report)

    def default_translate_report(self, report: KBaseReport) -> str:
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
            html_texts.append(link.label + ":\n" + self._fetch_html_file(link))
        html_text = "\n".join(html_texts)
        return "\n".join(
            [
                f"message: {message}",
                f"direct html: {direct_html}",
                f"html report: {html_text}",
            ]
        )

    def translate_checkm_report(self, report: KBaseReport) -> str:
        summary_header = "CheckM summary table:"
        summary = "not found"
        target_file_name = "CheckM_summary_table.tsv.zip"
        target_unzipped_file = "CheckM_summary_table.tsv"
        target_url = None
        for report_file in report.file_links:
            if report_file.name == target_file_name:
                target_url = report_file.URL
        if target_url is not None:
            blobstore = Blobstore(token=self._token)
            resp = blobstore.download_report_file(target_url)
            comp_file = zipfile.ZipFile(io.BytesIO(resp.content))
            foi = None
            for data_file in comp_file.filelist:
                if Path(data_file.filename).name == target_unzipped_file:
                    foi = data_file
                    break
            if foi is not None:
                with comp_file.open(foi) as infile:
                    summary = infile.read().decode("utf-8")
        return "\n".join([summary_header, summary])

    def translate_fastqc_report(self, report: KBaseReport) -> str:
        """
        Downloads the report files, which are zipped.
        Unzips and extracts the relevant report info from "fastqc_data.txt"
        """
        report_data = {report_file.name: None for report_file in report.file_links}
        target_file_name = "fastqc_data.txt"
        blobstore = Blobstore(token=self._token)
        for report_file in report.file_links:
            resp = blobstore.download_report_file(report_file.URL)
            # resp = self._download_report_file(report_file, self._token)
            comp_file = zipfile.ZipFile(io.BytesIO(resp.content))
            foi = None
            for data_file in comp_file.filelist:
                if Path(data_file.filename).name == target_file_name:
                    foi = data_file
                    break
            if foi is not None:
                with comp_file.open(foi) as infile:
                    report_data[report_file.name] = infile.read().decode("utf-8")
        report_result = []
        for idx, [name, value] in enumerate(report_data.items()):
            report_result.append(f"file {idx + 1}: {name}:")
            report_result.append(value)
        return "\n".join(report_result)

    def _fetch_html_file(self, html_file: LinkedFile) -> str:
        """
        Uses the information in the given LinkedFile to fetch the html report
        and return it as a string.
        """
        blobstore = Blobstore(token=self._token)
        resp = blobstore.download_report_file(html_file.URL)
        comp_file = zipfile.ZipFile(io.BytesIO(resp.content))
        # skim through and find the file with the given name in the zip
        for data_file in comp_file.filelist:
            if Path(data_file.filename).name == html_file.name:
                with comp_file.open(data_file) as infile:
                    return infile.read().decode("utf-8")
        return ""
