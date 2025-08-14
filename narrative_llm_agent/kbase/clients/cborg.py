import requests
from narrative_llm_agent.config import get_config
from narrative_llm_agent.kbase.clients.llm_provider import LLMProviderClient


class CborgAuth(LLMProviderClient):
    def __init__(self, endpoint: str = None):
        if endpoint is None:
            endpoint = get_config().cborg_api_endpoint
        super().__init__(endpoint)
        self._token_path = "user/info"

    def get_key_info(self, api_key: str) -> dict:
        if not api_key:
            raise ValueError("Must provide CBORG API key")
        return self.api_get(self._token_path, {"Authorization": ("Bearer " + api_key)})

    def validate_key(self, api_key: str):
        """
        If the key's valid, this won't fail.
        """
        self.get_key_info(api_key)

    def check_request_error(self, response: requests.Response):
        if response.status_code != 200:
            try:
                resp_data = response.json()
            except Exception:
                err = "Non-JSON response from server, status code: " + str(response.status_code)
                raise IOError(err)

            if "error" in resp_data:
                err_msg = resp_data["error"].get("message", "Unknown error")
            elif "detail" in resp_data:
                err_msg = resp_data["detail"]

            raise CborgError(f"{response.status_code}: {err_msg}")

class CborgError(Exception):
    """Errors from the LBL CBORG API service"""
