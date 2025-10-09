from datetime import datetime
from narrative_llm_agent.kbase.service_client import ServiceClient
import requests
import uuid
from typing import Any
from narrative_llm_agent.config import get_kbase_auth_token, get_config

class DynamicServiceClient(ServiceClient):
    def __init__(
        self,
        service: str,
        endpoint: str = None,
        token: str = None,
        timeout: int = 1800,
        url_cache_time: int = 3600,
        service_version: str = None
    ):
        self._service = service
        if endpoint is None:
            endpoint = get_config().service_wizard_endpoint
        self._endpoint = endpoint
        self._token = token
        self._timeout = timeout
        self._headers = {}
        if self._token is None:
            self._token = get_kbase_auth_token()
        if self._token is not None:
            self._headers["Authorization"] = self._token
        self._timeout = timeout
        self._url_cache_time = url_cache_time
        self.service_endpoint = None
        self.last_update = datetime.fromtimestamp(0)
        self._service_version = service_version

    def _need_url_update(self):
        return int((datetime.now() - self.last_update).total_seconds()) >= self._url_cache_time

    def _get_service_endpoint(self):
        if self.service_endpoint is None or self._need_url_update():
            resp = self.make_kbase_jsonrpc_1_call(
                "ServiceWizard.get_service_status",
                [{"module_name": self._service, "version": self._service_version}]
            )[0]
            self.service_endpoint = resp["url"]
        return self.service_endpoint

    def simple_call(self, method: str, params: Any) -> Any:
        endpoint = self._get_service_endpoint()
        return self.make_kbase_jsonrpc_1_call(f"{self._service}.{method}", [params], endpoint=endpoint)[0]
