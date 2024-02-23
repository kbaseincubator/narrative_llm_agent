import pytest
import requests_mock

@pytest.fixture
def mock_auth_request(requests_mock):
    def auth_request(url: str, token: str, return_value: dict, status_code: int=200):
        requests_mock.register_uri(
            "GET",
            url,
            request_headers={"Authorization": token},
            json=return_value,
            status_code=status_code
        )
    return auth_request

@pytest.fixture
def mock_auth_request_ok(mock_auth_request):
    def auth_request_ok(url: str, token: str):
        auth_success = {
            "type": "Login",
            "id": "blah_blah_token_id",
            "expires": 1714583567055,
            "created": 1706807567055,
            "name": "llm agency",
            "user": "j_random_user",
            "custom": {},
            "cachefor": 300000
        }
        mock_auth_request(url, token, auth_success)
        return auth_success
    return auth_request_ok

@pytest.fixture
def mock_auth_request_bad_token(mock_auth_request):
    def auth_request_bad_token(url: str, token: str):
        unauth_error = {
            "error": {
                "httpcode": 401,
                "httpstatus": "Unauthorized",
                "appcode": 10020,
                "apperror": "Invalid token",
                "message": "10020 Invalid token",
                "callid": "12345",
                "time": 1708720112853
            }
        }
        mock_auth_request(url, token, unauth_error, status_code=401)
        return unauth_error
    return auth_request_bad_token

@pytest.fixture
def mock_kbase_server_error(requests_mock):
    def mock_generic_error(method: str, url: str, err: dict):
        requests_mock.register_uri(method, url, status_code=500, json=err)
    return mock_generic_error
