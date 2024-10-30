from ..service_client import ServiceClient
from narrative_llm_agent.config import get_config
import requests


class Blobstore(ServiceClient):
    _service = "blobstore"

    def __init__(self: "Blobstore", endpoint: str = None, token: str = None) -> None:
        if endpoint is None:
            endpoint = get_config().blobstore_endpoint
        super().__init__(endpoint, self._service, token=token)

    def download_report_file(self: "Blobstore", report_url: str) -> requests.Response:
        download_url = report_url
        if "shock-api" in report_url:
            # url looks like:
            # https://env.kbase.us/services/shock-api/node/<shock-uuid>
            # we need to make it look like
            # https://env.kbase.us/services/data_import_export/download?id=<shock_uuid>&wszip=0&name=<filename>
            node = report_url.split("/shock-api/node/")[-1]
            download_url = f"{get_config().blobstore_endpoint}/node/{node}?download"
        headers = {"Authorization": f"OAuth {self._token}"}
        resp = requests.get(download_url, headers=headers)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            raise ValueError(
                f"HTTP status code {resp.status_code} for report file at {download_url} (original url {report_url})"
            )
        return resp
