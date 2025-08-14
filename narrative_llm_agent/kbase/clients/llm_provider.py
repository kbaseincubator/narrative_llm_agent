from abc import ABC, abstractmethod
import requests

class LLMProviderClient(ABC):
    def __init__(self, endpoint: str):
        self._endpoint = endpoint

    def api_get(self, path: str, headers: dict[str, str]) -> dict:
        response = requests.get(self._endpoint + path, headers=headers)
        self.check_request_error(response)
        return response.json()

    @abstractmethod
    def check_request_error(self, response: requests.Response):
        pass

    @abstractmethod
    def validate_key(self, api_key: str):
        pass
