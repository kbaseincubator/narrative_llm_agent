import requests
from narrative_llm_agent.config import get_config
from narrative_llm_agent.kbase.clients.llm_provider import LLMProviderClient

class OpenAIAuth(LLMProviderClient):
    def __init__(self, endpoint: str = None):
        if endpoint is None:
            endpoint = get_config().openai_api_endpoint
        super().__init__(endpoint)
        self._models_path = "v1/models"

    def get_models_list(self, api_key: str) -> dict:
        """
        Returns a list of OpenAI models.
        This fails if the api_key is invalid or missing, so is a decent
        measure for validity.
        """
        return self.api_get(self._models_path, {"Authorization": ("Bearer " + api_key)})

    def validate_key(self, api_key: str):
        """
        If the key's valid, this won't fail.
        """
        if not api_key:
            raise ValueError("Must provide OpenAI API key")
        self.get_models_list(api_key)

    def check_request_error(self, response: requests.Response):
        if response.status_code != 200:
            try:
                resp_data = response.json()
            except Exception:
                err = "Non-JSON response from server, status code: " + str(response.status_code)
                raise IOError(err)

            if "error" in resp_data:
                err_msg = resp_data["error"].get("message", "Unknown error")
            else:
                err_msg = "Unknown error reported from OpenAI server"

            raise OpenAIError(f"{response.status_code}: {err_msg}")


class OpenAIError(Exception):
    """Errors from the LBL CBORG API service"""
