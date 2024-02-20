import json
from narrative_llm_agent.kbase.clients.workspace import Workspace
import requests
import zipfile
import io
from pathlib import Path
from narrative_llm_agent.kbase.objects.narrative import (
    Narrative,
    is_narrative,
    NARRATIVE_ID_KEY
)
from narrative_llm_agent.kbase.objects.report import (
    KBaseReport,
    LinkedFile,
    is_report
)

class WorkspaceUtil:
    _ws: Workspace
    _service_endpoint: str
    _token: str

    def __init__(self, token: str, service_endpoint: str):
        self._token = token
        self._service_endpoint = service_endpoint
        self._ws = Workspace(self._token, self._service_endpoint + "ws")

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
            return json.dumps(self.translate_fastqc_report(KBaseReport(obj["data"])))
        else:
            return json.dumps(obj)

    def translate_fastqc_report(self, report: KBaseReport) -> dict:
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
        return report_data

    def _download_report_file(self, report_file: LinkedFile, token: str) -> requests.Response:
        url = report_file.url
        if "shock-api" in url:
            # url looks like:
            # https://env.kbase.us/services/shock-api/node/<shock-uuid>
            # we need to make it look like
            # https://env.kbase.us/services/data_import_export/download?id=<shock_uuid>&wszip=0&name=<filename>
            node = url.split("/shock-api/node/")[-1]
            url = f"{self._service_endpoint}/data_import_export/download?id={node}&wszip=0&name={report_file.name}"
        headers = {
            "Authorization": token
        }
        resp = requests.get(url, headers=headers)
        try:
            resp.raise_for_status()
        except:
            raise ValueError(f"HTTP status code {resp.status_code} for report file at {url} (original url {report_file.url})")
        return resp

    def get_narrative_from_wsid(self, ws_id: int, ver: int=None) -> Narrative:
        """
        Returns a Narrative object from the workspace with the given wsid.
        """
        ws_info = self._ws.get_workspace_info(ws_id)
        if NARRATIVE_ID_KEY not in ws_info.meta:
            raise ValueError(f"No narrative found in workspace {ws_id}")

        narr_ref = f"{ws_id}/{ws_info.meta[NARRATIVE_ID_KEY]}"
        narr_obj = self._ws.get_objects([narr_ref])[0]
        if not is_narrative(narr_obj["info"][2]):
            raise ValueError(f"The object with reference {narr_ref} is not a KBase Narrative.")

        return Narrative(narr_obj["data"])
