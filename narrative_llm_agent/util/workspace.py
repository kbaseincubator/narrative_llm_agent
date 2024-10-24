import json
from narrative_llm_agent.kbase.clients.workspace import Workspace
import requests
import zipfile
import io
from pathlib import Path
from narrative_llm_agent.kbase.objects.report import (
    KBaseReport,
    LinkedFile,
    is_report
)
from narrative_llm_agent.config import get_config

class WorkspaceUtil:
    _ws: Workspace
    _token: str

    def __init__(self, token: str):
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
        if recent.get("method", "").lower() == "runfastqc" and recent.get("service", "").lower() == "kb_fastqc":
            return "fastqc"
        return "other"

    def get_report(self, upa: str) -> str:
        """
        Fetches a report object and returns the relevant portion, depending on what it's
        a report for. Which is hard to say. Maybe it needs the app name?
        """
        # get and test it's a report
        obj = self._ws.get_objects([upa])[0]
        if "info" not in obj or len(obj["info"]) < 10:
            raise ValueError(f"Object with UPA {upa} does not appear to be properly formatted.")
        if not is_report(obj["info"][2]):
            raise ValueError(f"Object with UPA {upa} is not a report but a {obj['info'][2]}.")
        # check report source from provenance and process based on its service and method
        report_source = self._get_report_source(obj["provenance"])
        if report_source == "fastqc":
            return self.translate_fastqc_report(KBaseReport(obj["data"]))
        else:
            return json.dumps(obj)

    def translate_fastqc_report(self, report: KBaseReport) -> str:
        """
        Downloads the report files, which are zipped.
        Unzips and extracts the relevant report info from "fastqc_data.txt"
        """
        report_data = {report_file.name: None for report_file in report.file_links}
        target_file_name = "fastqc_data.txt"
        for report_file in report.file_links:
            resp = self._download_report_file(report_file, self._token)
            comp_file = zipfile.ZipFile(io.BytesIO(resp.content))
            foi = None
            for data_file in comp_file.filelist:
                if Path(data_file.filename).name == target_file_name:
                    foi = data_file
                    break
            if foi is not None:
                with comp_file.open(data_file) as infile:
                    report_data[report_file.name] = infile.read().decode("utf-8")
        report_result = []
        for idx, [name, value] in enumerate(report_data.items()):
            report_result.append(f"file {idx+1}: {name}:")
            report_result.append(value)
        return "\n".join(report_result)

    def _download_report_file(self, report_file: LinkedFile, token: str) -> requests.Response:
        url = report_file.url
        if "shock-api" in url:
            # url looks like:
            # https://env.kbase.us/services/shock-api/node/<shock-uuid>
            # we need to make it look like
            # https://env.kbase.us/services/data_import_export/download?id=<shock_uuid>&wszip=0&name=<filename>
            node = url.split("/shock-api/node/")[-1]
            url = f"{get_config().service_endpoint}blobstore/node/{node}?download"
        headers = {
            "Authorization": f"OAuth {token}"
        }
        resp = requests.get(url, headers=headers)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            raise ValueError(f"HTTP status code {resp.status_code} for report file at {url} (original url {report_file.url})")
        return resp
